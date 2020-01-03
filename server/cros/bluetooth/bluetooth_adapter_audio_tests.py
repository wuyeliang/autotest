# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Server side Bluetooth audio tests."""

import logging

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.bluetooth.bluetooth_audio_test_data import (
        a2dp_test_data)
from autotest_lib.server.cros.bluetooth.bluetooth_adapter_tests import (
        BluetoothAdapterTests, test_retry_and_log)


class BluetoothAdapterAudioTests(BluetoothAdapterTests):
    """Server side Bluetooth adapter audio test class."""

    DEVICE_TYPE = 'BLUETOOTH_AUDIO'
    FREQUENCY_TOLERANCE_RATIO = 0.01

    def _get_pulseaudio_bluez_source(self, get_source_method, device):
        """Get the specified bluez device number in the pulseaudio source list.

        @param get_source_method: the method to get distinct bluez source
        @param device: the bluetooth peer device

        @returns: True if the specified bluez source is derived
        """
        sources = device.ListSources()
        logging.debug('ListSources()\n%s', sources)
        self.bluez_source = get_source_method()
        result = bool(self.bluez_source)
        if result:
            logging.debug('bluez_source device number: %s', self.bluez_source)
        else:
            logging.debug('waiting for bluez_source ready in pulseaudio...')
        return result


    def _get_pulseaudio_bluez_source_a2dp(self, device):
        """Get the a2dp bluez source device number.

        @param device: the bluetooth peer device

        @returns: the a2dp bluez source device number
        """
        return self._get_pulseaudio_bluez_source(
                device.GetBluezSourceA2DPDevice, device)


    def _get_pulseaudio_bluez_source_hfp(self, device):
        """Get the hfp bluez source device number.

        @param device: the bluetooth peer device

        @returns: the hfp bluez source device number
        """
        return self._get_pulseaudio_bluez_source(
                device.GetBluezSourceHFPDevice, device)


    def _check_frequency(self, recorded_freq, expected_freq):
        """Check if the recorded frequency is within tolerance.

        @param recorded_freq: the frequency of recorded audio
        @param expected_freq: the expected frequency

        @returns: True if the recoreded frequency falls within the tolerance of
                  the expected frequency
        """
        tolerance = expected_freq * self.FREQUENCY_TOLERANCE_RATIO
        return abs(expected_freq - recorded_freq) <= tolerance


    def _check_primary_frequencies(self, audio_test_data):
        """Check if the recorded frequencies meet expectation.

        @param audio_test_data: a dictionary about the audio test data
                defined in client/cros/bluetooth/bluetooth_audio_test_data.py

        @returns: True if the recorded frequencies of all channels fall within
                the tolerance of expected frequencies
        """
        recorded_frequencies = self.bluetooth_facade.get_primary_frequencies(
                audio_test_data['recorded_file'])
        expected_frequencies = audio_test_data['frequencies']
        final_result = True
        self.results = dict()
        for channel, expected_freq in enumerate(expected_frequencies):
            recorded_freq = recorded_frequencies[channel]
            ret_val = self._check_frequency(recorded_freq, expected_freq)
            pass_fail_str = 'pass' if ret_val else 'fail'
            self.results['Channel %d' % channel] = (
                    'primary frequency %d (expected %d): %s' % (
                    recorded_freq, expected_freq, pass_fail_str))
            if not ret_val:
                final_result = False

        logging.debug(str(self.results))
        if not final_result:
            logging.error('Failure at checking primary frequencies')
        return final_result


    def initialize_bluetooth_audio(self, device):
        """Initialize the Bluetooth audio task.

        Note: pulseaudio is not stable. Need to restart it in the beginning.

        @param device: the bluetooth peer device

        """
        if not device.StartPulseaudio():
            raise error.TestError('Failed to start pulseaudio.')
        logging.debug('pulseaudio is started.')


    def cleanup_bluetooth_audio(self, device):
        """Cleanup for Bluetooth audio.

        @param device: the bluetooth peer device

        """
        if not device.StopPulseaudio():
            logging.warn('Failed to stop pulseaudio. Ignored.')


    # ---------------------------------------------------------------
    # Definitions of all bluetooth audio test cases
    # ---------------------------------------------------------------


    @test_retry_and_log(False)
    def test_a2dp_sinewaves(self, device):
        """Test Case: a2dp sinewaves

        @param device: the bluetooth peer device

        @returns: True if the recorded primary frequency is within the
                  tolerance of the playback sine wave frequency.

        """
        try:
            utils.poll_for_condition(
                    condition=(lambda:
                               self._get_pulseaudio_bluez_source_a2dp(device)),
                    timeout=20,
                    sleep_interval=1,
                    desc='Waiting for bluez a2dp source in pulseaudio')
        except Exception as e:
            logging.error('pulseaudio bluez_source: %s', e)
            raise error.TestError('Bluetooth peer failed to get bluez source.')

        # Start recording audio on the peer Bluetooth audio device.
        if not device.StartRecordingAudioSubprocess('a2dp'):
            raise error.TestError(
                    'Failed to record on the peer Bluetooth audio device.')

        # Play stereo audio on the DUT.
        if not self.bluetooth_facade.play_audio(a2dp_test_data):
            raise error.TestError('DUT failed to play audio.')

        # Stop recording audio on the peer Bluetooth audio device.
        if not device.StopRecordingingAudioSubprocess():
            msg = 'Failed to stop recording on the peer Bluetooth audio device'
            logging.error(msg)

        # Copy the recorded audio file to the DUT for spectrum analysis.
        recorded_file = a2dp_test_data['recorded_file']
        device.ScpToDut(recorded_file, recorded_file, self.host.ip)

        # Check if the primary frequencies of recorded file meet expectation.
        check_freq_result = self._check_primary_frequencies(a2dp_test_data)
        return check_freq_result
