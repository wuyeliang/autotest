# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

#!/usr/bin/python

import unittest
import common

from autotest_lib.server.hosts import servo_repair


class ConfigVerifierTest(unittest.TestCase):
    """Tests the _ConfigVerifier function."""

    def test_get_config_val_cmd(self):
        """Tests _get_config_val_cmd."""
        self.assertEqual(
                '[ -f /tmp/foo ] && . /tmp/foo && echo $BOARD',
                servo_repair._ConfigVerifier._get_config_val_cmd(
                    '/tmp/foo', 'BOARD'))


if __name__ == "__main__":
    unittest.main()
