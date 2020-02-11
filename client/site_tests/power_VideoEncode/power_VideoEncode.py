# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import itertools
import logging
import time

from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.input_playback import keyboard
from autotest_lib.client.cros.power import power_dashboard
from autotest_lib.client.cros.power import power_status
from autotest_lib.client.cros.power import power_test


class power_VideoEncode(power_test.power_Test):
    """class for power_VideoEncode test."""
    version = 1

    video_url = 'https://crospower.page.link/power_VideoEncode'
    extra_browser_args = ['--use-fake-ui-for-media-stream']

    codecs = ['h264', 'vp8', 'vp9', 'av1']
    resolutions = ['360', '720', '1080', '4k']
    framerates = [30, 60]

    def run_once(self, seconds_per_test=120, codecs=codecs,
                 resolutions=resolutions, framerates=framerates):
        """run_once method.

        @param seconds_per_test: time in seconds for each subtest.
        @param codecs: list of codec to test. Possible value are
                       ['h264', 'vp8', 'vp9', 'av1'].
        @param resolutions: list of resolutions to test. Possible value are
                       ['360', '540', '720', '1080', '1440', '4k'].
        @param framerates: list of framerate to test. Possible value are
                           number in the range of 1 to 60.

        """
        with chrome.Chrome(init_network_controller=True,
                           extra_browser_args=self.extra_browser_args) as cr:

            tab = cr.browser.tabs.New()
            tab.Activate()

            # Just measure power in full-screen.
            fullscreen = tab.EvaluateJavaScript('document.webkitIsFullScreen')
            if not fullscreen:
                with keyboard.Keyboard() as keys:
                    keys.press_key('f4')

            url = self.video_url
            tab.Navigate(url)
            tab.WaitForDocumentReadyStateToBeComplete()
            time.sleep(10)

            self._vlog = power_status.VideoFpsLogger(tab,
                seconds_period=self._seconds_period,
                checkpoint_logger=self._checkpoint_logger)
            self._meas_logs.append(self._vlog)

            loop = 0
            self.start_measurements()
            for codec, resolution, fps in itertools.product(codecs, resolutions,
                                                            framerates):
                tagname = '%s_%s_%sfps' % (codec, resolution, fps)
                js = 'changeFormat("%s", "%s", %d)' % (codec, resolution, fps)
                logging.info(js)
                tab.EvaluateJavaScript(js)
                loop_start = time.time()
                self.loop_sleep(loop, seconds_per_test)
                self.checkpoint_measurements(tagname, loop_start)
                loop += 1

    def publish_dashboard(self):
        """Report results power dashboard."""
        super(power_VideoEncode, self).publish_dashboard()

        vdash = power_dashboard.VideoFpsLoggerDashboard(
            self._vlog, self.tagged_testname, self.resultsdir,
            note=self._pdash_note)
        vdash.upload()
