#!/usr/bin/env python2
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file
from __future__ import unicode_literals
from __future__ import print_function

import collections
import datetime
import io
import json
import os
import subprocess
import tempfile
import time
import shutil
import sys
import types

import common

_THIS_FILE = os.path.abspath(__file__)
_THIS_DIR = os.path.dirname(_THIS_FILE)

_SKYLAB_EXE = 'skylab'

__all__ = ['migrate', 'setup']

_TEMPPATH = object()

_FAILED_STEP_SENTINEL = object()

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
    assert not isinstance(lines, (str, unicode))
    with tempfile.NamedTemporaryFile() as fh:
        for line in lines:
            fh.write(line)
            if line.endswith('\n'):
                pass
            else:
                fh.write('\n')
        fh.flush()
        assert os.path.exists(fh.name)
        cmd = [(x if x is not _TEMPPATH else fh.name) for x in cmd]
        try:
            output = subprocess.check_output(cmd)
            if isinstance(output, (bytes, unicode)):
                output = output.splitlines()
            return CommandOutput(
                exit_code=0, output=[x.decode('utf-8') for x in output])
        except subprocess.CalledProcessError as e:
            return CommandOutput(
                exit_code=e.returncode,
                output=[x.decode('utf-8') for x in e.output.splitlines()])


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

MigrationPlan = collections.namedtuple('MigrationPlan', ['transfer', 'retain'])


class MigrationException(Exception):
    """Raised when migration fails"""
    pass


def stderr_log(*args, **kwargs):
    return print(*args, file=sys.stderr, **kwargs)


def _humantime():
    return tuple(datetime.datetime.now().timetuple())[:6]


def _migration_json_summary(failed_step=_FAILED_STEP_SENTINEL,
                            plan=None,
                            not_locked=None,
                            migrate_status=None,
                            unconditionally_migrate_status=None):
    assert isinstance(plan, MigrationPlan)
    assert not isinstance(not_locked, (str, unicode))
    assert isinstance(failed_step, (types.NoneType, unicode))
    assert isinstance(migrate_status, (types.NoneType, MigrateDutCommandStatus))
    assert isinstance(unconditionally_migrate_status, MigrateDutCommandStatus)

    def merge_attrs(fieldname, struct1, struct2=None):
        merged = set()
        if struct1:
            merged.update(getattr(struct1, fieldname))
        if struct2:
            merged.update(getattr(struct2, fieldname))
        return sorted(merged)


    out = {
        'locked_success': (failed_step is None),
        'failed_step': failed_step,
        'plan': {
            'transfer': merge_attrs('transfer', plan),
            'retain': merge_attrs('retain', plan),
        },
        'duts': {
            'migrated':
                merge_attrs('success', migrate_status, unconditionally_migrate_status),
            'not_locked':
                list(sorted(set(not_locked))),
            'needs_add_to_skylab':
                merge_attrs('needs_add_to_skylab', migrate_status, unconditionally_migrate_status),
            'needs_drone':
                merge_attrs('needs_drone', migrate_status, unconditionally_migrate_status),
            'needs_rename':
                merge_attrs('needs_rename', migrate_status, unconditionally_migrate_status),
        }
    }
    return out


