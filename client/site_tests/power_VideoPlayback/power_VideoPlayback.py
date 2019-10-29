# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import os
import time

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import file_utils
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.audio import audio_helper
from autotest_lib.client.cros.input_playback import keyboard
from autotest_lib.client.cros.power import power_test


class power_VideoPlayback(power_test.power_Test):
    """class for power_VideoPlayback test.
    """
    version = 1

    _BASE_URL='http://storage.googleapis.com/chromiumos-test-assets-public/tast/cros/video/power/2m/'

    # list of video name and url.
    _VIDEOS = [
        ('h264_720_30fps',
         _BASE_URL + '720p30fpsH264_foodmarket_sync_2m.mp4'
        ),
        ('h264_720_60fps',
         _BASE_URL + '720p60fpsH264_boat_sync_2m.mp4'
        ),
        ('h264_1080_30fps',
         _BASE_URL + '1080p30fpsH264_foodmarket_sync_2m.mp4'
        ),
        ('h264_1080_60fps',
         _BASE_URL + '1080p60fpsH264_boat_sync_2m.mp4'
        ),
        ('h264_4k_30fps',
         _BASE_URL + '4k30fpsH264_foodmarket_sync_vod_2m.mp4'
        ),
        ('h264_4k_60fps',
         _BASE_URL + '4k60fpsH264_boat_sync_vod_2m.mp4'
        ),
        ('vp8_720_30fps',
         _BASE_URL + '720p30fpsVP8_foodmarket_sync_2m.webm'
        ),
        ('vp8_720_60fps',
         _BASE_URL + '720p60fpsVP8_boat_sync_2m.webm'
        ),
        ('vp8_1080_30fps',
         _BASE_URL + '1080p30fpsVP8_foodmarket_sync_2m.webm'
        ),
        ('vp8_1080_60fps',
         _BASE_URL + '1080p60fpsVP8_boat_sync_2m.webm'
        ),
        ('vp8_4k_30fps',
         _BASE_URL + '4k30fpsVP8_foodmarket_sync_2m.webm'
        ),
        ('vp8_4k_60fps',
         _BASE_URL + '4k60fpsVP8_boat_sync_2m.webm'
        ),
        ('vp9_720_30fps',
         _BASE_URL + '720p30fpsVP9_foodmarket_sync_2m.webm'
        ),
        ('vp9_720_60fps',
         _BASE_URL + '720p60fpsVP9_boat_sync_2m.webm'
        ),
        ('vp9_1080_30fps',
         _BASE_URL + '1080p30fpsVP9_foodmarket_sync_2m.webm'
        ),
        ('vp9_1080_60fps',
         _BASE_URL + '1080p60fpsVP9_boat_sync_2m.webm'
        ),
        ('vp9_4k_30fps',
         _BASE_URL + '4k30fpsVP9_foodmarket_sync_2m.webm'
        ),
        ('vp9_4k_60fps',
         _BASE_URL + '4k60fpsVP9_boat_sync_2m.webm'
        ),
        ('av1_720_30fps',
         _BASE_URL + '720p30fpsAV1_foodmarket_sync_2m.mp4'
        ),
        ('av1_720_60fps',
         _BASE_URL + '720p60fpsAV1_boat_sync_2m.mp4'
        ),
        ('av1_1080_30fps',
         _BASE_URL + '1080p30fpsAV1_foodmarket_sync_2m.mp4'
        ),
        ('av1_1080_60fps',
         _BASE_URL + '1080p60fpsAV1_boat_sync_2m.mp4'
        ),
    ]

    # Ram disk location to download video file.
    # We use ram disk to avoid power hit from network / disk usage.
    _RAMDISK = '/tmp/ramdisk'

    # Time in seconds to wait after set up before starting each video.
    _WAIT_FOR_IDLE = 15

    # Time in seconds to measure power per video file.
    _MEASUREMENT_DURATION = 120

    # Chrome arguments to disable HW video decode
    _DISABLE_HW_VIDEO_DECODE_ARGS = '--disable-accelerated-video-decode'

    def initialize(self, pdash_note='', seconds_period=3):
        """Create and mount ram disk to download video."""
        super(power_VideoPlayback, self).initialize(
                seconds_period=seconds_period, pdash_note=pdash_note)
        utils.run('mkdir -p %s' % self._RAMDISK)
        # Don't throw an exception on errors.
        result = utils.run('mount -t ramfs -o context=u:object_r:tmpfs:s0 '
                           'ramfs %s' % self._RAMDISK, ignore_status=True)
        if result.exit_status:
            logging.info('cannot mount ramfs with context=u:object_r:tmpfs:s0,'
                         ' trying plain mount')
            # Try again without selinux options.  This time fail on error.
            utils.run('mount -t ramfs ramfs %s' % self._RAMDISK)
        audio_helper.set_volume_levels(10, 10)

    def _play_video(self, cr, local_path):
        """Opens the video and plays it.

        @param cr: Autotest Chrome instance.
        @param local_path: path to the local video file to play.
        """
        tab = cr.browser.tabs[0]
        tab.Navigate(cr.browser.platform.http_server.UrlOf(local_path))
        tab.WaitForDocumentReadyStateToBeComplete()

    def _calculate_dropped_frame_percent(self, tab):
        """Calculate percent of dropped frame.

        @param tab: tab object that played video in Autotest Chrome instance.
        """
        decoded_frame_count = tab.EvaluateJavaScript(
                "document.getElementsByTagName"
                "('video')[0].webkitDecodedFrameCount")
        dropped_frame_count = tab.EvaluateJavaScript(
                "document.getElementsByTagName"
                "('video')[0].webkitDroppedFrameCount")
        if decoded_frame_count != 0:
            dropped_frame_percent = \
                    100.0 * dropped_frame_count / decoded_frame_count
        else:
            logging.error("No frame is decoded. Set drop percent to 100.")
            dropped_frame_percent = 100.0

        logging.info("Decoded frames=%d, dropped frames=%d, percent=%f",
                decoded_frame_count, dropped_frame_count, dropped_frame_percent)
        return dropped_frame_percent

    def run_once(self, videos=None, secs_per_video=_MEASUREMENT_DURATION,
                 use_hw_decode=True):
        """run_once method.

        @param videos: list of tuple of tagname and video url to test.
        @param secs_per_video: time in seconds to play video and measure power.
        @param use_hw_decode: if False, disable hw video decoding.
        """
        if not videos:
            videos = self._VIDEOS

        extra_browser_args = []
        if not use_hw_decode:
            extra_browser_args.append(self._DISABLE_HW_VIDEO_DECODE_ARGS)

        with chrome.Chrome(extra_browser_args=extra_browser_args,
                           init_network_controller=True) as self.cr:
            tab = self.cr.browser.tabs.New()
            tab.Activate()

            # Just measure power in full-screen.
            fullscreen = tab.EvaluateJavaScript('document.webkitIsFullScreen')
            if not fullscreen:
                with keyboard.Keyboard() as keys:
                    keys.press_key('f4')

            self.start_measurements()
            idle_start = time.time()

            for name, url in videos:
                # Download video to ramdisk
                local_path = os.path.join(self._RAMDISK, os.path.basename(url))
                logging.info('Downloading %s to %s', url, local_path)
                file_utils.download_file(url, local_path)
                self.cr.browser.platform.SetHTTPServerDirectories(self._RAMDISK)

                time.sleep(self._WAIT_FOR_IDLE)

                logging.info('Playing video: %s', name)
                self._play_video(self.cr, local_path)
                self.checkpoint_measurements('idle', idle_start)

                loop_start = time.time()
                time.sleep(secs_per_video)
                self.checkpoint_measurements(name, loop_start)

                idle_start = time.time()
                self.keyvals[name + '_dropped_frame_percent'] = \
                        self._calculate_dropped_frame_percent(tab)
                self.cr.browser.platform.StopAllLocalServers()
                os.remove(local_path)

    def cleanup(self):
        """Unmount ram disk."""
        utils.run('umount %s' % self._RAMDISK)
        super(power_VideoPlayback, self).cleanup()
