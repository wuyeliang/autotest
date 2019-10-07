#!/usr/bin/env python2


# user facing commands:
#
#  -- write_statjson_hostnames
#  -- do_quick_add



# pretty_dump_board:

# Given the name of a board, dump it to a directory with
# the following structure:

# data.dir
#   - hostname1
#   - hostname2
#   - hostname3

# NEXT, report all the ways in which hostnames of that board are not valid
# jsonified protobufs for adding a new DUT.
#
# this involves shelling out to skylab validate-new-dut-json



# adding a dut that's already present
# $ skylab quick-add-dut /tmp/json
# Deployment ID:         d604b46b-87c7-4a4d-8b8a-ed97565c4797
# Status:                DUT_DEPLOYMENT_STATUS_FAILED
# Inventory change URL:
# Deploy task URL:
# Message:               failed to add DUT(s) to fleet: add dut to fleet: inventory store commit: nothing to commit


# adding a dut successfully
# $ skylab quick-add-dut /tmp/json
# Deployment ID:         8e27b3ff-39ad-4b92-9bea-3f804a9d7bf9
# Status:                DUT_DEPLOYMENT_STATUS_FAILED
# Inventory change URL:  https://chrome-internal-review.googlesource.com/c/chromeos/infra_internal/skylab_inventory/+/1940714
# Deploy task URL:
# Message:               missing deploy task ID in deploy request entry



# $ atest host rename --for-migration --non-interactive chromeos2-row1-rack7-host1
# Successfully renamed:
# chromeos2-row1-rack7-host1 to chromeos2-row1-rack7-host1-migrated-do-not-use


# unsuccessful lock

# $ atest host mod --lock -r 'migration to skylab' chromeos2-row1-rack7-host1-migrated-do-not-use
# Operation modify_host failed:
#     ValidationError: {'locked': u'Host chromeos2-row1-rack7-host1-migrated-do-not-use already locked by pprabhu on 2019-08-29 16:48:51.'}
#    1


# successful lock



from __future__ import print_function
from __future__ import unicode_literals
import os
import sys
import subprocess
import pipes
import os.path
import warnings
import json
import tempfile
import shutil

TEXT = (type(b""), type(u""))
NONETYPE = type(None)


def flush_sync(fh):
    fh.flush()
    os.fsync(fh)
    return


