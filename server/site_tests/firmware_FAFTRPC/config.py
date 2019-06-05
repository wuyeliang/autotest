import operator
import xmlrpclib


NO_ARGS = tuple()
ONE_INT_ARG = (1, )
ONE_STR_ARG = ("foo", )
SAMPLE_FILE = "/tmp/foo"

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
    @key allow_error_msg (optional): String. If the RPC method is called with a
                                     passing_args tuple, but it yields an RPC
                                     error whose message contains this string,
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
        "category_name": "system",
        "test_cases": [
            {
                "method_names": [
                    "is_available",
                    "has_host",
                    "get_platform_name",
                    "dev_tpm_present",
                    "get_root_dev",
                    "get_root_part",
                    "get_fw_vboot2",
                    "request_recovery_boot",
                    "is_removable_device_boot",
                    "get_internal_device",
                ],
                "passing_args": [NO_ARGS],
                "failing_args": [ONE_INT_ARG, ONE_STR_ARG],
            },
            {
                "method_name": "wait_for_client",
                "passing_args": [ONE_INT_ARG],
                "failing_args": [NO_ARGS, ONE_STR_ARG],
                "allow_error_msg":
                    "'LocalShell' object has no attribute 'wait_for_device'",
            },
            {
                "method_name": "wait_for_client_offline",
                "passing_args": [ONE_INT_ARG],
                "failing_args": [NO_ARGS, ONE_STR_ARG],
                "allow_error_msg":
                    "'LocalShell' object has no attribute 'wait_for_no_device'",
            },
            {
                "method_name": "dump_log",
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
                    "run_shell_command",
                    "run_shell_command_get_output",
                    "run_shell_command_get_status",
                ],
                "passing_args": [
                    ("ls", ),
                ],
                "failing_args": [
                    NO_ARGS,
                    ("ls", "-l"),
                ],
            },
            {
                "method_name": "get_crossystem_value",
                "passing_args": [
                    ("fwid", ),
                ],
                "failing_args": [NO_ARGS],
            },
            {
                "method_name": "set_try_fw_b",
                "passing_args": [
                    NO_ARGS,
                    (1, ),
                ],
                "failing_args": [
                    (1, 1),
                ],
            },
            {
                "method_name": "set_fw_try_next",
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
                "method_name": "get_dev_boot_usb",
                "passing_args": [NO_ARGS],
                "failing_args": [ONE_INT_ARG, ONE_STR_ARG],
                "store_result_as": "dev_boot_usb",
            },
            {
                "method_name": "set_dev_boot_usb",
                "passing_args": [
                    (operator.itemgetter("dev_boot_usb"), ),
                ],
                "failing_args": [
                    NO_ARGS,
                    (True, False),
                ],
            },
            {
                "method_name": "create_temp_dir",
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
                "method_name": "remove_file",
                "passing_args": [
                    (SAMPLE_FILE, ),
                ],
                "failing_args": [
                    NO_ARGS,
                    (1, 2),
                ],
            },
            {
                "method_name": "remove_dir",
                "passing_args":  [
                    (operator.itemgetter("temp_dir"), ),
                ],
                "failing_args": [
                    NO_ARGS,
                    (1, 2),
                ]
            },
            {
                "method_name": "check_keys",
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
        "category_name": "host",
        "test_cases": [
            {
                "method_names": [
                    "run_shell_command",
                    "run_shell_command_get_output",
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
        "category_name": "bios",
        "test_cases": [
            {
                "method_names": [
                    "reload",
                ],
                "passing_args": [NO_ARGS],
                "failing_args": [ONE_INT_ARG, ONE_STR_ARG]
            },
            {
                "method_name": "get_gbb_flags",
                "passing_args": [NO_ARGS],
                "failing_args": [ONE_INT_ARG, ONE_STR_ARG],
                "expected_return_type": int,
                "store_result_as": "gbb_flags",
            },
            {
                "method_name": "set_gbb_flags",
                "passing_args": [
                    (operator.itemgetter("gbb_flags"), ),
                ],
                "failing_args": [NO_ARGS],
            },
            {
                "method_name": "get_preamble_flags",
                "passing_args": [
                    ("a", ),
                ],
                "failing_args": [NO_ARGS, ONE_INT_ARG],
                "store_result_as": "preamble_flags",
            },
            {
                "method_name": "set_preamble_flags",
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
                    "get_body_sha",
                    "get_sig_sha",
                    "get_version",
                    "get_datakey_version",
                    "get_kernel_subkey_version",
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
                    "corrupt_sig",
                    "restore_sig",
                    "corrupt_body",
                    "restore_body",
                    "move_version_backward",
                    "move_version_forward",
                ],
                "passing_args": [
                    ("a", ),
                    ("b", ),
                    ( ("a", "b"), ),
                ],
                "failing_args": [
                    NO_ARGS,
                    ONE_INT_ARG,
                    ("c", ),
                ]
            },
            {
                "method_names": [
                    "dump_whole",
                    "write_whole",
                ],
                "passing_args": [
                    (SAMPLE_FILE, ),
                ],
                "failing_args": [NO_ARGS],
            },
        ],
    },
    {
        "category_name": "ec",
        "test_cases": [
            {
                "method_names": [
                    "reload",
                    "get_version",
                    "get_active_hash",
                    "is_efs",
                ],
                "passing_args": [NO_ARGS],
                "failing_args": [ONE_INT_ARG, ONE_STR_ARG],
                "allow_error_msg": "list index out of range",
            },
            {
                "method_names": [
                    "dump_whole",
                    "write_whole",
                    "dump_firmware"
                ],
                "passing_args": [
                    (SAMPLE_FILE, ),
                ],
                "failing_args": [NO_ARGS],
            },
            {
                "method_name": "corrupt_body",
                "passing_args": [
                    ("rw", ),
                ],
                "failing_args": [
                    NO_ARGS,
                    ONE_INT_ARG,
                    ("ro", ),
                ],
            },
            {
                "method_name": "set_write_protect",
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
                "method_name": "copy_rw",
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
                "method_name": "reboot_to_switch_slot",
                "passing_args": [NO_ARGS],
                "failing_args": [ONE_INT_ARG, ONE_STR_ARG],
                "allow_error_msg": "ShellError",
            },
        ],
    },
    {
        "category_name": "kernel",
        "test_cases": [
            {
                "method_names": [
                    "corrupt_sig",
                    "restore_sig",
                    "move_version_backward",
                    "move_version_forward",
                ],
                "passing_args": [
                    ("a", ),
                    ("b", ),
                    (("a", "b"), )
                ],
                "failing_args": [
                    NO_ARGS,
                    ONE_INT_ARG,
                    ("c", ),
                ],
            },
            {
                "method_names": [
                    "get_version",
                    "get_datakey_version",
                    "get_sha",
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
                "method_name": "diff_a_b",
                "passing_args": [NO_ARGS],
                "failing_args": [
                    ONE_INT_ARG,
                    ONE_STR_ARG,
                ],
                "expected_return_type": bool,
            },
            {
                "method_name": "resign_with_keys",
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
                    "dump",
                    "write",
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
        "category_name": "tpm",
        "test_cases": [
            {
                "method_names": [
                    "get_firmware_version",
                    "get_firmware_datakey_version",
                    "get_kernel_version",
                    "get_kernel_datakey_version",
                    "stop_daemon",
                    "restart_daemon",
                ],
                "passing_args": [NO_ARGS],
                "failing_args": [ONE_INT_ARG, ONE_STR_ARG],
            },
        ]
    },
    {
        "category_name": "cgpt",
        "test_cases": [
            {
                "method_name": "get_attributes",
                "passing_args": [NO_ARGS],
                "failing_args": [
                    ONE_INT_ARG,
                    ONE_STR_ARG,
                ],
                "store_result_as": "cgpt_attributes",
            },
            {
                "method_name": "set_attributes",
                "passing_args": [
                    (operator.itemgetter("cgpt_attributes"), ),
                ],
                "failing_args": [NO_ARGS],
            }
        ]
    },
    {
        "category_name": "updater",
        "test_cases": [
            {
                "method_names": [
                    "get_fwid",
                    "modify_fwid",
                    "get_installed_fwid",
                ],
                "passing_args": [
                    NO_ARGS,
                    ("bios", "ro"),
                    ("bios", "a"),
                ],
                "failing_args": [
                    ("", ),
                    ("foo", ),
                    ("bios", ""),
                    ("bios", "foo"),
                ],
                "expected_return_type": str,
                "allow_error_msg": "is already modified",
            },
            {
                "method_names": [
                    "get_fwid",
                    "modify_fwid",
                    "get_installed_fwid",
                ],
                "passing_args": [
                    ("bios", ()),
                    ("bios", ("ro",)),
                    ("bios", ("ro", "a")),
                ],
                "failing_args": [
                    ("", ("ro",)),
                    ("bios", ("foo",)),
                    ("bios", ("foo", "bar")),
                ],
                "expected_return_type": dict,
                "allow_error_msg": "is already modified",
            },
            {
                "method_name": "copy_bios",
                "passing_args": [
                    ('/tmp/fake-bios.bin', )
                ],
                "failing_args": [
                    NO_ARGS,
                    ('/tmp/fake-bios.bin', "foo")
                ],
                "expected_return_type": str
            },
            {
                "method_name": "reset_shellball",
                "passing_args": [NO_ARGS],
                "failing_args": [ONE_INT_ARG, ONE_STR_ARG]
            }
        ]
    },
    {
        "category_name": "rootfs",
        "test_cases": [
            {
                "method_name": "verify_rootfs",
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
