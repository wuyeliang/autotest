from __future__ import unicode_literals
from __future__ import print_function
import sys
import json

# Source of truth is DUTPool enum at
# https://cs.chromium.org/chromium/infra/go/src/infra/libs/skylab/inventory/device.proto
MANAGED_POOLS = {
    "cq": "DUT_POOL_CQ",
    "bvt": "DUT_POOL_BVT",
    "suites": "DUT_POOL_SUITES",
    "cts": "DUT_POOL_CTS",
    "cts-perbuild": "DUT_POOL_CTS_PERBUILD",
    "continuous": "DUT_POOL_CONTINUOUS",
    "arc-presubmit": "DUT_POOL_ARC_PRESUBMIT",
    "quota": "DUT_POOL_QUOTA",
}


VIDEO_ACCELERATION_WHITELIST = {
    "VIDEO_ACCELERATION_H264",
    "VIDEO_ACCELERATION_ENC_H264",
    "VIDEO_ACCELERATION_VP8",
    "VIDEO_ACCELERATION_ENC_VP8",
    "VIDEO_ACCELERATION_VP9",
    "VIDEO_ACCELERATION_ENC_VP9",
    "VIDEO_ACCELERATION_VP9_2",
    "VIDEO_ACCELERATION_ENC_VP9_2",
    "VIDEO_ACCELERATION_H265",
    "VIDEO_ACCELERATION_ENC_H265",
    "VIDEO_ACCELERATION_MJPG",
    "VIDEO_ACCELERATION_ENC_MJPG",
}



def _normalize_pools(l):
    """take in the list of pools and distribute them between criticalPools and
    self_serve_pools"""
    pools = l.get_all_strings("pool")
    out = {"criticalPools": [], "self_serve_pools": []}
    for pool in pools:
        if pool in MANAGED_POOLS:
            # convert name to prototype enum for skylab-managed pools
            out["criticalPools"].append(MANAGED_POOLS[pool])
        else:
            # for unmanaged pools preserve the name
            out["self_serve_pools"].append(pool)
    #TODO(gregorynisbet): reject empty pools too.
    if len(out["criticalPools"]) > 1:
        sys.stderr.write("multiple critical pools %s\n" % pools)
        out["criticalPools"] = ["DUT_POOL_SUITES"]
    return out


def _get_chameleon(l):
    out = l.get_enum("chameleon", prefix="CHAMELEON_TYPE_")
    # send CHAMELEON_TYPE_['HDMI'] -> CHAMELEON_TYPE_HDMI
    out = "".join(ch for ch in out if ch not in "[']")
    if out == "CHAMELEON_TYPE_":
        return None
    good_val = False
    for ch in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMOPQRSTUVWXYZ0123456789":
        if out.startswith("CHAMELEON_TYPE_" + ch):
            good_val = True
    if good_val:
        return out
    else:
        return None


EC_TYPE_ATEST_TO_SK = {
    "cros": "EC_TYPE_CHROME_OS",
}

REQUIRED_LABELS = ["board", "model", "sku", "brand"]


class SkylabMissingLabelException(Exception):
    pass


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
        """get the boolean keys beginning with a certain prefix.

        Takes time proportional to the number of boolean keys.
        """
        for x in self.bools:
            if x.startswith(prefix):
                yield x


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


def _cts_cpu(l):
    out = []
    for abi in ["cts_cpu_x86", "cts_cpu_arm"]:
        if l.get_bool(abi):
            out.append(abi.upper())
    return out


def _os_type(l):
    """Get the operating system type"""
    return l.get_enum("os", prefix="OS_TYPE_")

def _ec_type(l):
    """Get the ec type."""
    name = l.get_string("ec")
    return EC_TYPE_ATEST_TO_SK.get(name, "EC_TYPE_INVALID")


def _video_acceleration(l):
    """produce a list of enums corresponding

    to the video_acc_ keys in the atest format
    """
    out = []
    for prefix in ["video_acc", "hw_video_acc"]:
        for key in l.bool_keys_starting_with(prefix=prefix):
            _, delim, suffix = key.rpartition("video_acc_")
            assert delim == "video_acc_"
            new_label = "VIDEO_ACCELERATION" + "_" + suffix.upper()
            if new_label in VIDEO_ACCELERATION_WHITELIST:
                out.append(new_label)
    return out


def _platform(l):
    return l.get_string("platform") or l.get_string("Platform")


def validate_required_fields_for_skylab(skylab_fields):
    """Does 'skylab_fields' have all required fields to add a DUT?

    Throw a SkylabMissingLabelException if any mandatory field is not present

    @param skylab_fields : a DUT description to be handed to 'skylab add-dut'
    @returns: Nothing
    """
    try:
        labels = skylab_fields["common"]["labels"]
    except (KeyError, TypeError, ValueError):
        raise ValueError(
            'skylab_fields["common"]["labels"] = { ... } is not present')
    for label in REQUIRED_LABELS:
        if label not in labels or labels[label] is None:
            raise SkylabMissingLabelException(label)
    return


