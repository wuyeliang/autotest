import operator
import xmlrpclib


NO_ARGS = tuple()
ONE_INT_ARG = (1, )
ONE_STR_ARG = ("foo", )

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
                    "software_reboot",
                    "get_platform_name",
                    "dev_tpm_present",
                    "get_root_dev",
                    "get_root_part",
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
        ]
    },
    {
        "category_name": "host",
        "test_cases": []
    },
    {
        "category_name": "bios",
        "test_cases": [
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
        ],
    },
    {
        "category_name": "ec",
        "test_cases": []
    },
    {
        "category_name": "kernel",
        "test_cases": []
    },
    {
        "category_name": "tpm",
        "test_cases": []
    },
    {
        "category_name": "cgpt",
        "test_cases": []
    },
    {
        "category_name": "updater",
        "test_cases": []
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
