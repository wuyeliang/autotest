import xmlrpclib

NO_ARGS = tuple()
ONE_INT_ARG = (1, )
ONE_STR_ARG = ("foo", )
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
        "test_cases": []
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
