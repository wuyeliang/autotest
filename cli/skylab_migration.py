#!/usr/bin/env python
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file
from __future__ import unicode_literals
from __future__ import print_function

import collections
import datetime
import io
import os
import subprocess
import tempfile
import time
import sys

import common

_THIS_FILE = os.path.abspath(__file__)
_THIS_DIR = os.path.dirname(_THIS_FILE)

_SKYLAB_EXE = 'skylab'

__all__ = ['migrate', 'setup']

_TEMPPATH = object()

_LITERAL_MAP = {
    'True': True,
    'False': False,
    'None': None,
}


def find_atest_path():
    """Get the path to the 'atest' executable.

    @return : path to 'atest' executable
    """
    atest_exe = os.path.join(_THIS_DIR, 'atest')
    assert os.path.exists(atest_exe)
    return atest_exe


_ATEST_EXE = find_atest_path()


def call_with_tempfile(cmd, lines):
    """Execute command requiring a temporary file and return a CommandOutput struct.

    @param cmd : the components of the argv to be executed.
                 The magical value _TEMPPATH will be replaced with the path
                 to the temporary file.
    @param lines : the lines of content to write to the temporary file

    @returns : CommandOutput struct containing output as list of lines
               and the exit status
    """
    if isinstance(cmd, (str, unicode)):
        raise TypeError('cmd cannot be str or unicode')
    with tempfile.NamedTemporaryFile() as fh:
        for line in lines:
            fh.write(line)
            if line.endswith('\n'):
                pass
            else:
                fh.write('\n')
        fh.close()
        cmd = [(x if x is not _TEMPPATH else fh.name) for x in cmd]
        try:
            output = subprocess.check_output(cmd, stdout=subprocess.PIPE)
            if isinstance(output, (bytes, unicode)):
                output = output.splitlines()
            return CommandOutput(
                exit_code=0, output=[x.decode('utf-8') for x in output])
        except subprocess.CalledProcessError as e:
            return CommandOutput(
                exit_code=e.returncode,
                output=[x.decode('utf-8') for x in output])


CommandOutput = collections.namedtuple('CommandOutput', ['output', 'exit_code'])


def _nontrivially_pairwise_disjoint(*sets):
    """If there are any items present in more than one set, then 'sets' is not pairwise disjoint.

    If there are exactly zero or one sets, then there are no pairs of sets
    and therefore the pairwise disjoint condition will always hold
    regardless of the set contents. Therefore, calling
    _nontrivially_pairwise_disjoint
    with fewer than 2 sets probably indicates a logic error and will result
    in an exception being thrown.

    Example:        [{1}, {2}, set(), {3, 4, 5}, set()]
    CounterExample: [{1, 2}, {2, 3}]

    @param sets: a sequence of sets
    @return: whether the sets are pairwise disjoint
    """
    if len(sets) in (0, 1):
        raise ValueError(
            'a collection of 0 or 1 sets is trivially pairwise disjoint.')
    combined = set()
    sum_len_set = 0
    for set_ in sets:
        combined.update(set_)
        sum_len_set += len(set_)
    assert len(combined) <= sum_len_set
    return len(combined) == sum_len_set


MigrateDutCommandStatus = collections.namedtuple('MigrateDutCommandStatus', [
    'success', 'failure', 'needs_add_to_skylab', 'needs_drone', 'needs_rename'
])

AddToSkylabInventoryAndDroneStatus = collections.namedtuple(
    'AddToSkylabInventoryAndDroneStatus',
    ['complete', 'without_drone', 'not_started'])

RenameCommandStatus = collections.namedtuple('RenameCommandStatus',
                                             ['renamed', 'not_renamed'])

LockCommandStatus = collections.namedtuple('LockCommandStatus',
                                           ['locked', 'not_locked', 'tries'])


class MigrationException(Exception):
    """Raised when migration fails"""
    pass


