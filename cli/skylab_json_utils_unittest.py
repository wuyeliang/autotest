# pylint: disable-msg=C0111
#!/usr/bin/python
#
# Copyright 2008 Google Inc. All Rights Reserved.
"""Test for skylab json utils."""

from __future__ import unicode_literals

import unittest

import common
from autotest_lib.cli import skylab_json_utils as sky

basic_labels = sky.Labels()
basic_labels._add_label("key1:value1")
basic_labels._add_label("key2")
basic_labels._add_label("key4")
basic_labels._add_label("key6")


class skylab_json_utils_unittest(unittest.TestCase):

    def test_label_empty(self):
        self.assertFalse(sky.Labels().bools)
        self.assertFalse(sky.Labels().strings)
        self.assertFalse(sky.Labels())

    def test_label_copy(self):
        basic_labels2 = sky.Labels(basic_labels)
        self.assertEqual(basic_labels, basic_labels2)

    def test_bool_label_present(self):
        self.assertTrue(basic_labels.get_bool("key2"))

    def test_bool_label_absent(self):
        self.assertFalse(basic_labels.get_bool("nonexistent-key"))

    def test_string_label_present(self):
        self.assertEqual(basic_labels.get_string("key1"), "value1")

    def test_string_label_absent(self):
        self.assertIsNone(basic_labels.get_string("nonexistent-key"))

    def test_enum_label_present(self):
        """the value in a key:value pair into a string that resembles a

        protobuf constant.

        The skylab add-dut JSON API expects certain fields which are
        protobuf enums to be strings of this form.
    """
        self.assertEqual(
            basic_labels.get_enum("key1", prefix="PREFIX_"), "PREFIX_VALUE1")

    def test_enum_label_absent(self):
        """by convention, many of the 'zero values' protobuf constants

    are named TYPE_INVALID.

        e.g. 'CARRIER_INVALID'
    """
        self.assertEqual(
            basic_labels.get_enum("nonexistent-key", prefix="THING_"),
            "THING_INVALID")

    def test_bool_keys_starting_with(self):
        self.assertEqual(
            set(basic_labels.bool_keys_starting_with("k")),
            {"key2", "key4", "key6"})

    def test_arc_present(self):
        l = sky.Labels()
        l._add_label("arc")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["arc"], True)

    def test_arc_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["arc"], False)

    def test_board_present(self):
        l = sky.Labels()
        l._add_label("board:nami")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["board"], "nami")

    def test_board_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["board"], None)

    def test_cr50phase_present(self):
        l = sky.Labels()
        l._add_label("cr50:0.3.18")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["cr50Phase"], "CR50_PHASE_0.3.18")

    def test_cr50phase_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["cr50Phase"], "CR50_PHASE_INVALID")

    def test_board_present(self):
        l = sky.Labels()
        l._add_label("model:syndra")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["model"], "syndra")

    def test_board_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["model"], None)

    def test_platform(self):
        l = None
        out = sky.process_labels(None, platform=47)
        self.assertEqual(out["platform"], 47)

    def test_reference_design_present(self):
        l = sky.Labels()
        l._add_label("reference_design:Google_Nami")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["referenceDesign"], "Google_Nami")

    def test_reference_design_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["referenceDesign"], None)

    def test_ec_present(self):
        l = sky.Labels()
        l._add_label("ec:cros")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["ecType"], "EC_TYPE_CHROME_OS")

    def test_ec_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertIsNone(out["ecType"])

    def test_os_present(self):
        l = sky.Labels()
        l._add_label("os:cros")
        out = sky.process_labels(l, platform=None)
        # NOTE: the type is OS_TYPE_CROS not OS_TYPE_CHROME_OS
        self.assertEqual(out["osType"], "OS_TYPE_CROS")

    def test_os_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["osType"], "OS_TYPE_INVALID")

    def test_critical_pool_present(self):
        l = sky.Labels()
        # note: use suites rather than another pool because
        # suites will always be mapped to DUT_POOL_SUITES
        l._add_label("pool:suites")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["criticalPools"], ["DUT_POOL_SUITES"])

    def test_critical_pool_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["criticalPools"], [])

    def test_cts_abi_present(self):
        l = sky.Labels()
        l._add_label("cts_abi_arm")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["ctsAbi"], ["CTS_ABI_ARM"])

    def test_cts_abi_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["ctsAbi"], [])

    def test_atrus_present(self):
        l = sky.Labels()
        l._add_label("atrus")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["atrus"], True)

    def test_atrus_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["atrus"], False)

    def test_bluetooth_present(self):
        l = sky.Labels()
        l._add_label("bluetooth")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["bluetooth"], True)

    def test_bluetooth_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["bluetooth"], False)

    def test_detachablebase_present(self):
        l = sky.Labels()
        l._add_label("detachablebase")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["detachablebase"], True)

    def test_detachablebase_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["detachablebase"], False)

    def test_flashrom_present(self):
        l = sky.Labels()
        l._add_label("flashrom")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["flashrom"], True)

    def test_flashrom_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["flashrom"], False)

    def test_hotwording_present(self):
        l = sky.Labels()
        l._add_label("hotwording")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["hotwording"], True)

    def test_hotwording_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["hotwording"], False)

    def test_internal_display_present(self):
        l = sky.Labels()
        l._add_label("internal_display")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["internalDisplay"], True)

    def test_internal_display_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["internalDisplay"], False)

    def test_lucidsleep_present(self):
        l = sky.Labels()
        l._add_label("lucidsleep")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["lucidsleep"], True)

    def test_lucidsleep_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["lucidsleep"], False)

    def test_touchpad_present(self):
        l = sky.Labels()
        l._add_label("touchpad")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["touchpad"], True)

    def test_touchpad_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["touchpad"], False)

    def test_webcam_present(self):
        l = sky.Labels()
        l._add_label("webcam")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["webcam"], True)

    def test_webcam_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["webcam"], False)

    def test_modem_present(self):
        l = sky.Labels()
        l._add_label("modem:gobi2k")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["modem"], "gobi2k")

    def test_modem_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["modem"], "")

    def test_power_present(self):
        l = sky.Labels()
        l._add_label("power:battery")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["power"], "battery")

    def test_power_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["power"], None)

    def test_storage_present(self):
        l = sky.Labels()
        l._add_label("storage:nmve")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["storage"], "nmve")

    def test_storage_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertIsNone(out["capabilities"]["storage"])

    def test_telephony_present(self):
        l = sky.Labels()
        l._add_label("telephony:volte")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["telephony"], "volte")

    def test_telephony_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["telephony"], "")

    def test_carrier_present(self):
        l = sky.Labels()
        l._add_label("carrier:att")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["carrier"], "CARRIER_ATT")

    def test_carrier_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["capabilities"]["carrier"], "CARRIER_INVALID")

    def test_audio_board_present(self):
        l = sky.Labels()
        l._add_label("audio_board")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["peripherals"]["audioBoard"], True)

    def test_audio_board_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["peripherals"]["audioBoard"], False)

    def test_audio_box_present(self):
        l = sky.Labels()
        l._add_label("audio_box")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["peripherals"]["audioBox"], True)

    def test_audio_box_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["peripherals"]["audioBox"], False)

    def test_audio_loopback_dongle_present(self):
        l = sky.Labels()
        l._add_label("audio_loopback_dongle")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["peripherals"]["audioLoopbackDongle"], True)

    def test_audio_loopback_dongle_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["peripherals"]["audioLoopbackDongle"], False)

    def test_chameleon_present(self):
        l = sky.Labels()
        l._add_label("chameleon")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["peripherals"]["chameleon"], True)

    def test_chameleon_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["peripherals"]["chameleon"], False)

    def test_chameleon_type_present(self):
        l = sky.Labels()
        # the chameleon type field is named chameleon:something
        # NOT chameleon_type:something
        l._add_label("chameleon:hdmi")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["peripherals"]["chameleonType"],
                         "CHAMELEON_TYPE_HDMI")

    def test_chameleon_type_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["peripherals"]["chameleonType"],
                         "CHAMELEON_TYPE_INVALID")

    def test_conductive_present(self):
        l = sky.Labels()
        l._add_label("conductive")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["peripherals"]["conductive"], True)

    def test_conductive_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["peripherals"]["conductive"], False)

    def test_huddly_present(self):
        l = sky.Labels()
        l._add_label("huddly")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["peripherals"]["huddly"], True)

    def test_huddly_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["peripherals"]["huddly"], False)

    def test_mimo_present(self):
        l = sky.Labels()
        l._add_label("mimo")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["peripherals"]["mimo"], True)

    def test_mimo_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["peripherals"]["mimo"], False)

    def test_servo_present(self):
        l = sky.Labels()
        l._add_label("servo")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["peripherals"]["servo"], True)

    def test_servo_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["peripherals"]["servo"], False)

    def test_stylus_present(self):
        l = sky.Labels()
        l._add_label("stylus")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["peripherals"]["stylus"], True)

    def test_stylus_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["peripherals"]["stylus"], False)

    def test_wificell_present(self):
        l = sky.Labels()
        l._add_label("wificell")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["peripherals"]["wificell"], True)

    def test_wificell_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["peripherals"]["wificell"], False)

    def test_chaos_dut_present(self):
        l = sky.Labels()
        l._add_label("chaos_dut")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["testCoverageHints"]["chaosDut"], True)

    def test_chaos_dut_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["testCoverageHints"]["chaosDut"], False)

    def test_chaos_dut_present(self):
        l = sky.Labels()
        l._add_label("chaos_dut")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["testCoverageHints"]["chaosDut"], True)

    def test_chaos_dut_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["testCoverageHints"]["chaosDut"], False)

    def test_chromesign_present(self):
        l = sky.Labels()
        l._add_label("chromesign")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["testCoverageHints"]["chromesign"], True)

    def test_chromesign_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["testCoverageHints"]["chromesign"], False)

    def test_hangout_app_present(self):
        l = sky.Labels()
        l._add_label("hangout_app")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["testCoverageHints"]["hangoutApp"], True)

    def test_hangout_app_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["testCoverageHints"]["hangoutApp"], False)

    def test_meet_app_present(self):
        l = sky.Labels()
        l._add_label("meet_app")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["testCoverageHints"]["meetApp"], True)

    def test_meet_app_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["testCoverageHints"]["meetApp"], False)

    def test_recovery_test_present(self):
        l = sky.Labels()
        l._add_label("recovery_test")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["testCoverageHints"]["recoveryTest"], True)

    def test_recovery_test_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["testCoverageHints"]["recoveryTest"], False)

    def test_test_audio_jack_present(self):
        # NOTE: test_audio_jack maps to testAudiojack
        # instead of the expected *testAudioJack
        l = sky.Labels()
        l._add_label("test_audio_jack")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["testCoverageHints"]["testAudiojack"], True)

    def test_test_audio_jack_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["testCoverageHints"]["testAudiojack"], False)

    def test_test_hdmiaudio_present(self):
        l = sky.Labels()
        l._add_label("test_hdmiaudio")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["testCoverageHints"]["testHdmiaudio"], True)

    def test_test_hdmiaudio_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["testCoverageHints"]["testHdmiaudio"], False)

    def test_test_usbprinting_present(self):
        l = sky.Labels()
        l._add_label("test_usbprinting")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["testCoverageHints"]["testUsbprinting"], True)

    def test_test_usbprinting_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["testCoverageHints"]["testUsbprinting"], False)

    def test_usb_detect_present(self):
        l = sky.Labels()
        l._add_label("usb_detect")
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["testCoverageHints"]["usbDetect"], True)

    def test_usb_detect_absent(self):
        l = sky.Labels()
        out = sky.process_labels(l, platform=None)
        self.assertEqual(out["testCoverageHints"]["usbDetect"], False)


if __name__ == "__main__":
    unittest.main()
