# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import tcpdump_analyzer
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server.cros.network import wifi_cell_test_base


class network_WiFi_APSupportedRates(wifi_cell_test_base.WiFiCellTestBase):
    """Test that the WiFi chip honors the SupportedRates IEs sent by the AP."""
    version = 1

    def check_bitrates_in_capture(self, pcap_result, supported_rates):
        """
        Check that bitrates look like we expect in a packet capture.

        The DUT should not send packets at bitrates that were disabled by the
        AP.

        @param pcap_result: RemoteCaptureResult tuple.
        @param supported_rates: List of upported legacy bitrates (Mbps).

        """
        dut_src_display_filter = 'wlan.sa==%s' % self.context.client.wifi_mac
        # Some chips use self-addressed frames to tune channel
        # performance. They don't carry host-generated traffic, so
        # filter them out.
        dut_dst_display_filter = 'wlan.da==%s' % self.context.client.wifi_mac
        frames = tcpdump_analyzer.get_frames(pcap_result.local_pcap_path,
                                             ('%s and not %s' % (
                                              dut_src_display_filter,
                                              dut_dst_display_filter)),
                                             reject_bad_fcs=False)

        for frame in frames:
            # Some frames don't have bitrate fields -- for example, if they are
            # using MCS rates (not legacy rates). For MCS rates, that's OK,
            # since that satisfies this test requirement (not using
            # "unsupported legacy rates"). So ignore them.
            if (frame.bit_rate is not None and
                frame.bit_rate not in supported_rates):
                logging.error('Unexpected rate for: %s', frame)
                raise error.TestFail('Frame at %s was sent at %f Mbps '
                                     '(expected %r).' %
                                     (frame.time_string, frame.bit_rate,
                                      supported_rates))

    def parse_additional_arguments(self, commandline_args, additional_params):
        """Hook into super class to take control files parameters.

        @param commandline_args dict of parsed parameters from the autotest.
        @param additional_params HostapConfig object.

        """
        self._ap_config = additional_params

    def run_once(self):
        """Verify that we respond sanely to APs that disable legacy bitrates.
        """
        ap_config = self._ap_config
        self.context.configure(ap_config)
        self.context.capture_host.start_capture(
                ap_config.frequency,
                ht_type=ap_config.ht_packet_capture_mode)
        assoc_params = xmlrpc_datatypes.AssociationParameters(
                ssid=self.context.router.get_ssid())
        self.context.assert_connect_wifi(assoc_params)
        self.context.assert_ping_from_dut()
        results = self.context.capture_host.stop_capture()
        if len(results) != 1:
            raise error.TestError('Expected to generate one packet '
                                  'capture but got %d captures instead.' %
                                  len(results))
        self.check_bitrates_in_capture(results[0],
                                       ap_config.supported_rates)