class AtestCmd(object):
    """Helper functions for executing 'atest' commands"""

    @staticmethod
    def brief_info_cmd():
        """Command line for getting per-host info.

        @return : list of strings to be executed as external command
        """
        return [_ATEST_EXE, 'host', 'list', '--parse', '-M', _TEMPPATH]

    @staticmethod
    def brief_info(hostnames=[]):
        """Run brief info command.

        @return : iterator of dictionaries describing each hostname
        """
        items = call_with_tempfile(AtestCmd.brief_info_cmd(), hostnames).output
        for item in AtestCmd.brief_info_filter(items):
            yield item

    @staticmethod
    def brief_info_filter(stream):
        """Filter lines of output from 'atest host list...'.

        @return : iterator of fields
        """
        for line in stream:
            line = line.rstrip()
            if line:
                fields = line.split('|')
                # if the line of output has exactly zero or one
                # |-delimited sections, then it is not a description
                # of a DUT. Silently discard such lines.
                if len(fields) in (0, 1):
                    continue
                # trim labels entry if it exists
                if fields[-1].startswith('Labels='):
                    fields.pop()
                d = {}
                for f in fields:
                    k, _, v = f.partition('=')
                    # if the value associated with a key is a Python literal
                    # such as True, False, or None, replace it with the
                    # corresponding Python value.
                    # otherwise, use the original string.
                    d[k] = _LITERAL_MAP.get(v, v)
                yield d

    @staticmethod
    def rename_cmd(for_migration=True):
        """Generate command line arguments for 'rename'.

        @return : command line arguments
        """
        name_flag = '--for-migration' if for_migration else '--for-rollback'
        return [
            _ATEST_EXE, 'host', 'rename', '--no-confirmation', name_flag,
            '--parse', '-M', _TEMPPATH
        ]

    @staticmethod
    def rename(hostnames=[], for_migration=True):
        """Rename a list of hosts.

        @return : iterator of successfully renamed hosts
        """
        items = call_with_tempfile(
            AtestCmd.rename_cmd(for_migration=for_migration),
            lines=hostnames).output
        for item in AtestCmd.rename_filter(items):
            yield item

    @staticmethod
    def rename_filter(stream):
        """Process each item of output from `atest host rename...`.

        @return : iterator of successfully renamed hosts
        """
        for item in stream:
            row = [x.strip() for x in item.strip().split()]
            if len(row) == 3:
                src, sep, dest = row
                if sep != 'to':
                    continue
                yield dest

    @staticmethod
    def statjson_cmd(hostname=None):
        """Command line for generating json for hostname.

        @return : command line
        """
        return [_ATEST_EXE, 'host', 'statjson', '--', hostname]

    @staticmethod
    def statjson(hostname=None):
        """Run the command for getting the host json.

        @return : 'atest host statjson' output.
        """
        cmd = AtestCmd.statjson_cmd(hostname=hostname)
        out = subprocess.check_output(cmd)
        return out

    @staticmethod
    def atest_lock_cmd(reason=None):
        """Generate command for 'atest host mod --lock'.

        @return : command line
        """
        return [
            _ATEST_EXE, 'host', 'mod', '--lock', '-r', reason, '-M', _TEMPPATH
        ]

    @staticmethod
    def atest_lock(reason=None, hostnames=[]):
        """Lock hostnames via 'atest host mod --lock'.

        @return : iterator of successfully locked hostnames
        """
        cmd = AtestCmd.atest_lock_cmd(reason=reason)
        items = call_with_tempfile(cmd, hostnames).output
        for item in AtestCmd.atest_lock_filter(items):
            yield item

    @staticmethod
    def atest_lock_filter(stream):
        """Take lines from 'atest host mod --lock' and emit a stream of hostnames.

        The first line "Locked hosts:" is removed. We trim the whitespace of the
        other lines.

        Input:
            Locked Hosts:
                A
                B
                C

        Output:
            A
            B
            C
        """
        for x in stream:
            if x.lower().startswith('locked host'):
                continue
            else:
                yield x.strip()

    @staticmethod
    def atest_unlock_cmd():
        """Generate command for 'atest host mod --unlock'."""
        return [_ATEST_EXE, 'host', 'mod', '--unlock', '-M', _TEMPPATH]

    @staticmethod
    def atest_unlock(reason=None, hostnames=[]):
        """Unlock hostnames via 'atest host mod --unlock'.

        @return : iterator of successfully unlocked hosts
        """
        cmd = AtestCmd.atest_unlock_cmd()
        items = call_with_tempfile(cmd, hostnames).output
        for item in AtestCmd.atest_unlock_filter(items):
            yield item

    @staticmethod
    def atest_unlock_filter(stream):
        """Take lines from 'atest host mod --unlock' and emit a stream of hostnames.

        The first line "Unlocked hosts:" is removed. We trim the whitespace of
        the other lines.

        Input:
            Unlocked Hosts:
                A
                B
                C

        Output:
            A
            B
            C
        """
        for x in stream:
            if x.lower().startswith('unlocked host'):
                continue
            else:
                yield x.strip()


