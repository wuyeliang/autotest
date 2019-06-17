# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This is a server side audio sanity test testing assumptions other audio tests
rely on.
"""

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.chameleon import audio_test_utils
from autotest_lib.server.cros.multimedia import remote_facade_factory
from autotest_lib.server import test

class audio_AudioSanityCheck(test.test):
    """
    This test talks to a Cros device to verify if some basic functions that
    other audio tests rely on still work after a suspension.
    """
    version = 1
    SUSPEND_SECONDS = 30
    RPC_RECONNECT_TIMEOUT = 60

    def run_once(self, host):
        factory = remote_facade_factory.RemoteFacadeFactory(
                host, results_dir=self.resultsdir)
        audio_facade = factory.create_audio_facade()

        # Check if the chrome.audio API is available
        if not audio_facade.get_chrome_audio_availablity():
            raise error.TestFail("chrome.audio API is not available")

        # chrome.audio API should remain available after a suspension
        audio_test_utils.suspend_resume(host, self.SUSPEND_SECONDS)
        utils.poll_for_condition(condition=factory.ready,
                                 timeout=self.RPC_RECONNECT_TIMEOUT,
                                 desc='multimedia server reconnect')
        if not audio_facade.get_chrome_audio_availablity():
            raise error.TestFail(
                    "chrome.audio API is not available after suspend")
