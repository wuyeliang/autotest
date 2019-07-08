from __future__ import unicode_literals

# NOTE: send bvt to BVT
#       send everything else to SUITES
#
# This decision has to be made on a pool by pool basis.
POOL_ATEST_TO_SK = {
    "bvt": "DUT_POOL_BVT",
    "suites": "DUT_POOL_SUITES",
    "labstation_main": "DUT_POOL_SUITES",
    "lab_automation": "DUT_POOL_SUITES",
    "cts": "DUT_POOL_SUITES",
    "wificell": "DUT_POOL_SUITES",
}

EC_TYPE_ATEST_TO_SK = {
    "cros": "EC_TYPE_CHROME_OS",
}


class Labels(object):
    """a queryable interface to labels taken from autotest"""

    def __init__(self, labels=None):
        self.bools = set()
        self.strings = {}
        if isinstance(labels, Labels):
            self.bools.update(labels.bools)
            self.strings.update(labels.strings)
        elif labels:
            for label in labels:
                self._add_label(label["name"])

    def __len__(self):
        return len(self.bools) + len(self.strings)

    def __eq__(self, other):
        return self.bools == other.bools and self.strings == other.strings

    def _add_label(self, name):
        """add a label with a name of the autotest form:

        key or key:value.
        """
        key, sep, value = name.partition(":")
        if sep:
            self.strings.setdefault(key, [])
            self.strings[key].append(value)
        else:
            self.bools.add(key)

    def get_bool(self, x):
        return x in self.bools

    def get_string(self, x, default=None):
        item = self.strings.get(x, [])
        # TODO(gregorynisbet) -- what should we actually do if there's more than
        #   one value associated with the same key?
        if item:
            return item[0]
        else:
            return default

    def get_all_strings(self, x, default=None):
        return self.strings.get(x, [])

    def get_enum(self, x, default=None, prefix=None):
        if default is None:
            default = "INVALID"
        raw = self.get_string(x, default=default)
        return prefix + raw.upper()

    def get_enum_or_none(self, x, prefix=None):
        assert prefix.endswith("_")
        raw = self.get_string(x, default=None)
        if raw is None:
            return None
        else:
            return prefix + raw.upper()

    def bool_keys_starting_with(self, prefix):
        """get the boolean keys beginning with
        a certain prefix.

        Takes time proportional to the number of boolean keys.
        """
        for x in self.bools:
            if x.startswith(prefix):
                yield x


def _critical_pools(l):
    atest_pools = l.get_all_strings("pool")
    out = []
    for value in atest_pools:
        out.append(POOL_ATEST_TO_SK[value])
    return out


def _cr50_phase(l):
    return l.get_enum("cr50", prefix="CR50_PHASE_")


def _cts_abi(l):
    """The ABI has the structure cts_abi_x86 and cts_abi_arm

    instead of the expected cts_abi:x86 and cts_abi_arm
    """
    out = []
    for abi in ["cts_abi_x86", "cts_abi_arm"]:
        if l.get_bool(abi):
            out.append(abi.upper())
    return out


def _ec_type(l):
    """Get the ec type."""
    name = l.get_string("ec")
    return EC_TYPE_ATEST_TO_SK.get(name, None)


def _video_acceleration(l):
    """produce a list of enums corresponding

    to the video_acc_ keys in the atest format
    """
    out = []
    for key in l.bool_keys_starting_with("video_acc"):
        _, delim, suffix = key.rpartition("video_acc_")
        assert delim == "video_acc_"
        out.append("VIDEO_ACCELERATION" + _ + suffix.upper())
    return out


def _platform(l):
    return l.get_string("platform") or l.get_string("Platform")


def process_labels(labels, platform):
    """produce a JSON object of the kind accepted by skylab add-dut

    for the labels from autotest
    """
    l = Labels(labels)

    # The enum-type keys below default to None
    # except for 'telephony' and 'modem', which default to ''
    # This is intentional.
    # This function will always return a json-like Python data object,
    # even in cases where some normally required fields are missing.
    # The explicit None is there as an explicit placeholder.
    return {
        # boolean keys in label
        "arc": l.get_bool("arc"),
        # string keys in label
        "board": l.get_string("board", default=None),
        "cr50Phase": _cr50_phase(l),
        "model": l.get_string("model", default=None),
        "platform": platform,
        "referenceDesign": l.get_string("reference_design"),
        # enum keys
        "ecType": _ec_type(l),
        "osType": l.get_enum("os", prefix="OS_TYPE_"),
        "phase": l.get_enum("phase", prefix="PHASE_"),
        # list of enum keys
        "criticalPools": _critical_pools(l),
        "ctsAbi": _cts_abi(l),
        # capabilities substructure
        "capabilities": {
            # boolean keys in capabilities
            "atrus": l.get_bool("atrus"),
            "bluetooth": l.get_bool("bluetooth"),
            "detachablebase": l.get_bool("detachablebase"),
            "flashrom": l.get_bool("flashrom"),
            "hotwording": l.get_bool("hotwording"),
            "internalDisplay": l.get_bool("internal_display"),
            "lucidsleep": l.get_bool("lucidsleep"),
            "touchpad": l.get_bool("touchpad"),
            "webcam": l.get_bool("webcam"),
            # string keys in capabilities
            "modem": l.get_string("modem", default=""),
            "power": l.get_string("power", default=None),
            "storage": l.get_string("storage", default=None),
            "telephony": l.get_string("telephony", default=""),
            # enum keys in capabilities
            "carrier": l.get_enum("carrier", prefix="CARRIER_"),
        },
        # peripherals substructure
        "peripherals": {
            "audioBoard": l.get_bool("audio_board"),
            "audioBox": l.get_bool("audio_box"),
            "audioLoopbackDongle": l.get_bool("audio_loopback_dongle"),
            "chameleon": l.get_bool("chameleon"),
            "chameleonType": l.get_enum("chameleon", prefix="CHAMELEON_TYPE_"),
            "conductive": l.get_bool("conductive"),
            "huddly": l.get_bool("huddly"),
            "mimo": l.get_bool("mimo"),
            "servo": l.get_bool("servo"),
            "stylus": l.get_bool("stylus"),
            "wificell": l.get_bool("wificell"),
        },
        # test hints substructure
        "testCoverageHints": {
            "chaosDut": l.get_bool("chaos_dut"),
            "chromesign": l.get_bool("chromesign"),
            "hangoutApp": l.get_bool("hangout_app"),
            "meetApp": l.get_bool("meet_app"),
            "recoveryTest": l.get_bool("recovery_test"),
            "testAudiojack": l.get_bool("test_audio_jack"),
            "testHdmiaudio": l.get_bool("test_hdmiaudio"),
            "testUsbprinting": l.get_bool("test_usbprinting"),
            "usbDetect": l.get_bool("usb_detect"),
        },
    }