class AtestCmd(object):
    """Helper functions for executing 'atest' commands"""

    @staticmethod
    def brief_info_cmd():
        """Command line for getting per-host info.

        @return : list of strings to be executed as external command
        """
        return [_ATEST_EXE, 'host', 'list', '--parse', '-M', _TEMPPATH]

    @staticmethod
    def brief_info(hostnames=None):
        """Run brief info command.

        @return : iterator of dictionaries describing each hostname
        """
        hostnames = hostnames or set()
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
            _ATEST_EXE, 'host', 'rename', '--non-interactive', name_flag,
            '--parse', '-M', _TEMPPATH
        ]

    @staticmethod
    def rename(hostnames=None, for_migration=True):
        """Rename a list of hosts.

        @return : iterator of successfully renamed hosts
        """
        hostnames = hostnames or set()
        stderr_log('begin rename', time.time(), _humantime())
        items = call_with_tempfile(
            AtestCmd.rename_cmd(for_migration=for_migration),
            lines=hostnames).output
        out = list(AtestCmd.rename_filter(items))
        stderr_log('end rename', time.time(), _humantime())
        return out

    @staticmethod
    def rename_filter(stream):
        """Process each item of output from `atest host rename...`.

        @return : iterator of successfully renamed hosts
        """
        for item in stream:
            row = [x.strip() for x in item.strip().split()]
            if len(row) == 3:
                src, sep, dest = row
                # dest has the 'migrated-do-not-use' suffix
                # use src!
                if sep != 'to':
                    continue
                yield src

    @staticmethod
    def statjson_cmd(hostname=None):
        """Command line for generating json for hostname.

        @return : command line
        """
        return [_ATEST_EXE, 'host', 'statjson', '--', hostname]

    @staticmethod
    def statjson(hostname=None):
        """Run the command for getting the host json.

        @return : 'atest host statjson' output as parsed json.
        """
        cmd = AtestCmd.statjson_cmd(hostname=hostname)
        out = subprocess.check_output(cmd)
        return json.loads(out.decode('utf-8'))

    @staticmethod
    def atest_lock_cmd(reason=None):
        """Generate command for 'atest host mod --lock'.

        @return : command line
        """
        return [
            _ATEST_EXE, 'host', 'mod', '--lock', '-r', reason, '-M', _TEMPPATH
        ]

    @staticmethod
    def atest_lock(reason=None, hostnames=None):
        """Try to lock hostnames via 'atest host mod --lock'.

        @return : Nothing
        """
        hostnames = hostnames or set()
        assert isinstance(reason, unicode)
        cmd = AtestCmd.atest_lock_cmd(reason=reason)
        # NOTE: attempting to lock a host can fail because the host
        # is already locked. Therefore, atest_lock always succeeds
        # regardless of the exit status of the command.
        call_with_tempfile(cmd, hostnames)

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
    def atest_unlock(reason=None, hostnames=None):
        """Unlock hostnames via 'atest host mod --unlock'.

        @return : iterator of successfully unlocked hosts
        """
        hostnames = hostnames or set()
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

    @staticmethod
    def atest_get_migration_plan_cmd(ratio):
        """Generate command for 'atest host get_migration_plan --mlist ...'"""
        return [
            _ATEST_EXE, 'host', 'get_migration_plan', '--ratio',
            unicode(ratio), '--mlist', _TEMPPATH
        ]

    @staticmethod
    def atest_get_migration_plan(ratio, hostnames=[]):
        cmd = AtestCmd.atest_get_migration_plan_cmd(ratio)
        output = call_with_tempfile(cmd, hostnames).output
        out = json.loads(''.join(output))
        return out


class SkylabCmd(object):
    """Helper functions for executing Skylab commands"""

    ADD_MANY_DUTS_CMD = (_SKYLAB_EXE, 'quick-add-duts')

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
        stderr_log('begin add_one_dut', time.time(), _humantime())
        cmd = SkylabCmd.add_one_dut_cmd()
        out = call_with_tempfile(cmd, [json.dumps(add_dut_content)])
        stderr_log('end add_one_dut', time.time(), _humantime())
        return out

    @staticmethod
    def assign_one_dut_cmd(hostname=None):
        """Command line for assigning a single DUT to a randomly chosen drone."""
        # by default, skylab assign-dut will pick a random drone
        return [_SKYLAB_EXE, 'assign-dut', '--', hostname]

    @staticmethod
    def add_many_duts(dut_contents):
        """Add multiple DUTs to skylab at once.

        @param dut_contents: a sequence of JSON-like objects describing DUTs as
                             used by `skylab add-dut` and `skylab quick-add-dut`

        @returns : nothing
        """
        # TODO(gregorynisbet) -- how fine-grained does the error reporting need
        #                        to be? is it possible for some duts to be
        #                        successfully migrated and others not?
        #                        The action performed by `skylab quick-add-duts`
        #                        is idempotent, so trying multiple times is not
        #                        necessarily a problem.
        td = tempfile.mkdtemp()
        try:
            paths = []
            for i, dut_content in enumerate(dut_contents):
                path_ = os.path.join(td, str(i))
                with open(path_, 'w') as fh:
                    json.dump(dut_contents, fh)
                paths.append(path_)
            cmd = list(SkylabCmd.ADD_MANY_DUTS_CMD) + paths
            subprocess.call(cmd)
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @staticmethod
    def assign_one_dut(hostname=None):
        """Assign a DUT to a randomly chosen drone."""
        assert isinstance(hostname, unicode)
        cmd = SkylabCmd.assign_one_dut_cmd(hostname=hostname)
        # run command capturing stdout and stderr regardless of exit status
        def run(cmd):
            try:
                return [0, subprocess.check_output(cmd, stderr=subprocess.STDOUT)]
            except subprocess.CalledProcessError as e:
                return [e.returncode, e.output]
        # NOTE: we need to look at the output of the wrapped command
        # in order to determine whether the failure is due to a drone
        # already having been assigned or not.
        # If the DUT in question is already assigned to a drone,
        # then we report success to our caller.
        exit_code, output = run(cmd)
        # the skylab command does not use a dedicated error status for
        # failure due to the DUT already being assigned to a drone.
        # In order to determine whether this happened, we look for a string
        # in the output. The output contains some JSON and a preamble, so
        # we can't parse the output since it isn't pure JSON.
        already_present = ' is already assigned to drone ' in output
        if already_present:
            return CommandOutput(exit_code=0, output=output)
        else:
            return CommandOutput(exit_code=e.returncode, output=output)


