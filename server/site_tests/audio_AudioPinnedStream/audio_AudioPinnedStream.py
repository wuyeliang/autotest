# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a server side pinned stream audio test using the Chameleon board."""

import logging
import os
import time

from autotest_lib.client.cros.audio import audio_test_data
from autotest_lib.client.cros.chameleon import audio_test_utils
from autotest_lib.client.cros.chameleon import chameleon_audio_ids
from autotest_lib.client.cros.chameleon import chameleon_audio_helper
from autotest_lib.server.cros.audio import audio_test
from autotest_lib.server.cros.multimedia import remote_facade_factory


class audio_AudioPinnedStream(audio_test.AudioTest):
    """Server side pinned stream audio test.

    This test talks to a Chameleon board and a Cros device to verify
    pinned stream audio function of the Cros device.

    """
    version = 1
    DELAY_BEFORE_RECORD_SECONDS = 0.5
    RECORD_SECONDS = 3
    DELAY_AFTER_BINDING = 0.5
    DELAY_AFTER_SETTING = 5

    def run_once(self, host):
        """Running basic pinned stream audio tests.

        @param host: device under test host
        """
        if not audio_test_utils.has_headphone(host):
            return

        # [1330, 1330] sine wave
        golden_file = audio_test_data.SIMPLE_FREQUENCY_TEST_1330_FILE
        # [2000, 1000] sine wave
        usb_golden_file = audio_test_data.FREQUENCY_TEST_FILE

        chameleon_board = host.chameleon
        factory = remote_facade_factory.RemoteFacadeFactory(
                host, results_dir=self.resultsdir)

        chameleon_board.setup_and_reset(self.outputdir)

        widget_factory = chameleon_audio_helper.AudioWidgetFactory(
                factory, host)

        source = widget_factory.create_widget(
            chameleon_audio_ids.CrosIds.HEADPHONE)

        recorder = widget_factory.create_widget(
            chameleon_audio_ids.ChameleonIds.LINEIN)
        binder = widget_factory.create_binder(source, recorder)

        usb_source = widget_factory.create_widget(
            chameleon_audio_ids.CrosIds.USBOUT)
        usb_recorder = widget_factory.create_widget(
            chameleon_audio_ids.ChameleonIds.USBIN)
        usb_binder = widget_factory.create_binder(usb_source, usb_recorder)

        with chameleon_audio_helper.bind_widgets(usb_binder):
            with chameleon_audio_helper.bind_widgets(binder):
                time.sleep(self.DELAY_AFTER_BINDING)

                audio_facade = factory.create_audio_facade()
                plugger = chameleon_board.get_audio_board().get_jack_plugger()

                # Fix for chameleon rack hosts because audio jack is always plugged.
                # crbug.com/955009
                if plugger is None:
                    audio_facade.set_selected_node_types(['HEADPHONE'], [''])
                    time.sleep(self.DELAY_AFTER_SETTING)

                audio_test_utils.check_audio_nodes(
                    audio_facade, (['HEADPHONE'], None))

                logging.info('Setting playback data on Cros device')
                source.set_playback_data(golden_file)
                usb_source.set_playback_data(usb_golden_file)

                logging.info('Start playing %s on USB', usb_golden_file.path)
                usb_source.start_playback(pinned=True)

                logging.info('Start playing %s on headphone', golden_file.path)
                source.start_playback()

                time.sleep(self.DELAY_BEFORE_RECORD_SECONDS)
                logging.info('Start recording from Chameleon.')

                # Not any two recorders on chameleon can record at the same
                # time. USB and LineIn can but we would keep them separate
                # here to keep things simple and change it when needed.
                # Should still record 1330 sine wave from USB as it was set
                # pinned on USB.
                usb_recorder.start_recording()
                time.sleep(self.RECORD_SECONDS)
                usb_recorder.stop_recording()

                # Should record [2000, 1000] sine from headphone.
                recorder.start_recording()
                time.sleep(self.RECORD_SECONDS)
                recorder.stop_recording()

                logging.info('Stopped recording from Chameleon.')

                audio_test_utils.dump_cros_audio_logs(
                        host, audio_facade, self.resultsdir, 'after_recording')

                recorder.read_recorded_binary()
                usb_recorder.read_recorded_binary()
                logging.info('Read recorded binary from Chameleon.')

        recorded_file = os.path.join(self.resultsdir, "recorded.raw")
        logging.info('Saving recorded data to %s', recorded_file)
        recorder.save_file(recorded_file)

        # Removes the beginning of recorded data. This is to avoid artifact
        # caused by Chameleon codec initialization in the beginning of
        # recording.
        recorder.remove_head(0.5)

        recorded_file = os.path.join(self.resultsdir, "recorded_clipped.raw")
        logging.info('Saving clipped data to %s', recorded_file)
        recorder.save_file(recorded_file)

        usb_recorded_file = os.path.join(self.resultsdir, "usb_recorded.raw")
        logging.info('Saving recorded data to %s', usb_recorded_file)
        usb_recorder.save_file(usb_recorded_file)

        audio_test_utils.check_recorded_frequency(golden_file, recorder)

        audio_test_utils.check_recorded_frequency(usb_golden_file, usb_recorder)
