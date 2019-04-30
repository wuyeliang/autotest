import xmlrpclib

NO_ARGS = tuple()
ONE_INT_ARG = (1, )
ONE_STR_ARG = ("foo", )
RPC_CATEGORIES = [
    {
        "category_name": "system",
        "rpc_methods": [
            {
                "method_name": "is_available",
                "passing_args": [NO_ARGS],
                "failing_args": [ONE_INT_ARG, ONE_STR_ARG],
            },
            {
                "method_name": "has_host",
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
                "method_name": "software_reboot",
                "passing_args": [NO_ARGS],
                "failing_args": [ONE_INT_ARG, ONE_STR_ARG],
            },
            {
                "method_name": "get_platform_name",
                "passing_args": [NO_ARGS],
                "failing_args": [ONE_INT_ARG, ONE_STR_ARG],
            },
            {
                "method_name": "dev_tpm_present",
                "passing_args": [NO_ARGS],
                "failing_args": [ONE_INT_ARG, ONE_STR_ARG],
            },
            {
                "method_name": "get_root_dev",
                "passing_args": [NO_ARGS],
                "failing_args": [ONE_INT_ARG, ONE_STR_ARG],
            },
            {
                "method_name": "get_root_part",
                "passing_args": [NO_ARGS],
                "failing_args": [ONE_INT_ARG, ONE_STR_ARG],
            },
        ]
    },
    {
        "category_name": "host",
        "rpc_methods": []
    },
    {
        "category_name": "bios",
        "rpc_methods": []
    },
    {
        "category_name": "ec",
        "rpc_methods": []
    },
    {
        "category_name": "kernel",
        "rpc_methods": []
    },
    {
        "category_name": "tpm",
        "rpc_methods": []
    },
    {
        "category_name": "cgpt",
        "rpc_methods": []
    },
    {
        "category_name": "updater",
        "rpc_methods": []
    },
    {
        "category_name": "rootfs",
        "rpc_methods": [
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