class Migration(object):

    @staticmethod
    def migration_plan(ratio, hostnames=None):
        hostnames = hostnames or set()
        plan = AtestCmd.atest_get_migration_plan(
            ratio=ratio, hostnames=hostnames)
        return MigrationPlan(transfer=plan['transfer'], retain=plan['retain'])

    @staticmethod
    def lock(hostnames=None, reason=None, retries=3):
        """Lock a list of hostnames with retries.
        """
        hostnames = hostnames or set()
        assert isinstance(reason, unicode)
        to_lock = set(hostnames)
        for _ in range(retries):
            AtestCmd.atest_lock(hostnames=to_lock.copy(), reason=reason)

    @staticmethod
    def ensure_lock(hostnames=None):
        """Without changing the state of a DUT, determine which are locked.

        @return : LockCommandStatus
        """
        hostnames = hostnames or set()
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
    def rename(hostnames=None, for_migration=True, retries=1):
        """Rename a list of hosts with retry.

        @return : {"renamed": renamed hosts, "not-renamed": not renamed
        hosts}
        """
        hostnames = hostnames or set()
        all_hosts = set(hostnames)
        needs_rename = all_hosts.copy()
        for _ in range(retries):
            for successfully_renamed in AtestCmd.rename(
                    hostnames=needs_rename.copy(), for_migration=for_migration):
                needs_rename.discard(successfully_renamed)
        out = RenameCommandStatus(
            renamed=(all_hosts - needs_rename),
            not_renamed=needs_rename,
        )
        return out

    @staticmethod
    def add_to_skylab_inventory_and_drone(hostnames=None, rename_retries=3):
        """@returns : AddToSkylabInventoryAndDroneStatus"""
        hostnames = hostnames or set()
        assert not isinstance(hostnames, (unicode, bytes))
        stderr_log('begin add hostnames to inventory', time.time(),
                   _humantime())
        all_hosts = set(hostnames)
        moved = set()
        renamed = set()
        for hostname in hostnames:
            skylab_dut_descr = AtestCmd.statjson(hostname=hostname)
            status = SkylabCmd.add_one_dut(add_dut_content=skylab_dut_descr)
            if status.exit_code != 0:
                continue
            moved.add(hostname)
            for _ in range(rename_retries):
                status = SkylabCmd.assign_one_dut(hostname=hostname)
                if status.exit_code == 0:
                    renamed.add(hostname)
                    break
        out = AddToSkylabInventoryAndDroneStatus(
            complete=renamed,
            without_drone=(moved - renamed),
            not_started=((all_hosts - moved) - renamed),
        )
        stderr_log('end add hostnames to inventory', time.time(), _humantime())
        return out

    @staticmethod
    def migrate_known_good_duts_until_max_duration_sync(hostnames=None,
                                                        max_duration=60 * 60,
                                                        min_ready_intervals=10,
                                                        interval_len=0):
        """Take a list of DUTs and attempt to migrate them when they aren't busy.

        @param hostnames : list of hostnames
        @param max_duration : when to stop trying to safely migrate duts
        @param atest : path to atest executable
        @param min_ready_intervals : the minimum number of intervals that a DUT
        must have a good status
        @param interval_len : the length in seconds of interval
        @param skylab : path to skylab executable

        @returns : {"success": successfuly migrated DUTS, "failure":
        non-migrated DUTS}
        """
        hostnames = hostnames or set()
        assert interval_len is not None
        stderr_log('begin migrating only ready DUTs', time.time(), _humantime())
        start = time.time()
        stop = start + max_duration
        good_intervals = collections.Counter()
        need_to_move = set(hostnames)
        successfully_moved = set()
        needs_add_to_skylab = set()
        needs_drone = set()
        needs_rename = set()
        while time.time() < stop:
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
            time.sleep(interval_len)
        out = MigrateDutCommandStatus(
            success=successfully_moved,
            failure=(need_to_move | needs_add_to_skylab | needs_drone
                     | needs_rename),
            needs_add_to_skylab=needs_add_to_skylab,
            needs_drone=needs_drone,
            needs_rename=needs_rename,
        )
        stderr_log('end migrating only ready DUTs', time.time(), _humantime())
        return out

    @staticmethod
    def migrate_duts_unconditionally(hostnames):
        """regardless of the DUTs' status, forcibly migrate all the DUTs to skylab.

        @returns: MigrateDutCommandStatus
        """
        assert not isinstance(hostnames, (unicode, bytes))
        stderr_log('begin unconditional migration', time.time(), _humantime())
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
        needs_rename.discard(rename_summary.not_renamed)
        out = MigrateDutCommandStatus(
            success=successfully_moved,
            failure=(needs_drone | needs_rename | needs_add_to_skylab),
            needs_add_to_skylab=needs_add_to_skylab,
            needs_drone=needs_drone,
            needs_rename=needs_rename,
        )
        stderr_log('end unconditional migration', time.time(), _humantime())
        return out

    @staticmethod
    def migrate(hostnames=None,
                ratio=1,
                reason=None,
                max_duration=None,
                interval_len=None,
                min_ready_intervals=10,
                immediately=None):
        """Migrate duts from autotest to skylab.

        @param ratio : ratio of DUTs in hostnames to migrate.
        @param hostnames : hostnames to migrate
        @param reason : the reason to give for providing the migration
        @param interval_len : length of time between checks for DUT readiness
        @param max_duration : the grace period to allow DUTs to finish their
        tasks
        @param min_ready_intervals : minimum number of intervals before a device
                is healthy

        @return : nothing
        """
        hostnames = hostnames or set()
        assert isinstance(reason, (unicode, bytes))
        assert interval_len is not None
        assert max_duration is not None
        assert immediately is not None
        reason = reason if isinstance(reason,
                                      unicode) else reason.decode('utf-8')
        # log the parameters of the migration
        stderr_log('begin migrate', time.time(), _humantime())
        stderr_log('number of hostnames', len(hostnames), time.time(), _humantime())
        stderr_log('ratio', ratio, time.time(), _humantime())
        stderr_log('max_duration', max_duration, time.time(), _humantime())
        stderr_log('atest', _ATEST_EXE, time.time(), _humantime())
        stderr_log('skylab', _SKYLAB_EXE, time.time(), _humantime())
        stderr_log('minimum number of intervals', min_ready_intervals, time.time(), _humantime())
        stderr_log('immediately', immediately, time.time(), _humantime())
        all_hosts = tuple(hostnames)
        plan = Migration.migration_plan(ratio=ratio, hostnames=all_hosts)
        Migration.lock(hostnames=plan.transfer, reason=reason)
        failed_step = _FAILED_STEP_SENTINEL
        ensure_lock_status = Migration.ensure_lock(hostnames=plan.transfer)
        if ensure_lock_status.not_locked:
            failed_step = 'lock'
        to_migrate = plan.transfer
        migrate_status = None
        if not immediately:
            migrate_status = Migration.migrate_known_good_duts_until_max_duration_sync(
                hostnames=to_migrate,
                max_duration=max_duration,
                min_ready_intervals=min_ready_intervals,
                interval_len=interval_len)
            to_migrate = migrate_status.failure
        unconditionally_migrate_status = Migration.migrate_duts_unconditionally(
            hostnames=to_migrate)
        failed_step = None
        out = _migration_json_summary(
            failed_step=failed_step,
            plan=plan,
            not_locked=ensure_lock_status.not_locked,
            migrate_status=migrate_status,
            unconditionally_migrate_status=unconditionally_migrate_status,
        )
        stderr_log('end migrate', time.time(), _humantime())
        return out


migrate = Migration.migrate


def setup(atest_exe=None, skylab_exe=None):
    """Configure the module-scoped path to atest and skylab executables."""
    if atest_exe is not None:
        _ATEST_EXE = atest_exe
    if skylab_exe is not None:
        _SKYLAB_EXE = skylab_exe
