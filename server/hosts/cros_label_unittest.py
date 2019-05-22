#!/usr/bin/python
# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import common

from autotest_lib.server import utils
from autotest_lib.server.hosts.cros_label import BoardLabel
from autotest_lib.server.hosts.cros_label import BluetoothLabel
from autotest_lib.server.hosts.cros_label import Cr50Label
from autotest_lib.server.hosts.cros_label import ModelLabel
from autotest_lib.server.hosts import host_info

# pylint: disable=missing-docstring

NON_UNI_LSB_RELEASE_OUTPUT = """
CHROMEOS_RELEASE_APPID={63A9F698-C1CA-4A75-95E7-6B90181B3718}
CHROMEOS_BOARD_APPID={63A9F698-C1CA-4A75-95E7-6B90181B3718}
CHROMEOS_CANARY_APPID={90F229CE-83E2-4FAF-8479-E368A34938B1}
DEVICETYPE=CHROMEBOOK
CHROMEOS_ARC_VERSION=4234098
CHROMEOS_ARC_ANDROID_SDK_VERSION=25
GOOGLE_RELEASE=9798.0.2017_08_02_1022
CHROMEOS_DEVSERVER=http://shapiroc3.bld.corp.google.com:8080
CHROMEOS_RELEASE_BOARD=pyro
CHROMEOS_RELEASE_BUILD_NUMBER=9798
CHROMEOS_RELEASE_BRANCH_NUMBER=0
CHROMEOS_RELEASE_CHROME_MILESTONE=62
CHROMEOS_RELEASE_PATCH_NUMBER=2017_08_02_1022
CHROMEOS_RELEASE_TRACK=testimage-channel
CHROMEOS_RELEASE_DESCRIPTION=9798.0.2017_08_02_1022 (Test Build)
CHROMEOS_RELEASE_BUILD_TYPE=Test Build
CHROMEOS_RELEASE_NAME=Chromium OS
CHROMEOS_RELEASE_VERSION=9798.0.2017_08_02_1022
CHROMEOS_AUSERVER=http://someserver.bld.corp.google.com:8080/update
"""

UNI_LSB_RELEASE_OUTPUT = """
CHROMEOS_RELEASE_APPID={5A3AB642-2A67-470A-8F37-37E737A53CFC}
CHROMEOS_BOARD_APPID={5A3AB642-2A67-470A-8F37-37E737A53CFC}
CHROMEOS_CANARY_APPID={90F229CE-83E2-4FAF-8479-E368A34938B1}
DEVICETYPE=CHROMEBOOK
CHROMEOS_ARC_VERSION=4340813
CHROMEOS_ARC_ANDROID_SDK_VERSION=25
GOOGLE_RELEASE=9953.0.2017_09_18_1334
CHROMEOS_DEVSERVER=http://server.bld.corp.google.com:8080
CHROMEOS_RELEASE_BOARD=coral
CHROMEOS_RELEASE_BUILD_NUMBER=9953
CHROMEOS_RELEASE_BRANCH_NUMBER=0
CHROMEOS_RELEASE_CHROME_MILESTONE=63
CHROMEOS_RELEASE_PATCH_NUMBER=2017_09_18_1334
CHROMEOS_RELEASE_TRACK=testimage-channel
CHROMEOS_RELEASE_DESCRIPTION=9953.0.2017_09_18_1334 (Test Build)
CHROMEOS_RELEASE_BUILD_TYPE=Test Build
CHROMEOS_RELEASE_NAME=Chromium OS
CHROMEOS_RELEASE_UNIBUILD=1
CHROMEOS_RELEASE_VERSION=9953.0.2017_09_18_1334
CHROMEOS_AUSERVER=http://server.bld.corp.google.com:8080/update
CHROMEOS_RELEASE_MODELS=coral astronaut blue bruce lava nasher
"""

GSCTOOL_OUTPUT_PVT = """
start
target running protocol version 6
keyids: RO 0xaa66150f, RW 0xde88588d
offsets: backup RO at 0x40000, backup RW at 0x44000
Current versions:
RO 0.0.10
RW 0.3.14
"""

GSCTOOL_OUTPUT_PREPVT = """
start
target running protocol version 6
keyids: RO 0xaa66150f, RW 0xde88588d
offsets: backup RO at 0x40000, backup RW at 0x44000
Current versions:
RO 0.0.10
RW 0.4.15
"""

class MockCmd(object):
    """Simple mock command with base command and results"""

    def __init__(self, cmd, exit_status, stdout):
        self.cmd = cmd
        self.stdout = stdout
        self.exit_status = exit_status


class MockAFEHost(utils.EmptyAFEHost):

    def __init__(self, labels=[], attributes={}):
        self.labels = labels
        self.attributes = attributes