# accepts: shell command, rest of args
# returns: exit_status, stdout, stderr
def shell_capture_all(cmd, *rest):
    shellcmd = ("bash", "-c", cmd, "bash",) + rest
    pr = subprocess.Popen(
        shellcmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = pr.communicate()
    return pr.returncode, stdout, stderr


# accepts: name of board
# returns: list of hostnames, error message (None if no error)
def get_all_hosts_for_board(board):
    # extract just the hostnames for all the hosts in the board
    cmd = "set -o pipefail; ( atest host list --label=%%%LABEL%%% | awk '{print $1}' )"
    cmd = cmd.replace("%%%LABEL%%%", pipes.quote("board:%s" % board))
    returncode, out, err = shell_capture_all(cmd)
    if returncode != 0:
        return None, "get_all_hosts_for_board: " + err
    hostnames = [x.strip() for x in out.split()]
    if hostnames and hostnames[0] == "Host":
        hostnames.pop(0)
    return hostnames, None


# make a directory and test if we can write to it as defensively as possible
# free vars: %%%DEST%%%
MAKE_DIR_CMD = r"""
mkdir -p %%%DEST%%%
cd %%%DEST%%% && touch ./writeable && rm ./writeable
"""


# free vars: %%%HOSTNAME%%% %%%DEST%%%
STATJSON_CMD = r"""
atest host statjson %%%HOSTNAME%%% 1>%%%DEST%%%/%%%HOSTNAME%%%
"""

# accepts: path to directory
# returns: error message (None if successfully made dir)
def mkdirp(dirpath):
    cmd = MAKE_DIR_CMD.replace('%%%DEST%%%', pipes.quote(dirpath))
    returncode, out, err = shell_capture_all(cmd)
    if returncode == 0:
        return None
    else:
        return err


# accepts: list of hostnames, output directory (path)
# returns: successful hosts, failed hosts, error message (None if no error)
def write_statjson_hostnames(hostnames, outdir):
    successful_hosts = []
    failed_hosts = []
    err = mkdirp(outdir)
    if err is not None:
        return None, None, err
    for hostname in hostnames:
        cmd = STATJSON_CMD
        cmd = cmd.replace('%%%HOSTNAME%%%', pipes.quote(hostname))
        cmd = cmd.replace('%%%DEST%%%', pipes.quote(outdir))
        returncode, out, err = shell_capture_all(cmd)
        if returncode == 0:
            successful_hosts.append(hostname)
        else:
            failed_hosts.append(hostname)
    return successful_hosts, failed_hosts, None


# accepts: board name, output directory
# returns: successful hosts, failed hosts, error message
def write_statjson_board(board, outdir):
    hostnames, err = get_all_hosts_for_board(board)
    if err is not None:
        return None, None, err
    successful_hosts, failed_hosts, err = write_statjson_hostnames(hostnames, outdir)
    return successful_hosts, failed_hosts, err


# free vars: %%%PATH%%%
VALIDATE_CMD = r"""
skylab validate-new-dut-json %%%PATH%%%
"""


# accepts: directory with hostname files
# returns: dictionary of the form below, error message (or None if no error)
#
# {
#    hostname: error message (or None if no error)
# }
def validate_output(hostname_dir):
    try:
        paths = os.listdir(hostname_dir)
    except OSError:
        return None, ("bad directory: %s" % hostname_dir)

    # defensively populate result dictionary with errors
    # so that we don't erroneously conclude that an unvisited
    # hostname was validated
    result = {}
    for path in paths:
        result[path] = "DID NOT PROCESS"

    for path in paths:
        cmd = VALIDATE_CMD
        cmd = cmd.replace('%%%PATH%%%', pipes.quote(os.path.join(hostname_dir, path)))
        returncode, out, err = shell_capture_all(cmd)
        if returncode != 0:
            result[path] = "failed to validate (errcode %s): %s" % (returncode, err)
        elif os.path.exists(os.path.join(hostname_dir, path)):
            result[path] = None
        else:
            warnings.warn("nonexistent path %s" % path)
            result[path] = "file does not exist"

    return result, None



# accepts: name of board, output directory
# returns: dictionary of form below, error message (or None if no error)
#
# {
#    hostname: error-message or NOFILE if no file or None if no error
# }
def process_board(board, output_dir):
    queried_hosts, unqueried_hosts, err = write_statjson_board(board, output_dir)
    if err is not None:
        return None, err
    validate_result, err = validate_output(output_dir)
    if err is not None:
        return None, err
    result = {}

    for hostname in queried_hosts:
        try:
            result[hostname] = validate_result[hostname]
        except KeyError:
            warnings.warn("hostname (%s) not present in validate_result")

    for hostname in unqueried_hosts:
        result["hostname"] = "NOFILE"

    return result, None


# accepts: name of board, output directory
# returns: number of bad hosts
# emits:   prints error message for every bad host
def pretty_process_board(board, output_dir):
    result, err = process_board(board, output_dir)
    if err is not None:
        print(err)
        return 1
    bad_results = {}
    for k in result:
        if result[k] is not None:
            bad_results[k] = result[k]
    # no bad results --> nothing printed
    for k in bad_result:
        print(k, result[k])
    return len(bad_results)


# accepts: path to output directory
# returns: combined json object, error message (None if no error)
# NOTE: the directory not existing is a fatal error
#       processing a file that is invalid json AFTER the output directory
#       has been validated produces a warning. the invalid json situation
#       should be impossible, but also isn't enough to prevent assemble_output_dir
#       from doing something reasonable.
def assemble_output_dir(output_dir):
    _, err = validate_output(output_dir)
    if err is not None:
        return None, err
    out = []
    items = None
    try:
        items = os.listdir(output_dir)
    except OSError:
        return None, ("directory %s does not exist or is not readable" % output_dir)
    for item in items:
        obj = None
        try:
            with open(os.path.join(output_dir, item), "r") as fh:
                try:
                    obj = json.load(fh)
                except ValueError:
                    warnings.warn("file %s does not contain valid JSON" % item)
                    continue
        except IOError:
            warnings.warn("file %s somehow doesn't exist" % item)
            continue
        out.append(obj)
    return out, None


# accepts: single json dictionary
# returns: error message (None if valid)
def validate_single_dut_json(obj):
    with tempfile.NamedTemporaryFile(delete=True) as fh:
        json.dump(obj, fh)
        flush_sync(fh)
        cmd = VALIDATE_CMD
        cmd = cmd.replace('%%%PATH%%%', pipes.quote(fh.name))
        returncode, out, err = shell_capture_all(cmd)
        if returncode == 0:
            return None
        else:
            return err


# accepts: json obj
# returns: hostname, error message (None if no error)
def get_hostname_from_dut_json(obj):
    try:
        common = obj["common"]
    except KeyError:
        return None, "dut has no common element"
    if not isinstance(common, dict):
        return None, ("common block must be dict not %s" % type(common))
    try:
        return common["hostname"], None
    except KeyError:
        return None, "common block has no hostname element"


# accepts: path to file
# returns: hostname mapping, error message
# hostname mapping has the following form
#
# {
#    hostname -> new_dut_info_json
# }
#
# malformed entries are not included in the map
def load_hostname_map_file(filepath):
    obj = None
    try:
        with open(filepath, "r") as fh:
            try:
                obj = json.load(fh)
            except ValueError:
                return None, ("file does not contain JSON %s" % filepath)
    except IOError:
        return None, ("cannot load hostname map from nonexistent file %s" % filepath)

    out = {}

    # return a singleton map if the toplevel entry is a dictionary
    if isinstance(obj, dict):
        err = validate_single_dut_json(obj)
        if err is not None:
            return None, err
        hostname, err = get_hostname_from_dut_json(obj)
        if err is not None:
            return None, err
        return {hostname: obj}, None

    # validate all elements if the toplevel entry is a list
    elif isinstance(obj, list):
        for subobj in obj:
            err = validate_single_dut_json(subobj)
            if err is not None:
                warnings.warn(err)
                continue
            hostname, err = get_hostname_from_dut_json(subobj)
            if err is not None:
                warnings.warn(err)
                continue
            # warn if we get a duplicate, but don't halt execution
            if hostname in out:
                warnings.warn(("duplicate hostname %s" % hostname))
            out[hostname] = subobj

    if len(out) == 0:
        return out, "out cannot be empty"

    return out, None


# accepts: path to directory
# returns: hostnaming mapping, error message
# hostname mapping has the following form
#
# {
#    hostname -> new_dut_info_json
# }
#
# malformed entries are not included in the map
def load_hostname_map(dirpath):
    items = None
    try:
        items = os.listdir(dirpath)
    except OSError:
        return None, ("cannot load from nonexistent directory %s" % dirpath)
    if len(items) == 0:
        return None, ("nothing in directory %s" % dirpath)
    out = {}
    for item in items:
        hostname_map, err = load_hostname_map_file(os.path.join(dirpath, item))
        if err is not None:
            warnings.warn(err)
            continue

        for hostname in hostname_map:
            if hostname in out:
                warnings.warn("load_hostname_map: duplicate hostname %s" % hostname)
                continue
            out[hostname] = hostname_map[hostname]

    return out, None


# free vars: %%%DIR%%%
QUICK_ADD_DUTS_CMD = r"""
skylab quick-add-duts %%%DIR%%%/*
"""


# accepts: list of hostnames, hostname_dirpath
# returns: error message (None if successful)
# NOTE: the quick-add-duts API is atomic
# emits: missing hostnames when there are missing hostnames
def do_quick_add_duts(hostnames, dirpath):
    # validation
    if isinstance(hostnames, TEXT):
        return "hostnames cannot be %s" % type(hostnames)
    for hostname in hostnames:
        if hostname.startswith("."):
            return "hostname cannot start with '.' (%s)" % hostname
        if not hostname:
            return "hostname cannot be falsey (%s)" % hostname


    hostnames_map, err = load_hostname_map(dirpath)
    if err is not None:
        return err

    # check that every hostname is in the map before trying
    missing_hostnames = set([])
    for hostname in hostnames:
        if hostname not in hostnames_map:
            missing_hostnames.add(hostname)

    if missing_hostnames:
        for hostname in sorted(missing_hostnames):
            print(("MISSING %s" % hostname))
        return "%s missing hostnames" % len(missing_hostnames)

    try:
        # construct temporary directory of dut files.
        tdir = tempfile.mkdtemp()
        for hostname in hostnames:
            newpath = os.path.join(tdir, hostname)
            with open(newpath, "w") as fh:
                json.dump(obj=hostnames_map[hostname], fp=fh)

        # paranoia, check number of files.
        num_files = len(os.listdir(tdir))
        if num_files != len(hostnames):
            return "internal error. hostnames: %s, files: %s, tdir: %s" % (len(hostnames_map), num_files, tdir)

        # validate directory contents before proceeding
        _, err = validate_output(tdir)
        if err is not None:
            return err

        # execute the command, transfer file contents to skylab
        # NOTE: this step is atomic
        # note... skylab quick-add-duts will claim there's no deploy task ID
        # when it is successful
        # we need to parse the output to tell what happened
        #
        # right now, I use the presence of the magic strings 'nothing to commit'
        # and 'missing deploy task ID in request entry' to diagnose what happened
        # but this is fragile.
        cmd = QUICK_ADD_DUTS_CMD
        cmd = cmd.replace('%%%DIR%%%', pipes.quote(tdir))
        returncode, out, err = shell_capture_all(cmd)
        if " nothing to commit" in out:
            warnings.warn("nothing to commit ... no change made to inventory")
            return None
        elif "missing deploy task ID in deploy request entry" in out:
            print("SUCCESS!")
            print(out)
            return None
        else:
            return ("%s\n%s" % (out, err))
    finally:
        print(("path to tempdir: %s" % tdir))