class SkylabCmd(object):
    """Helper functions for executing Skylab commands"""

    @staticmethod
    def add_one_dut_cmd():
        """Create the skylab command line invocation for adding a single DUT."""
        return [
            _SKYLAB_EXE,
            'add-dut',
            '-skip-image-download',
            '-skip-install-firmware',
            '-skip-install-os',
            '-specs-file',
            _TEMPPATH,
        ]

    @staticmethod
    def add_one_dut(add_dut_content):
        """Add one dut to skylab."""
        cmd = SkylabCmd.add_one_dut_cmd()
        return call_with_tempfile(cmd, add_dut_content)

    @staticmethod
    def assign_one_dut_cmd(hostname=None):
        """Command line for assigning a single DUT to a randomly chosen drone."""
        # by default, skylab assign-dut will pick a random drone
        return [_SKYLAB_EXE, 'assign-dut', '--', hostname]

    @staticmethod
    def assign_one_dut(hostname=None):
        """Assign a DUT to a randomly chosen drone."""
        cmd = SkylabCmd.assign_one_dut_cmd(hostname=None)
        try:
            output = subprocess.check_call(cmd)
            return CommandOutput(exit_code=0, output=output)
        except subprocess.CalledProcessError as e:
            return CommandOutput(exit_code=e.returncode, output=e.output)


