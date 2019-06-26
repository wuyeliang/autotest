import operator
import xmlrpclib

from autotest_lib.client.common_lib.cros import chip_utils


NO_ARGS = tuple()
ONE_INT_ARG = (1, )
ONE_STR_ARG = ("foo", )
SAMPLE_FILE = "/tmp/foo"
CHIP_FW_NAMES = (chip.fw_name for chip in chip_utils.chip_id_map.itervalues())
SAMPLE_CGPT_A = {
    "UUID": "93EF7B23-606B-014B-A10C-E9D7CF53DFD3",
    "successful": 1,
    "partition": 2,
    "priority": 1,
    "tries": 0,
    "Type": "ChromeOS kernel",
}
SAMPLE_CGPT_B = {
    "UUID": "C6604D6B-5563-EE4E-9915-0C50530B158A",
    "successful": 0,
    "partition": 4,
    "priority": 0,
    "tries": 15,
    "Type": "ChromeOS kernel",
}

"""
RPC_CATEGORIES contains all the test cases for our RPC tests.
Each element of RPC_CATEGORIES must be a dict containing the following keys:

@key category_name: A string naming the RPC category, such as bios or kernel.
@key test_cases: A list of test cases, each of which must be a dict containing
                 the following keys:
    @key method_name (optional): A string naming an RPC method within
                                 this category. Either this key or method_names
                                 is required (but not both).
    @key method_names (optional): An array of strings naming RPC methods within
                                  this category. Either this key or method_name
                                  is required (but not both).
    @key passing_args: A list of tuples, each of which could be unpacked and
                       then passed into the RPC method as a valid set of
                       parameters. Each tuple might contain instances of
                       operator.itemgetter. If so, those instances will be
                       replaced with values from firmware_FAFTRPC._stored_values
                       before being passed into the RPC method.
    @key failing_args: A list of tuples, each of which could be unpacked and
                       then passed into the RPC method as a set of parameters
                       which should yield an RPC error. Each tuple might contain
                       instances of operator.itemgetter. If so, those instances
                       will be replaced with values from
                       firmware_FAFTRPC._stored_values before being passed into
                       the RPC method.
    @key silence_result: Normally, the RPC return value is logged. However, if
                         this key is truthy, then the result is not logged.
    @key allow_error_msg (optional): String representing a regex pattern.
                                     If the RPC method is called with a
                                     passing_args tuple, but it yields an RPC
                                     error whose message is matched by
                                     re.search(allow_error_msg, error_msg),
                                     then the test will be considered a pass.
    @key store_result_as (optional): String. If this field is specified, then
                                     the result from the RPC call will be stored
                                     in firmware_FAFTRPC._stored_values. This
                                     allows us to later reference the result
                                     via an operator.itemgetter, as described
                                     above in the docstrings for passing_args
                                     and failing_args.

"""
RPC_CATEGORIES = [
    {
        "category_name": "System",
        "test_cases": [
            {
                "method_names": [
                    "IsAvailable",
                    "HasHost",
                    "GetPlatformName",
                    "DevTpmPresent",
                    "GetRootDev",
                    "GetRootPart",
                    "GetFwVboot2",
                    "RequestRecoveryBoot",
                    "IsRemovableDeviceBoot",
                    "GetInternalDevice",
                ],
                "passing_args": [NO_ARGS],
                "failing_args": [ONE_INT_ARG, ONE_STR_ARG],
            },
            {
                "method_name": "WaitForClient",
                "passing_args": [ONE_INT_ARG],
                "failing_args": [NO_ARGS, ONE_STR_ARG],
                "allow_error_msg":
                    "'LocalShell' object has no attribute 'wait_for_device'",
            },
            {
                "method_name": "WaitForClientOffline",
                "passing_args": [ONE_INT_ARG],
                "failing_args": [NO_ARGS, ONE_STR_ARG],
                "allow_error_msg":
                    "'LocalShell' object has no attribute 'wait_for_no_device'",
            },
            {
                "method_name": "DumpLog",
                "passing_args": [
                    NO_ARGS,
                    (True, ),
                    (False, ),
                ],
                "failing_args": [
                    (True, False),
                ],
                "expected_return_type": str,
                "silence_result": True,
            },
            {
                "method_names": [
                    "RunShellCommand",
                    "RunShellCommandGetStatus",
                ],
                "passing_args": [
                    ("ls", ),
                ],
                "failing_args": [
                    NO_ARGS,
                    ("ls", "-l", 'foo'),
                ],
            },
            {
                "method_name": "RunShellCommandCheckOutput",
                "passing_args": [
                    ("ls -l", "total"),
                ],
                "failing_args": [
                    NO_ARGS,
                ],
            },
            {
                "method_name": "RunShellCommandGetOutput",
                "passing_args": [
                    ("ls -l", True),
                ],
                "failing_args": [
                    NO_ARGS,
                ],
            },
            {
                "method_name": "GetCrossystemValue",
                "passing_args": [
                    ("fwid", ),
                ],
                "failing_args": [NO_ARGS],
            },
            {
                "method_name": "SetTryFwB",
                "passing_args": [
                    NO_ARGS,
                    (1, ),
                ],
                "failing_args": [
                    (1, 1),
                ],
            },
            {
                "method_name": "SetFwTryNext",
                "passing_args": [
                    ("A", ),
                    ("A", 1),
                ],
                "failing_args": [
                    NO_ARGS,
                    ("A", 1, "B"),
                ],
            },
            {
                "method_name": "GetDevBootUsb",
                "passing_args": [NO_ARGS],
                "failing_args": [ONE_INT_ARG, ONE_STR_ARG],
                "store_result_as": "dev_boot_usb",
            },
            {
                "method_name": "SetDevBootUsb",
                "passing_args": [
                    (operator.itemgetter("dev_boot_usb"), ),
                ],
                "failing_args": [
                    NO_ARGS,
                    (True, False),
                ],
            },
            {
                "method_name": "CreateTempDir",
                "passing_args": [
                    NO_ARGS,
                    ONE_STR_ARG,
                ],
                "failing_args": [
                    ONE_INT_ARG,
                    ("foo", "bar"),
                ],
                "expected_return_type": str,
                "store_result_as": "temp_dir",
            },
            {
                "method_name": "RemoveFile",
                "passing_args": [
                    (SAMPLE_FILE, ),
                ],
                "failing_args": [
                    NO_ARGS,
                    (1, 2),
                ],
            },
            {
                "method_name": "RemoveDir",
                "passing_args":  [
                    (operator.itemgetter("temp_dir"), ),
                ],
                "failing_args": [
                    NO_ARGS,
                    (1, 2),
                ]
            },
            {
                "method_name": "CheckKeys",
                "passing_args": [
                    ([], ),
                    ([116], ),
                    ([28, 29, 32], ),
                ],
                "failing_args": [
                    NO_ARGS,
                    ([], [116]),
                ],
                "expected_return_type": int,
            },
        ]
    },
    {
        "category_name": "Host",
        "test_cases": [
            {
                "method_names": [
                    "RunShellCommand",
                    "RunShellCommandGetOutput",
                ],
                "passing_args": [
                    ("ls", ),
                ],
                "failing_args": [
                    NO_ARGS,
                    ("ls", "-l"),
                ],
                "allow_error_msg": "There is no host for DUT",
            },
        ]
    },
    {
        "category_name": "Bios",
        "test_cases": [
            {
                "method_names": [
                    "Reload",
                ],
                "passing_args": [NO_ARGS],
                "failing_args": [ONE_INT_ARG, ONE_STR_ARG]
            },
            {
                "method_name": "GetGbbFlags",
                "passing_args": [NO_ARGS],
                "failing_args": [ONE_INT_ARG, ONE_STR_ARG],
                "expected_return_type": int,
                "store_result_as": "gbb_flags",
            },
            {
                "method_name": "SetGbbFlags",
                "passing_args": [
                    (operator.itemgetter("gbb_flags"), ),
                ],
                "failing_args": [NO_ARGS],
            },
            {
                "method_name": "GetPreambleFlags",
                "passing_args": [
                    ("a", ),
                ],
                "failing_args": [NO_ARGS, ONE_INT_ARG],
                "store_result_as": "preamble_flags",
            },
            {
                "method_name": "SetPreambleFlags",
                "passing_args": [
                    ("a", operator.itemgetter("preamble_flags"), ),
                ],
                "failing_args": [
                    NO_ARGS,
                    ONE_INT_ARG,
                    ONE_STR_ARG,
                    ("c", operator.itemgetter("preamble_flags"), ),
                ],
            },
            {
                "method_names": [
                    "GetBodySha",
                    "GetSigSha",
                    "GetVersion",
                    "GetDatakeyVersion",
                    "GetKernelSubkeyVersion",
                ],
                "passing_args": [
                    ("a", ),
                    ("b", ),
                ],
                "failing_args": [
                    NO_ARGS,
                    ONE_INT_ARG,
                    (("a", "b"), ),
                    ("c", ),
                ]
            },
            {
                "method_names": [
                    "CorruptSig",
                    "RestoreSig",
                    "CorruptBody",
                    "RestoreBody",
                    "MoveVersionBackward",
                    "MoveVersionForward",
                ],
                "passing_args": [
                    ("a", ),
                    ("b", ),
                ],
                "failing_args": [
                    NO_ARGS,
                    ONE_INT_ARG,
                    ("c", ),
                ]
            },
            {
                "method_names": [
                    "DumpWhole",
                    "WriteWhole",
                ],
                "passing_args": [
                    (SAMPLE_FILE, ),
                ],
                "failing_args": [NO_ARGS],
            },
        ],
    },
    {
        "category_name": "Ec",
        "test_cases": [
            {
                "method_names": [
                    "Reload",
                    "GetVersion",
                    "GetActiveHash",
                    "IsEfs",
                ],
                "passing_args": [NO_ARGS],
                "failing_args": [ONE_INT_ARG, ONE_STR_ARG],
                "allow_error_msg": "list index out of range",
            },
            {
                "method_names": [
                    "DumpWhole",
                    "WriteWhole",
                    "DumpFirmware"
                ],
                "passing_args": [
                    (SAMPLE_FILE, ),
                ],
                "failing_args": [NO_ARGS],
            },
            {
                "method_name": "CorruptBody",
                "passing_args": [
                    ("rw", ),
                ],
                "failing_args": [
                    NO_ARGS,
                    ONE_INT_ARG,
                    ("ro", ),
                    ("rw", "rw"),
                ],
            },
            {
                "method_name": "SetWriteProtect",
                "passing_args": [
                    (True, ),
                    (False, ),
                ],
                "failing_args": [
                    NO_ARGS,
                    (True, False),
                ]
            },
            {
                "method_name": "CopyRw",
                "passing_args": [
                    ("rw", "rw"),
                ],
                "failing_args": [
                    NO_ARGS,
                    ("rw", "ro"),
                    ("ro", "rw"),
                    ("rw", ),
                ],
            },
            {
                "method_name": "RebootToSwitchSlot",
                "passing_args": [NO_ARGS],
                "failing_args": [ONE_INT_ARG, ONE_STR_ARG],
                "allow_error_msg": "ShellError",
            },
        ],
    },
    {
        "category_name": "Kernel",
        "test_cases": [
            {
                "method_names": [
                    "CorruptSig",
                    "RestoreSig",
                    "MoveVersionBackward",
                    "MoveVersionForward",
                ],
                "passing_args": [
                    ("a", ),
                    ("b", ),
                ],
                "failing_args": [
                    NO_ARGS,
                    ONE_INT_ARG,
                    ("c", ),
                    ("a", "b"),
                ],
            },
            {
                "method_names": [
                    "GetVersion",
                    "GetDatakeyVersion",
                    "GetSha",
                ],
                "passing_args": [
                    ("a", ),
                    ("b", ),
                ],
                "failing_args": [
                    (("a", "b"), ),
                    ("c", ),
                    NO_ARGS,
                    ONE_INT_ARG,
                ],
            },
            {
                "method_name": "DiffAB",
                "passing_args": [NO_ARGS],
                "failing_args": [
                    ONE_INT_ARG,
                    ONE_STR_ARG,
                ],
                "expected_return_type": bool,
            },
            {
                "method_name": "ResignWithKeys",
                "passing_args": [
                    ("a", ),
                    ("b", ),
                    ("b", SAMPLE_FILE),
                ],
                "failing_args": [
                    (("a", "b"), ),
                    ("c", ),
                    NO_ARGS,
                    ONE_INT_ARG,
                ],
            },
            {
                "method_names": [
                    "Dump",
                    "Write",
                ],
                "passing_args": [
                    ("a", SAMPLE_FILE),
                    ("b", SAMPLE_FILE),
                ],
                "failing_args": [
                    (("a", "b"), SAMPLE_FILE),
                    ("c", SAMPLE_FILE),
                    ("a", ),
                    NO_ARGS,
                ]
            }
        ],
    },
    {
        "category_name": "Tpm",
        "test_cases": [
            {
                "method_names": [
                    "GetFirmwareVersion",
                    "GetFirmwareDatakeyVersion",
                    "GetKernelVersion",
                    "GetKernelDatakeyVersion",
                    "StopDaemon",
                    "RestartDaemon",
                ],
                "passing_args": [NO_ARGS],
                "failing_args": [ONE_INT_ARG, ONE_STR_ARG],
            },
        ]
    },
    {
        "category_name": "Cgpt",
        "test_cases": [
            {
                "method_name": "GetAttributes",
                "passing_args": [NO_ARGS],
                "failing_args": [
                    ONE_INT_ARG,
                    ONE_STR_ARG,
                ],
            },
            {
                "method_name": "SetAttributes",
                "passing_args": [
                    NO_ARGS,
                    (SAMPLE_CGPT_A, ),
                    (None, SAMPLE_CGPT_B),
                    (SAMPLE_CGPT_A, SAMPLE_CGPT_B),
                    (None, None),
                ],
                "failing_args": [
                    (None, None, None),
                ],
            }
        ]
    },
    {
        "category_name": "Updater",
        "test_cases": [
            # TODO (gredelston/dgoyette):
            # Uncomment the methods which write to flash memory,
            # once we are able to set the firmware_updater to "emulate" mode.
            {
                "method_names": [
                    "Cleanup",
                    "StopDaemon",
                    "StartDaemon",
                    # "ModifyEcidAndFlashToBios",
                    "GetEcHash",
                    "ResetShellball",
                    # "RunFactoryInstall",
                    # "RunRecovery",
                    "CbfsSetupWorkDir",
                    # "CbfsSignAndFlash",
                    "GetTempPath",
                    "GetKeysPath",
                    "GetWorkPath",
                    "GetBiosRelativePath",
                    "GetEcRelativePath",
                ],
                "passing_args": [
                    NO_ARGS,
                ],
                "failing_args": [
                    ONE_INT_ARG,
                    ONE_STR_ARG,
                ],
                "allow_error_msg": (r"command cp -rf /var/tmp/faft/autest/work "
                                    r"/var/tmp/faft/autest/cbfs failed"),
            },
            {
                "method_name": "GetSectionFwid",
                "passing_args": [
                    NO_ARGS,
                    ("bios", ),
                    ("ec", ),
                    ("bios", "b"),
                    ("ec", "rw"),
                ],
                "failing_args": [
                    ("foo", ),
                    ("bios", "foo"),
                    ("ec", "foo"),
                ],
                "expected_return_type": str,
                "allow_error_msg": "is empty",
            },
            {
                "method_names": [
                    "GetAllFwids",
                    "GetAllInstalledFwids",
                ],
                "passing_args": [
                    NO_ARGS,
                    ("bios", ),
                    ("ec", ),
                ],
                "failing_args": [
                    ("foo", ),
                ],
                "expected_return_type": dict,
                "allow_error_msg": r"is already modified|is empty",
            },
            {
                "method_name": "ModifyFwids",
                "passing_args": [
                    NO_ARGS,
                    ("bios", ),
                    ("ec", ),
                    ("bios", ("b", "rec")),
                    ("ec", ("rw_b", )),
                ],
                "failing_args": [
                    ("foo", ),
                    ("bios", ("foo", )),
                    ("ec", ("foo", )),
                ],
                "expected_return_type": dict,
                "allow_error_msg": r"is already modified|is empty",
            },
            {
                "method_name": "ResignFirmware",
                "passing_args": [
                    ONE_INT_ARG,
                    (None, ),
                ],
                "failing_args": [
                    NO_ARGS,
                    ONE_STR_ARG,
                    (1, 1),
                ],
            },
            {
                "method_names": [
                    "RepackShellball",
                    "ExtractShellball",
                ],
                "passing_args": [
                    NO_ARGS,
                    ("test", ),
                    (None, ),
                ],
                "failing_args": [
                    ("foo", "bar"),
                ]
            },
            {
                "method_name": "RunFirmwareupdate",
                "passing_args": [
                    ("autoupdate", ),
                    ("recovery", ),
                    ("bootok", ),
                    ("factory_install", ),
                    ("bootok", None),
                    ("bootok", "foo"),
                    ("bootok", "foo", ()),
                    ("bootok", "foo", ("--noupdate_ec", "--wp=1")),
                ],
                "failing_args": [NO_ARGS],
            },
            {
                "method_names": [
                    "RunAutoupdate",
                    "RunBootok",
                ],
                "passing_args": [ONE_STR_ARG],
                "failing_args": [
                    NO_ARGS,
                    ("foo", "bar"),
                ],
            },
            {
                "method_names": [
                    "CbfsExtractChip",
                    "CbfsGetChipHash",
                    "CbfsReplaceChip",
                ],
                "passing_args": [
                    (chip_fw_name, ) for chip_fw_name in CHIP_FW_NAMES
                ],
                "failing_args": [
                    NO_ARGS,
                    ONE_INT_ARG,
                ],
                "allow_error_msg": "cbfstool /var/tmp/faft/"
            },
            {
                "method_name": "CopyBios",
                "passing_args": [
                    ('/tmp/fake-bios.bin', )
                ],
                "failing_args": [
                    NO_ARGS,
                    ('/tmp/fake-bios.bin', "foo")
                ],
                "expected_return_type": str
            },
        ]
    },
    {
        "category_name": "Rootfs",
        "test_cases": [
            {
                "method_name": "VerifyRootfs",
                "passing_args": [
                    ("A", ),
                    ("B", ),
                ],
                "failing_args": [
                    NO_ARGS,
                    ONE_INT_ARG,
                    ("C", ),
                    ("A", "B"),
                ],
            },
        ]
    }
]
RPC_ERRORS = (
    xmlrpclib.Fault,
    # grpc.RpcError, # TODO (gredelston): Un-comment when grpc is available
)
