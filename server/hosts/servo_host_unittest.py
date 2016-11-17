# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

#!/usr/bin/python

import unittest
import common

from autotest_lib.server.hosts import servo_host


class ServerHostTest(unittest.TestCase):
    """Tests the ServoHost function."""

    def test_get_sudo_sh_command(self):
        """Tests _get_config_val_cmd."""
        self.assertEqual(
                'sudo -n sh -c "[ -f /tmp/foo ] && . /tmp/foo && echo \\$BOARD"',
                servo_host._get_sudo_sh_command(
                    '[ -f /tmp/foo ] && . /tmp/foo && echo $BOARD'))


if __name__ == "__main__":
    unittest.main()