class Migration(object):

    @staticmethod
    def lock(hostnames=[], reason=None, retries=3):
        """Lock a list of hostnames with retries.


        @return: LockCommandStatus
        """
        to_lock = set(hostnames)
        did_lock = set()
        tries = collections.Counter()
        for _ in range(retries):
            if not to_lock:
                break
            tries.update(to_lock)
            results = AtestCmd.atest_lock(
                hostnames=to_lock.copy(), reason=reason)
            for successfully_locked in results:
                did_lock.add(successfully_locked)
                to_lock.discard(successfully_locked)
        assert to_lock.union(did_lock) == set(hostnames)
        assert len(to_lock.intersection(did_lock)) == 0
        return LockCommandStatus(
            locked=did_lock,
            not_locked=to_lock,
            tries=tries,
        )

    @staticmethod
    def ensure_lock(hostnames=[]):
        """Without changing the state of a DUT, determine which are locked.

        @return : LockCommandStatus
        """
        dut_infos = AtestCmd.brief_info(hostnames=hostnames)
        all_hosts = set(hostnames)
        confirmed_locked = set()
        for dut_info in dut_infos:
            locked = dut_info['Locked']
            assert locked in (True, False)
            if locked:
                confirmed_locked.add(dut_info['Host'])
        return LockCommandStatus(
            locked=confirmed_locked,
            not_locked=(all_hosts - confirmed_locked),
            tries=None,
        )

    @staticmethod
    def rename(hostnames=[], for_migration=True, retries=3):
        """Rename a list of hosts with retry.

        @return : {"renamed": renamed hosts, "not-renamed": not renamed
        hosts}
        """
        all_hosts = set(hostnames)
        needs_rename = all_hosts.copy()
        for _ in range(retries):
            for successfully_renamed in AtestCmd.rename(
                    hostnames=needs_rename.copy(), for_migration=for_migration):
                needs_rename.discard(successfully_renamed)
        return RenameCommandStatus(
            renamed=(all_hosts - needs_rename),
            not_renamed=needs_rename,
        )

    @staticmethod
    def add_to_skylab_inventory_and_drone(hostnames=[], rename_retries=3):
        """@returns : AddToSkylabInventoryAndDroneStatus"""
        all_hosts = set(hostnames)
        moved = set()
        renamed = set()
        for hostname in hostnames:
            skylab_dut_descr = AtestCmd.statjson(hostname=hostname)
            status = SkylabCmd.add_one_dut(add_dut_req_file=skylab_dut_descr)
            if status.exit_code != 0:
                continue
            moved.add(hostname)
            for _ in range(rename_retries):
                status = SkylabCmd.assign_one_dut(hostname=hostname)
                if status.exit_code == 0:
                    renamed.add(hostname)
                    break
        return AddToSkylabInventoryAndDroneStatus(
            complete=renamed,
            without_drone=(moved - renamed),
            not_started=((all_hosts - moved) - renamed),
        )

    @staticmethod
    def migrate_known_good_duts_until_max_duration_sync(
        hostnames=[],
        max_duration=datetime.timedelta(hours=1),
        min_ready_intervals=10,
        interval_len=0):
        """Take a list of DUTs and attempt to migrate them when they aren't busy.

        @param hostnames : list of hostnames
        @param max_duration : when to stop trying to safely migrate duts
        @param atest : path to atest executable
        @param min_ready_intervals : the minimum number of intervals that a DUT
        must have a good status
        @param interval_len : the length in time of an interval (timedelta)
        @param skylab : path to skylab executable

        @returns : {"success": successfuly migrated DUTS, "failure":
        non-migrated DUTS}
        """
        assert interval_len is not None
        start = datetime.datetime.now()
        stop = start + max_duration
        good_intervals = collections.Counter()
        need_to_move = set(hostnames)
        successfully_moved = set()
        needs_add_to_skylab = set()
        needs_drone = set()
        needs_rename = set()
        while datetime.datetime.now() < stop:
            if not need_to_move:
                break
            ready_to_move = set()
            # determine which duts have been in a good state for min_ready_intervals
            for record in AtestCmd.brief_info(hostnames=need_to_move.copy()):
                hostname = record['Host']
                if record['Status'] not in {'Running', 'Provisioning'}:
                    good_intervals[hostname] += 1
                else:
                    del good_intervals[hostname]
                if good_intervals[hostname] >= min_ready_intervals:
                    ready_to_move.add(hostname)
                    need_to_move.discard(hostname)
            # move the ready to move duts now
            # any dut that is declared ready to move at this point will definitely
            # reach a terminal state
            skylab_summary = Migration.add_to_skylab_inventory_and_drone(
                hostnames=ready_to_move)
            needs_add_to_skylab.update(skylab_summary.not_started)
            needs_drone.update(skylab_summary.without_drone)
            # rename the autotest entry all at once
            rename_summary = Migration.rename(
                hostnames=skylab_summary.complete, for_migration=True)
            needs_rename.update(rename_summary.not_renamed)
            successfully_moved.update(rename_summary.renamed)
            time.sleep(interval_len.total_seconds() if interval_len else 0)
        return MigrateDutCommandStatus(
            success=successfully_moved,
            failure=(need_to_move | needs_add_to_skylab | needs_drone
                     | needs_rename),
            needs_add_to_skylab=needs_add_to_skylab,
            needs_drone=needs_drone,
            needs_rename=needs_rename,
        )

    @staticmethod
    def migrate_duts_unconditionally(hostnames):
        """regardless of the DUTs' status, forcibly migrate all the DUTs to skylab.

        @returns: MigrateDutCommandStatus
        """
        successfully_moved = set()
        needs_add_to_skylab = set()
        needs_drone = set()
        needs_rename = set()
        skylab_summary = Migration.add_to_skylab_inventory_and_drone(
            hostnames=hostnames)
        needs_add_to_skylab.update(skylab_summary.not_started)
        needs_drone.update(skylab_summary.without_drone)
        rename_summary = Migration.rename(
            hostnames=skylab_summary.complete, for_migration=True)
        successfully_moved.update(rename_summary.renamed)
        needs_rename.update(rename_summary.not_renamed)
        return MigrateDutCommandStatus(
            success=successfully_moved,
            failure=(needs_drone | needs_rename | needs_add_to_skylab),
            needs_add_to_skylab=needs_add_to_skylab,
            needs_drone=needs_drone,
            needs_rename=needs_rename,
        )

    @staticmethod
    def migrate(hostnames=[],
                reason=None,
                interval=None,
                max_duration=None,
                interval_len=None,
                min_ready_intervals=10):
        """Migrate duts from autotest to skylab.

        @param hostnames : hostnames to migrate
        @param reason : the reason to give for providing the migration
        @param interval : length of time between checks for DUT readiness
        @param max_duration : the grace period to allow DUTs to finish their
        tasks
        @param atest : path to atest command
        @param skylab : path to skylab command
        @param min_ready_intervals : minimum number of intervals before a device
                is healthy

        @return : nothing
        """
        assert reason is not None
        assert interval_len is not None
        all_hosts = tuple(hostnames)
        lock_status = Migration.lock(hostnames=all_hosts, reason=reason)
        if lock_status.not_locked:
            raise MigrationException('failed to lock everything')
        ensure_lock_status = Migration.ensure_lock(hostnames=all_hosts)
        if ensure_lock_status.not_locked:
            raise MigrationException(
                'ensure-lock detected that some duts failed to lock')
        migrate_status = Migration.migrate_known_good_duts_until_max_duration_sync(
            hostnames=hostnames,
            max_duration=max_duration,
            min_ready_intervals=min_ready_intervals,
            interval_len=interval_len)
        unconditionally_migrate_status = Migration.migrate_duts_unconditionally(
            hostnames=migrate_status.failure)
        if unconditionally_migrate_status.failure:
            raise MigrationException('failed to migrate some duts')


migrate = Migration.migrate


def setup(atest_exe=None, skylab_exe=None):
    """Configure the module-scoped path to atest and skylab executables."""
    if atest_exe is not None:
        _ATEST_EXE = atest_exe
    if skylab_exe is not None:
        _SKYLAB_EXE = skylab_exe
