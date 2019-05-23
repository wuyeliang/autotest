# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Expects to be run in an environment with sudo and no interactive password
# prompt, such as within the Chromium OS development chroot.


"""This file provides core logic for pdtester verify/repair process."""

from autotest_lib.server.hosts import servo_host


# Names of the host attributes in the database that represent the values for
# the pdtester_host and pdtester_port for a PD tester connected to the DUT.
PDTESTER_HOST_ATTR = 'pdtester_host'
PDTESTER_PORT_ATTR = 'pdtester_port'


def make_pdtester_hostname(dut_hostname):
    """Given a DUT's hostname, return the hostname of its PD tester.

    @param dut_hostname: hostname of a DUT.

    @return hostname of the DUT's PD tester.

    """
    host_parts = dut_hostname.split('.')
    host_parts[0] = host_parts[0] + '-pdtester'
    return '.'.join(host_parts)


class PDTesterHost(servo_host.ServoHost):
    """Host class for a host that controls a PDTester object."""


    def _initialize(self, pdtester_host='localhost', pdtester_port=9998,
                    required_by_test=True, is_in_lab=None, *args, **dargs):
        """Initialize a PDTesterHost instance.

        A PDTesterHost instance represents a host that controls a PD tester.

        @param pdtester_host: Name of the host where the servod process
                              is running.
        @param pdtester_port: Port the servod process is listening on.

        """
        super(PDTesterHost, self)._initialize(pdtester_host, pdtester_port,
                                              False, None, *args, **dargs)
        self.connect_servo()


def create_pdtester_host(pdtester_args):
    """Create a PDTesterHost object used to access pdtester servo

    The `pdtester_args` parameter is a dictionary specifying optional
    PDTester client parameter overrides (i.e. a specific host or port).
    When specified, the caller requires that an exception be raised
    unless both the PDTesterHost and the PDTester are successfully
    created.

    @param pdtester_args: A dictionary that contains args for creating
                          a PDTesterHost object,
                          e.g. {'planton_host': '172.11.11.111',
                                'pdtester_port': 9999}.
                          See comments above.

    @returns: A PDTesterHost object or None. See comments above.

    """
    # TODO Make this work in the lab chromium:564836
    if pdtester_args is None:
        return None
    return PDTesterHost(Required_by_test=True, is_in_lab=False, **pdtester_args)
