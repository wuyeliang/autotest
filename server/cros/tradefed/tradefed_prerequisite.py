# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

def bluetooth(hosts):
    """Check for missing bluetooth hardware.
    """
    for host in hosts:
        output = host.run('hcitool dev').stdout
        lines = output.splitlines()
        if len(lines) < 2 or not lines[0].startswith('Devices:'):
            return False, 'Failed: Bluetooth device is missing.'\
                          'Stdout of the command "hcitool dev1"'\
                          'on host %s was %s' % (host, output)
    return True, ''


def region_us(hosts):
    """Check that region is set to "us".
    """
    for host in hosts:
        output = host.run('vpd -g region').stdout
        if out != 'us':
            return False, 'Failed: Region is not "us".'\
                          'Stdout of the command "vpd -l'\
                          '| grep region" on host %s was %s'\
                          % (host, output)
    return True, ''

prerequisite_map = {
    'bluetooth': bluetooth,
    'region_us': region_us,
}

def check(prereq, hosts):
    """Execute the prerequisite check.

    @return boolean indicating if check passes.
    @return string error message if check fails.
    """
    if prereq not in prerequisite_map:
        logging.info('%s is not a valid prerequisite.', prereq)
        return True, ''
    return prerequisite_map[prereq](hosts)
