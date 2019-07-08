from autotest_lib.client.cros.faft import rpc_functions


class RPCProxy(object):
    """Proxy to the FAFT RPC server on DUT.

    This stub class (see PEP-484) tells IDEs about the categories and methods
    that are available on RPCProxy via __getattr__.
    """

    Bios: rpc_functions.BiosServicer
    Cgpt: rpc_functions.CgptServicer
    Ec: rpc_functions.EcServicer
    Host: rpc_functions.HostServicer
    Kernel: rpc_functions.KernelServicer
    Rootfs: rpc_functions.RootfsServicer
    RpcSettings: rpc_functions.RpcSettingsServicer
    System: rpc_functions.SystemServicer
    Tpm: rpc_functions.TpmServicer
    Updater: rpc_functions.UpdaterServicer
