# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import requests
import subprocess
import time

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error


class NebraskaWrapper(object):
    """
    A wrapper around nebraska.py

    This wrapper is used to start a nebraska.py service and allow the
    update_engine to interact with it.

    """

    def __init__(self, log_dir=None):
        """
        Initializes the NebraskaWrapper module.

        @param log_dir: The directory to write nebraska.log into.

        """
        self._nebraska_server = None
        self._port = None
        self._log_dir = log_dir

    def __enter__(self):
        """So that NebraskaWrapper can be used as a Context Manager."""
        self.start()
        return self

    def __exit__(self, *exception_details):
        """
        So that NebraskaWrapper can be used as a Context Manager.

        @param exception_details: Details of exceptions happened in the
                ContextManager.

        """
        self.stop()

    def start(self):
        """
        Starts the Nebraska server.

        @raise error.TestError: If fails to start the Nebraska server.

        """
        logging.info('Starting nebraska.py')

        # Any previously-existing files (port, pid and log files) will be
        # overriden by Nebraska during bring up.
        runtime_root = '/tmp/nebraska'
        cmd = ['nebraska.py', '--runtime-root', runtime_root]
        if self._log_dir:
            cmd += ['--log-file', os.path.join(self._log_dir, 'nebraska.log')]

        try:
            self._nebraska_server = subprocess.Popen(cmd,
                                                     stdout=subprocess.PIPE,
                                                     stderr=subprocess.PIPE)

            # Wait for port file to appear.
            port_file = os.path.join(runtime_root, 'port')
            utils.poll_for_condition(lambda: os.path.exists(port_file),
                                     timeout=5)

            with open(port_file, 'r') as f:
                self._port = int(f.read())

            # Send a health_check request to it to make sure its working.
            requests.get('http://127.0.0.1:%d/health_check' % self._port)

        except Exception as e:
            raise error.TestError('Failed to start Nebraska %s' % e)

    def stop(self):
        """Stops the Nebraska server."""
        logging.info('Stopping nebraska.py')
        if not self._nebraska_server:
            return
        try:
            self._nebraska_server.terminate()
            self._nebraska_server.communicate()
            self._nebraska_server.wait()
        except subprocess.TimeoutExpired:
            logging.error('Failed to stop Nebraska. Ignoring...')
        finally:
            self._nebraska_server = None

    def get_port(self):
        """Returns the port which Nebraska is running."""
        return self._port