class MockHost(object):
    """Simple host for running mock'd host commands"""

    def __init__(self, labels, *args):
        self._afe_host = MockAFEHost(labels)
        self.mock_cmds = {c.cmd: c for c in args}
        info = host_info.HostInfo(labels=labels)
        self.host_info_store = host_info.InMemoryHostInfoStore(info)

    def run(self, command, **kwargs):
        """Finds the matching result by command value"""
        return self.mock_cmds[command]


class MockHostWithoutAFE(MockHost):

    def __init__(self, labels, *args):
        super(MockHostWithoutAFE, self).__init__(labels, *args)
        self._afe_host = utils.EmptyAFEHost()


class ModelLabelTests(unittest.TestCase):
    """Unit tests for ModelLabel"""

    def test_cros_config_succeeds(self):
        cat_lsb_release_output = """
CHROMEOS_RELEASE_BOARD=pyro
CHROMEOS_RELEASE_UNIBUILD=1
"""
        host = MockHost([],
                        MockCmd('cros_config / test-label', 0, 'coral\n'),
                        MockCmd('cat /etc/lsb-release', 0,
                                cat_lsb_release_output))
        self.assertEqual(ModelLabel().generate_labels(host), ['coral'])

    def test_cros_config_fails_mosys_succeeds(self):
        cat_lsb_release_output = """
CHROMEOS_RELEASE_BOARD=pyro
CHROMEOS_RELEASE_UNIBUILD=1
"""
        host = MockHost([],
                        MockCmd('cros_config / test-label', 1, ''),
                        MockCmd('mosys platform model', 0, 'coral\n'),
                        MockCmd('cat /etc/lsb-release', 0,
                                cat_lsb_release_output))
        self.assertEqual(ModelLabel().generate_labels(host), ['coral'])

    def test_cros_config_fails_mosys_fails(self):
        cat_lsb_release_output = """
CHROMEOS_RELEASE_BOARD=pyro
CHROMEOS_RELEASE_UNIBUILD=1
"""
        host = MockHost([],
                        MockCmd('cros_config / test-label', 1, ''),
                        MockCmd('mosys platform model', 1, ''),
                        MockCmd('cat /etc/lsb-release', 0,
                                cat_lsb_release_output))
        self.assertEqual(ModelLabel().generate_labels(host), ['pyro'])

    def test_cros_config_only_used_for_unibuilds(self):
        cat_lsb_release_output = """
CHROMEOS_RELEASE_BOARD=pyro
"""
        host = MockHost([],
                        MockCmd('cat /etc/lsb-release', 0,
                                cat_lsb_release_output))
        self.assertEqual(ModelLabel().generate_labels(host), ['pyro'])

    def test_existing_label(self):
        host = MockHost(['model:existing'])
        self.assertEqual(ModelLabel().generate_labels(host), ['existing'])

    def test_existing_label_in_host_info_store(self):
        host = MockHostWithoutAFE(['model:existing'])
        self.assertEqual(ModelLabel().generate_labels(host), ['existing'])


class BoardLabelTests(unittest.TestCase):
    """Unit tests for BoardLabel"""

    def test_new_label(self):
        cat_cmd = 'cat /etc/lsb-release'
        host = MockHost([], MockCmd(cat_cmd, 0, NON_UNI_LSB_RELEASE_OUTPUT))
        self.assertEqual(BoardLabel().generate_labels(host), ['pyro'])

    def test_existing_label(self):
        host = MockHost(['board:existing'])
        self.assertEqual(BoardLabel().generate_labels(host), ['existing'])

    def test_existing_label_in_host_info_store(self):
        host = MockHostWithoutAFE(['board:existing'])
        self.assertEqual(BoardLabel().generate_labels(host), ['existing'])

class BluetoothLabelTests(unittest.TestCase):
    """Unit tests for BluetoothLabel"""

    def test_new_label(self):
        test_cmd = 'test -d /sys/class/bluetooth/hci0'
        host = MockHost([], MockCmd(test_cmd, 0, ''))
        self.assertEqual(BluetoothLabel().exists(host), True)

    def test_existing_label(self):
        host = MockHostWithoutAFE(['bluetooth'])
        self.assertEqual(BoardLabel().exists(host), True)


class Cr50LabelTests(unittest.TestCase):
    """Unit tests for Cr50Label"""

    def test_cr50_prepvt(self):
        host = MockHost([],
                        MockCmd('gsctool -a -f', 0, GSCTOOL_OUTPUT_PREPVT))
        self.assertEqual(Cr50Label().get(host), ['cr50:0.4.15', 'cr50:prepvt'])

    def test_cr50_pvt(self):
        host = MockHost([],
                        MockCmd('gsctool -a -f', 0, GSCTOOL_OUTPUT_PVT))
        self.assertEqual(Cr50Label().get(host), ['cr50:0.3.14', 'cr50:pvt'])

    def test_gsctool_fails(self):
        host = MockHost([],
                        MockCmd('gsctool -a -f', 1, ''))
        self.assertEqual(Cr50Label().get(host), [])


if __name__ == '__main__':
    unittest.main()
