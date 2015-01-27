# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import httpd


WAIT_TIMEOUT_S = 5
PLAYBACK_TEST_TIME_S = 5
MEDIA_SUPPORT_AVAILABLE = 'maybe'


class video_VideoSanity(test.test):
    """This test verify the media elements and video sanity.

    - verify support for mp4, ogg and webm media.
    - verify html5 video playback.

    """
    version = 2


    def initialize(self):
        self._testServer = httpd.HTTPListener(8000, docroot=self.bindir)
        self._testServer.run()


    def cleanup(self):
        if self._testServer:
            self._testServer.stop()


    def video_current_time(self):
        """Returns video's current playback time.

        Returns:
            returns the current playback location in seconds (int).

        """
        return int(self.tab.EvaluateJavaScript('testvideo.currentTime'))


    def video_duration(self):
        """Returns video total length.

        Returns:
            returns the total video length in seconds (int).

        """
        return int(self.tab.EvaluateJavaScript('testvideo.duration'))


    def run_video_sanity_test(self, browser):
        """Run the video sanity test.

        @param browser: The Browser object to run the test with.

        """
        self.tab = browser.tabs.New()
        # Verifying <video> support.
        video_containers = ('mp4', 'ogg', 'webm')
        self.tab.Navigate('http://localhost:8000/video.html')
        for container in video_containers:
            logging.info('Verifying video support for %s.', container)
            js_script = ("document.createElement('video').canPlayType"
                         "('video/" + container + "')")
            status = self.tab.EvaluateJavaScript(js_script)
            if status != MEDIA_SUPPORT_AVAILABLE:
                raise error.TestError('No media support available for %s.'
                                       % container)
        # Waiting for test video to load.
        wait_time = 0 # seconds
        while float(
                self.tab.EvaluateJavaScript('videoCurTime.innerHTML')) < 1.0:
            time.sleep(1)
            wait_time = wait_time + 1
            if wait_time > WAIT_TIMEOUT_S:
                raise error.TestError('Video failed to load.')
        # Muting the video.
        self.tab.EvaluateJavaScript('testvideo.volume=0')

        # Verifying video playback.
        playback = 0 # seconds
        prev_playback = 0
        while (self.video_current_time() < self.video_duration()
               and playback < PLAYBACK_TEST_TIME_S):
            if self.video_current_time() <= prev_playback:
                raise error.TestError('Video is not playing.')
            prev_playback = self.video_current_time()
            time.sleep(1)
            playback = playback + 1


    def run_once(self):
        boards_to_skip = ['x86-mario', 'x86-zgb']
        # TODO(scottz): Remove this when crbug.com/220147 is fixed.
        dut_board = utils.get_current_board()
        if dut_board in boards_to_skip:
            logging.info("Skipping test run on this board.")
            return
        with chrome.Chrome() as cr:
            self.run_video_sanity_test(cr.browser)