def process_labels(labels, platform):
    """produce a JSON object of the kind accepted by skylab add-dut

    for the labels from autotest
    """
    l = Labels(labels)

    pools = _normalize_pools(l)

    # The enum-type keys below default to None
    # except for 'telephony' and 'modem', which default to ''
    # This is intentional.
    # This function will always return a json-like Python data object,
    # even in cases where some normally required fields are missing.
    # The explicit None is there as an explicit placeholder.
    out = {
        # boolean keys in label
        "arc": l.get_bool("arc"),
        # string keys in label
        "board": l.get_string("board", default=None),
        "brand": l.get_string("brand-code", default=None),
        "cr50Phase": _cr50_phase(l),
        "hwidSku": l.get_string("sku", default=None),
        "model": l.get_string("model", default=None),
        "platform": platform,
        "referenceDesign": l.get_string("reference_design"),
        # NOTE: the autotest label corresponding to "sku" is
        # "device-sku", not "sku"
        "sku": l.get_string("device-sku", default=None),
        # enum keys
        "ecType": _ec_type(l),
        "osType": _os_type(l),
        "phase": l.get_enum("phase", prefix="PHASE_"),
        # list of enum keys
        "criticalPools": pools["criticalPools"],
        "ctsAbi": _cts_abi(l),
        "ctsCpu": _cts_cpu(l),
        # list of string keys
        "self_serve_pools": pools["self_serve_pools"],
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
            "graphics": l.get_string("graphics", default=None),
            "gpuFamily": l.get_string("gpu_family", default=None),
            "modem": l.get_string("modem", default=""),
            "power": l.get_string("power", default=None),
            "storage": l.get_string("storage", default=None),
            "telephony": l.get_string("telephony", default=""),
            # enum keys in capabilities
            "carrier": l.get_enum("carrier", prefix="CARRIER_"),
            # video acceleration is its own thing.
            "videoAcceleration": _video_acceleration(l),
        },
        # peripherals substructure
        "peripherals": {
            "audioBoard": l.get_bool("audio_board"),
            "audioBox": l.get_bool("audio_box"),
            "audioLoopbackDongle": l.get_bool("audio_loopback_dongle"),
            "chameleon": l.get_bool("chameleon"),
            "chameleonType": _get_chameleon(l),
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

    if not out["criticalPools"]:
        del out["criticalPools"]

    if not out["self_serve_pools"]:
        del out["self_serve_pools"]

    return out



# accepts: string possibly in camelCase
# returns: string in snake_case
def to_snake_case(str):
    out = []
    for i, x in enumerate(str):
        if i == 0:
            out.append(x.lower())
            continue
        if x.isupper():
            out.append("_")
            out.append(x.lower())
        else:
            out.append(x.lower())
    return "".join(out)


def write(*args, **kwargs):
    print(*args, sep="", end="", **kwargs)

def writeln(*args, **kwargs):
    print(*args, sep="", end="\n", **kwargs)


# accepts: key, value, indentation level
# returns: nothing
# emits: textual protobuf format, best effort
def print_textpb_keyval(key, val, level=0):
    # repeated field, repeat the key in every stanza
    if isinstance(val, (list, tuple)):
        for x in val:
            # TODO(gregorynisbet): nested lists?
            print_textpb_keyval(to_snake_case(key), x, level=level)
    # if the value is a dictionary, don't print :
    elif isinstance(val, dict):
        write((level * " "), to_snake_case(key), " ")
        print_textpb(val, level=level)        
    else:
        write((level * " "), to_snake_case(key), ":", " ")
        print_textpb(val, level=0)


            


# accepts: obj, indentation level
# returns: nothing
# emits: textual protobuf format, best effort
def print_textpb(obj, level=0):
    # not sure what we want for None
    # an empty string seems like a good choice
    if obj is None:
        writeln((level * " "), '""')
    elif isinstance(obj, (int, long, float, bool)):
        writeln((level * " "), json.dumps(obj))
    elif isinstance(obj, (bytes, unicode)):
        # guess that something is not an enum if it
        # contains at least one lowercase letter or a space
        # or does not contain an underscore
        is_enum = True
        for ch in obj:
            if ch.islower() or ch == " ":
                is_enum = False
                break
        # check for the underscore
        is_enum = is_enum and "_" in obj
        if is_enum:
            writeln((level * " "), obj)
        else:
            writeln((level * " "), json.dumps(obj))
    elif isinstance(obj, dict):
        writeln("{")
        for key in sorted(obj):
            print_textpb_keyval(key=key, val=obj[key], level=(2 + level))
        writeln((level * " "), "}")
    elif isinstance(obj, (list, tuple)):
        raise RuntimeError("No sequences on toplevel")
    else:
        raise RuntimeError("Unsupported type (%s)" % type(obj))
