#!/usr/bin/python2
# pylint: disable-msg=C0111
#
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file
"""Test for skylab migration unittest."""

from __future__ import unicode_literals
from __future__ import print_function

import copy
import json
import os.path
import subprocess
import tempfile
import unittest
import shutil

import mock

import common
from autotest_lib.cli import skylab_migration


class ExecuteWithTempfileUnittest(unittest.TestCase):

    def test_call_with_tempfile(self):
        with mock.patch('subprocess.check_output') as check_output:
            check_output.return_value = b'\n'.join([b'x', b'y', b'z'])
            commandOutput = skylab_migration.call_with_tempfile([], [])
            self.assertEqual(commandOutput.output, ['x', 'y', 'z'])

    def test_call_with_tempfile_real(self):
        commandOutput = skylab_migration.call_with_tempfile(
            ['/bin/cat', skylab_migration._TEMPPATH], ['a', 'b', 'c'])
        self.assertEqual(commandOutput.output, ['a', 'b', 'c'])


class MigrationUnittest(unittest.TestCase):

    def setUp(self):
        super(MigrationUnittest, self).setUp()
        self._tempdir = tempfile.mkdtemp()

        def do_nothing(*args, **kwargs):
            pass

        self.__patches = {
            'call_with_tempfile':
                mock.patch.object(
                    skylab_migration, 'call_with_tempfile', new=None),
            'popen':
                mock.patch('subprocess.Popen', new=None),
            'check_call':
                mock.patch.object(subprocess, 'check_call', new=None),
            'call':
                mock.patch.object(subprocess, 'call', new=None),
            'check_output':
                mock.patch.object(subprocess, 'check_output', new=None),
            'mkdtemp':
                mock.patch.object(tempfile, 'mkdtemp', new=None),
            'mkstemp':
                mock.patch.object(tempfile, 'mkstemp', new=None),
            'NamedTemporaryFile':
                mock.patch('tempfile.NamedTemporaryFile', new=None),
            'stderr_log':
                mock.patch.object(
                    skylab_migration, 'stderr_log', new=do_nothing)
        }
        for x in self.__patches.values():
            x.start()

    def tearDown(self):
        for x in self.__patches.values():
            x.stop()
        shutil.rmtree(self._tempdir, ignore_errors=True)
        super(MigrationUnittest, self).tearDown()

    def test_find_atest(self):
        atest_exe = skylab_migration.find_atest_path()
        self.assertTrue(os.path.exists(atest_exe))

    def test_brief_info_cmd(self):
        return self.assertEqual(skylab_migration.AtestCmd.brief_info_cmd()[:-1],
                                [skylab_migration._ATEST_EXE] +
                                'host list --parse -M'.split())

    def test_brief_info(self):
        with mock.patch.object(skylab_migration, 'call_with_tempfile') as call_:
            call_.return_value = skylab_migration.CommandOutput(
                exit_code=0,
                output=[
                    'key1=a|Labels=x', 'key1=b|Labels=y', 'key1=c|Labels=z'
                ])
            items = list(
                skylab_migration.AtestCmd.brief_info(hostnames=['a', 'b', 'c']))
            self.assertEqual(items, [
                {
                    'key1': 'a'
                },
                {
                    'key1': 'b'
                },
                {
                    'key1': 'c'
                },
            ])

    def test_rename_cmd_for_migration(self):
        cmd = skylab_migration.AtestCmd.rename_cmd(for_migration=True)
        self.assertEqual(cmd, [
            skylab_migration._ATEST_EXE,
            'host',
            'rename',
            '--non-interactive',
            '--for-migration',
            '--parse',
            '-M',
            skylab_migration._TEMPPATH,
        ])

    def test_rename_cmd_for_rollback(self):
        cmd = skylab_migration.AtestCmd.rename_cmd(for_migration=False)
        self.assertEqual(cmd, [
            skylab_migration._ATEST_EXE,
            'host',
            'rename',
            '--non-interactive',
            '--for-rollback',
            '--parse',
            '-M',
            skylab_migration._TEMPPATH,
        ])

    def test_rename_filter(self):
        expected = ['10', '20']
        actual = list(
            skylab_migration.AtestCmd.rename_filter(['10 to 1', '20 to 2']))
        self.assertEqual(expected, actual)

    def test_rename(self):
        with mock.patch.object(skylab_migration, 'call_with_tempfile') as call_:
            output = skylab_migration.CommandOutput(
                exit_code=0,
                output=[
                    'a to a.suffix', 'b to b.suffix', 'c to c.suffix',
                    'd to d.suffix'
                ])
            expected = ['a', 'b', 'c', 'd']
            call_.return_value = output
            actual = list(skylab_migration.AtestCmd.rename(hostnames=[]))
            self.assertEqual(expected, actual)

    def test_statjson_cmd(self):
        self.assertEqual(
            skylab_migration.AtestCmd.statjson_cmd(hostname='H'),
            [skylab_migration._ATEST_EXE, 'host', 'statjson', '--', 'H'])

    def test_statjson(self):
        with mock.patch.object(subprocess, 'check_output') as check_output:
            check_output.return_value = '[]'
            obj = skylab_migration.AtestCmd.statjson(None)
            self.assertEqual(obj, [])

    def test_atest_lock_cmd(self):
        self.assertEqual(
            skylab_migration.AtestCmd.atest_lock_cmd(reason='R'), [
                skylab_migration._ATEST_EXE, 'host', 'mod', '--lock', '-r', 'R',
                '-M', skylab_migration._TEMPPATH
            ])

    def test_atest_lock(self):
        # just check that traversing the body of atest_lock doesn't throw an exception
        with mock.patch.object(skylab_migration, 'call_with_tempfile') as call_:
            call_.return_value = skylab_migration.CommandOutput(
                exit_code=0, output=['a', 'b'])

    def test_atest_unlock_cmd(self):
        self.assertEqual(skylab_migration.AtestCmd.atest_unlock_cmd(), [
            skylab_migration._ATEST_EXE, 'host', 'mod', '--unlock', '-M',
            skylab_migration._TEMPPATH
        ])

    def test_atest_unlock(self):
        with mock.patch.object(skylab_migration.AtestCmd,
                               'atest_unlock') as atest_unlock:
            atest_unlock.return_value = ['a', 'b']
            expected = ['a', 'b']
            actual = list(
                skylab_migration.AtestCmd.atest_unlock(hostnames=['a', 'b']))
            self.assertEqual(expected, actual)

    def test_add_one_dut_cmd(self):
        expected = [
            skylab_migration._SKYLAB_EXE, 'add-dut', '-skip-image-download',
            '-skip-install-firmware', '-skip-install-os', '-specs-file',
            skylab_migration._TEMPPATH
        ]
        actual = skylab_migration.SkylabCmd.add_one_dut_cmd()
        self.assertEqual(expected, actual)

    def test_add_many_duts(self):
        def mkdtemp_impl(*args, **kwargs):
            return self._tempdir

        def call_impl(cmd, stderr=None):
            self.assertEqual(cmd, [
                skylab_migration._SKYLAB_EXE, 'quick-add-duts',
                os.path.join(self._tempdir, '0'),
                os.path.join(self._tempdir, '1'),
                os.path.join(self._tempdir, '2'),
                os.path.join(self._tempdir, '3')
            ])

        with mock.patch.object(tempfile, 'mkdtemp', new=mkdtemp_impl):
            with mock.patch.object(subprocess, 'call', new=call_impl):
                with mock.patch.object(subprocess, 'check_call', new=call_impl):
                    with mock.patch.object(subprocess, 'check_output', new=call_impl):
                        skylab_migration.SkylabCmd.add_many_duts(
                            [None, None, None, None])

    def test_atest_get_migration_plan_cmd(self):
        expected = [
            skylab_migration._ATEST_EXE, 'host', 'get_migration_plan',
            '--ratio', '0.1', '--mlist', skylab_migration._TEMPPATH
        ]
        actual = skylab_migration.AtestCmd.atest_get_migration_plan_cmd(
            ratio=0.1)
        self.assertEqual(expected, actual)

    def test_atest_get_migration_plan(self):
        with mock.patch.object(skylab_migration,
                               'call_with_tempfile') as call_with_tempfile:
            call_with_tempfile.return_value = skylab_migration.CommandOutput(
                exit_code=0,
                output=[json.dumps({
                    'transfer': [],
                    'retain': []
                })])
            out = skylab_migration.AtestCmd.atest_get_migration_plan(
                ratio=0.4, hostnames=[])
            self.assertEqual(out['transfer'], [])
            self.assertEqual(out['retain'], [])

    def test_lock_smoke_test(self):
        # just make sure Migration.lock doesn't throw an exception
        with mock.patch.object(skylab_migration, 'call_with_tempfile') as call_:
            call_.return_value = skylab_migration.CommandOutput(
                exit_code=0, output=['a', 'b'])
            skylab_migration.Migration.lock(
                hostnames=[], reason='reason', retries=3)

    def test_lock_single_host(self):
        pass
        # def atest_lock(hostnames=[], **kwargs):
        #     """successfully lock every hostname"""
        #     for item in hostnames:
        #         yield item

        # with mock.patch.object(skylab_migration, 'AtestCmd') as atest_cmd:
        #     atest_cmd.atest_lock = atest_lock
        #     summary = skylab_migration.Migration.lock(
        #         hostnames=['HHH'], reason=None, retries=1)
        #     self.assertEqual(summary.locked, {'HHH'})
        #     self.assertEqual(summary.not_locked, set())
        #     self.assertEqual(list(summary.tries), ['HHH'])

    def test_lock_one_good_one_bad(self):
        # TODO(gregorynisbet): effectively just a smoke test
        def atest_lock(hostnames=[], **kwargs):
            return Nothing

        with mock.patch.object(skylab_migration, 'AtestCmd') as atest_cmd:
            atest_cmd.atest_lock = atest_lock

    def test_ensure_lock_smoke_test(self):

        def brief_info(hostnames=[], **kwargs):
            if False:
                yield 42

        with mock.patch.object(skylab_migration, 'AtestCmd') as atest_cmd:
            atest_cmd.brief_info = brief_info
            summary = skylab_migration.Migration.ensure_lock(hostnames=[])
            self.assertEqual(summary.locked, set())
            self.assertEqual(summary.not_locked, set())

    def test_ensure_lock_one_good_one_bad(self):

        def brief_info(**kwargs):
            yield {'Host': 'a', 'Locked': True}
            yield {'Host': 'b', 'Locked': False}

        with mock.patch.object(skylab_migration, 'AtestCmd') as atest_cmd:
            atest_cmd.brief_info = brief_info
            summary = skylab_migration.Migration.ensure_lock(
                hostnames=['a', 'b'])
            self.assertEqual(summary.locked, {'a'})
            self.assertEqual(summary.not_locked, {'b'})

    def test_rename_smoke_test(self):

        def atest_cmd_rename(**kwargs):
            if False:
                yield 42

        with mock.patch.object(skylab_migration, 'AtestCmd') as atest_cmd:
            atest_cmd.rename = atest_cmd_rename
            summary = skylab_migration.Migration.rename(hostnames=[])
            self.assertEqual(summary.renamed, set())
            self.assertEqual(summary.not_renamed, set())

    def test_rename_one_good_one_bad(self):

        def atest_cmd_rename(**kwargs):
            yield 'GOOD'

        with mock.patch.object(skylab_migration, 'AtestCmd') as atest_cmd:
            atest_cmd.rename = atest_cmd_rename
            summary = skylab_migration.Migration.rename(
                hostnames=['GOOD', 'BAD'])
            self.assertEqual(summary.renamed, set(['GOOD']))
            self.assertEqual(summary.not_renamed, set(['BAD']))

    def test_add_to_skylab_inventory_and_drone_smoke_test(self):
        summary = skylab_migration.Migration.add_to_skylab_inventory_and_drone(
            hostnames=[],
            use_quick_add=False)
        self.assertEqual(summary.complete, set())
        self.assertEqual(summary.without_drone, set())
        self.assertEqual(summary.not_started, set())

    def test_add_to_skylab_inventory_and_drone_one_of_each(self):

        @staticmethod
        def atest_statjson(hostname=None):
            return hostname

        @staticmethod
        def add_one_dut(add_dut_content=None):
            if add_dut_content in ('GOOD', 'MEDIUM'):
                return skylab_migration.CommandOutput(output=[], exit_code=0)
            else:
                return skylab_migration.CommandOutput(output=[], exit_code=1)

        @staticmethod
        def assign_one_dut(hostname=None):
            if hostname == 'GOOD':
                return skylab_migration.CommandOutput(output=[], exit_code=0)
            else:
                return skylab_migration.CommandOutput(output=[], exit_code=1)

        with mock.patch.object(
                skylab_migration.AtestCmd, 'statjson', new=atest_statjson):
            with mock.patch.object(
                    skylab_migration.SkylabCmd, 'add_one_dut', new=add_one_dut):
                summary = skylab_migration.Migration.add_to_skylab_inventory_and_drone(
                    use_quick_add=False,
                    hostnames=['GOOD', 'MEDIUM', 'BAD'])
                self.assertEqual(summary.complete, {'GOOD', 'MEDIUM'})
                self.assertEqual(summary.not_started, {'BAD'})

    def test_migrate_known_good_duts_until_max_duration_sync_smoke_test(self):

        def brief_info(**kwargs):
            if False:
                yield 42

        def rename(**kwargs):
            if False:
                yield 42

        with mock.patch.object(skylab_migration, 'AtestCmd') as atest_cmd:
            atest_cmd.brief_info = brief_info
            atest_cmd.rename = rename
            summary = skylab_migration.Migration.migrate_known_good_duts_until_max_duration_sync(
                use_quick_add=False,
                hostnames=[])
            self.assertEqual(summary.success, set())
            self.assertEqual(summary.failure, set())

    def test_migrate_known_good_duts_until_max_duration_one_good_one_bad(self):

        def brief_info(**kwargs):
            return [
                {
                    'Host': 'GOOD',
                    'Status': 'Ready'
                },
                {
                    'Host': 'BAD',
                    'Status': 'Ready'
                },
            ]

        inventory_return = skylab_migration.AddToSkylabInventoryAndDroneStatus(
            complete=['GOOD', 'BAD'],
            not_started=[],
            without_drone=[],
        )

        def atest_cmd_rename(hostname=None, **kwargs):
            yield 'GOOD'

        with mock.patch.object(skylab_migration, 'AtestCmd') as atest_cmd:
            atest_cmd.brief_info = brief_info
            atest_cmd.rename = atest_cmd_rename
            with mock.patch.object(skylab_migration, 'SkylabCmd') as skylab_cmd:
                with mock.patch.object(skylab_migration.Migration,
                                       'add_to_skylab_inventory_and_drone'
                                      ) as add_to_skylab_obj:
                    add_to_skylab_obj.return_value = inventory_return
                    summary = skylab_migration.Migration.migrate_known_good_duts_until_max_duration_sync(
                        use_quick_add=False,
                        hostnames=['GOOD', 'BAD'])
                    self.assertEqual(summary.success, set(['GOOD']))
                    self.assertEqual(summary.failure, set(['BAD']))
                    self.assertEqual(summary.needs_add_to_skylab, set())
                    self.assertEqual(summary.needs_drone, set())
                    self.assertEqual(summary.needs_rename, set(['BAD']))
                    add_to_skylab_obj.assert_called()

    def test_migrate_duts_unconditionally_smoke_test(self):

        def brief_info(**kwargs):
            if False:
                yield 42

        def rename(**kwargs):
            if False:
                yield 42

        with mock.patch.object(skylab_migration, 'AtestCmd') as atest_cmd:
            atest_cmd.brief_info = brief_info
            atest_cmd.rename = rename
            summary = skylab_migration.Migration.migrate_duts_unconditionally(
                use_quick_add=False,
                hostnames=[])
            self.assertEqual(summary.success, set())
            self.assertEqual(summary.failure, set())

    def test_migrate_duts_unconditionally_one_good_one_bad(self):

        def brief_info(**kwargs):
            return [
                {
                    'Host': 'GOOD',
                    'Status': 'Ready'
                },
                {
                    'Host': 'BAD',
                    'Status': 'Ready'
                },
            ]

        inventory_retval = skylab_migration.AddToSkylabInventoryAndDroneStatus(
            complete=['GOOD', 'BAD'],
            not_started=[],
            without_drone=[],
        )

        def atest_cmd_rename(hostname=None, **kwargs):
            yield 'GOOD'

        with mock.patch.object(skylab_migration, 'AtestCmd') as atest_cmd:
            atest_cmd.brief_info = brief_info
            atest_cmd.rename = atest_cmd_rename
            with mock.patch.object(skylab_migration, 'SkylabCmd') as skylab_cmd:
                with mock.patch.object(skylab_migration.Migration,
                                       'add_to_skylab_inventory_and_drone'
                                      ) as add_to_skylab_obj:
                    add_to_skylab_obj.return_value = inventory_retval
                    summary = skylab_migration.Migration.migrate_duts_unconditionally(
                        use_quick_add=False,
                        hostnames=['GOOD', 'BAD'])
                    self.assertEqual(summary.success, set(['GOOD']))
                    self.assertEqual(summary.failure, set(['BAD']))

    @mock.patch.object(skylab_migration.Migration, 'migration_plan')
    @mock.patch.object(skylab_migration.Migration,
                       'migrate_known_good_duts_until_max_duration_sync')
    @mock.patch.object(skylab_migration.Migration,
                       'migrate_duts_unconditionally')
    @mock.patch.object(skylab_migration.Migration, 'ensure_lock')
    @mock.patch.object(skylab_migration.Migration, 'lock')
    def test_migrate_smoke_test(self, lock, ensure_lock,
                                migrate_duts_unconditionally, known_good,
                                migration_plan):
        lock.return_value = skylab_migration.LockCommandStatus(
            locked=[], not_locked=[], tries=None)
        ensure_lock.return_value = skylab_migration.LockCommandStatus(
            locked=[], not_locked=[], tries=None)
        known_good.return_value = migrate_duts_unconditionally.return_value = skylab_migration.MigrateDutCommandStatus(
            success=[],
            failure=[],
            needs_add_to_skylab=[],
            needs_drone=[],
            needs_rename=[])
        migration_plan.return_value = skylab_migration.MigrationPlan(
            transfer=[], retain=[])
        skylab_migration.Migration.migrate(
            hostnames=[],
            reason='test',
            interval_len=0,
            max_duration=10,
            immediately=True)


if __name__ == '__main__':
    unittest.main()
