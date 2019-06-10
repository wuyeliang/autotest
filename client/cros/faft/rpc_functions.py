# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Code to provide functions for FAFT tests.

These can be exposed via a xmlrpci server running on the DUT.
"""
import httplib
import os
import sys
import tempfile
import traceback
import xmlrpclib

from autotest_lib.client.cros.faft.utils import (
        cgpt_handler,
        os_interface,
        firmware_check_keys,
        firmware_updater,
        flashrom_handler,
        kernel_handler,
        rootfs_handler,
        tpm_handler,
)


class RPCRouter(object):
    """
    A class which routes RPC methods to the proper servicers.

    Firmware tests are able to call an RPC method via:
        FAFTClient.[category].[method_name](params)
    When XML-RPC is being used, the RPC server routes the called method to:
        RPCHandler._dispatch('[category].[method]', params)
    The method is then dispatched to a Servicer class.
    """

    def __init__(self, os_if):
        """Initialize the servicer for each category.

        @type os_if: os_interface.OSInterface
        """
        self.bios = BiosServicer(os_if)
        self.cgpt = CgptServicer(os_if)
        self.ec = EcServicer(os_if)
        self.host = HostServicer(os_if)
        self.kernel = KernelServicer(os_if)
        self.rootfs = RootfsServicer(os_if)
        self.rpc_settings = RpcSettingsServicer(os_if)
        self.system = SystemServicer(os_if)
        self.tpm = TpmServicer(os_if)
        self.updater = UpdaterServicer(os_if)

        self._rpc_servicers = {
                'Bios': self.bios,
                'Cgpt': self.cgpt,
                'Ec': self.ec,
                'Host': self.host,
                'Kernel': self.kernel,
                'RpcSettings': self.rpc_settings,
                'Rootfs': self.rootfs,
                'System': self.system,
                'Tpm': self.tpm,
                'Updater': self.updater
        }

        self._os_if = os_if

    def _report_error(self, fault_code, message, exc_info=None):
        """Raise the given RPC error text, including information about last
        exception from sys.exc_info().  The log file gets the traceback in text;
        the raised exception keeps the old traceback (but not in text).

        Note: this must be called right after the original exception, or it may
        report the wrong exception.

        @raise: xmlrpclib.Fault

        @param fault_code: the status code to use
        @param message: the string message to include before exception text
        @param exc_info: the tuple from sys.exc_info()
        @return the exception to raise

        @type fault_code: int
        @type message: str
        @type exc_info: bool
        @rtype: Exception
        """
        if exc_info:
            tb = None
            try:
                (exc_class, exc, tb) = sys.exc_info()

                tb_str = ''.join(
                        traceback.format_exception(exc_class, exc, tb))
                self._os_if.log('Error: %s.\n%s' % (message, tb_str.rstrip()))

                exc_str = ''.join(
                        traceback.format_exception_only(exc_class, exc))
                exc = xmlrpclib.Fault(
                        fault_code, '%s. %s' % (message, exc_str.rstrip()))
                raise exc, None, tb
            finally:
                del exc_info
                del tb
        else:
            self._os_if.log('Error: %s' % message)
            return xmlrpclib.Fault(fault_code, message)

    def _dispatch(self, called_method, params):
        """
        Send any RPC call to the appropriate servicer method.

        @param called_method: The method of FAFTClient that was called.
                              Should take the form 'category.method'.
        @param params: The arguments passed into the method.

        @type called_method: str
        @type params: tuple

        @raise: xmlrpclib.Fault (using http error codes for fault codes)
        """
        self._os_if.log('Called: %s%s' % (called_method, params))

        name_pieces = called_method.split('.')
        num_pieces = len(name_pieces)

        if num_pieces < 1:
            raise self._report_error(
                    httplib.BAD_REQUEST,
                    'RPC request is invalid (completely empty): "%s"' %
                    called_method)

        if num_pieces < 2:
            # must be category.func (maybe with .__str__)
            raise self._report_error(
                    httplib.BAD_REQUEST,
                    'RPC request is invalid (must have category.method format):'
                    ' "%s"' % called_method)

        method_name = name_pieces.pop()
        category = '.'.join(name_pieces)

        if (method_name.startswith('_')
                and method_name not in ('__str__', '__repr__', '__call__')):
            # *._private() or *.__special__()
            # Forbid early, to prevent seeing which methods exist.
            raise self._report_error(
                    httplib.FORBIDDEN,
                    'RPC method name is private: %s.[%s]' %
                    (category, method_name))

        if not method_name:
            # anything.()
            raise self._report_error(
                    httplib.BAD_REQUEST,
                    'RPC method name is empty: %s.[%s]' %
                    (category, method_name))

        if category in self._rpc_servicers:
            # system.func()
            holder = self._rpc_servicers[category]
            if not hasattr(holder, method_name):
                raise self._report_error(
                        httplib.NOT_FOUND,
                        'RPC method not found: %s.[%s]' %
                        (category, method_name))

        elif category:
            # invalid.func()
            raise self._report_error(
                    httplib.NOT_FOUND,
                    'RPC category not found: [%s].%s' %
                    (category, method_name))

        else:
            # .invalid()
            raise self._report_error(
                    httplib.BAD_REQUEST,
                    'RPC request is invalid (empty category name): [%s].%s' %
                    (category, method_name))

        try:
            method = getattr(holder, method_name)

        except AttributeError:
            raise self._report_error(
                    httplib.NOT_IMPLEMENTED,
                    'RPC method not found: "%s"' % called_method, exc_info=True)

        try:
            return method(*params)

        except Exception:
            raise self._report_error(
                    httplib.INTERNAL_SERVER_ERROR,
                    'RPC call failed: %s()' % called_method, exc_info=True)


class BiosServicer(object):
    """Class to service all BIOS RPCs"""

    def __init__(self, os_if):
        """
        @type os_if: os_interface.OSInterface
        """
        self._os_if = os_if

        # This attribute is accessed via a property, so it can load lazily
        # when actually used by the test.
        self._real_bios_handler = flashrom_handler.FlashromHandler(
                self._os_if, None, '/usr/share/vboot/devkeys', 'bios')

    @property
    def _bios_handler(self):
        """Return the BIOS flashrom handler, after initializing it if necessary

        @rtype: flashrom_handler.FlashromHandler
        """
        if not self._real_bios_handler.initialized:
            self._real_bios_handler.init()
        return self._real_bios_handler

    def Reload(self):
        """Reload the firmware image that may be changed."""
        self._bios_handler.new_image()

    def GetGbbFlags(self):
        """Get the GBB flags.

        @return: An integer of the GBB flags.
        """
        return self._bios_handler.get_gbb_flags()

    def SetGbbFlags(self, flags):
        """Set the GBB flags.

        @param flags: An integer of the GBB flags.
        """
        self._bios_handler.set_gbb_flags(flags, write_through=True)

    def GetPreambleFlags(self, section):
        """Get the preamble flags of a firmware section.

        @param section: A firmware section, either 'a' or 'b'.
        @return: An integer of the preamble flags.
        """
        return self._bios_handler.get_section_flags(section)

    def SetPreambleFlags(self, section, flags):
        """Set the preamble flags of a firmware section.

        @param section: A firmware section, either 'a' or 'b'.
        @param flags: An integer of preamble flags.
        """
        version = self.GetVersion(section)
        self._bios_handler.set_section_version(
                section, version, flags, write_through=True)

    def GetBodySha(self, section):
        """Get SHA1 hash of BIOS RW firmware section.

        @param section: A firmware section, either 'a' or 'b'.
        @return: A string of the body SHA1 hash.
        """
        return self._bios_handler.get_section_sha(section)

    def GetSigSha(self, section):
        """Get SHA1 hash of firmware vblock in section.

        @param section: A firmware section, either 'a' or 'b'.
        @return: A string of the sig SHA1 hash.
        """
        return self._bios_handler.get_section_sig_sha(section)

    def CorruptSig(self, section):
        """Corrupt the requested firmware section signature.

        @param section: A firmware section, either 'a' or 'b'.
        """
        self._bios_handler.corrupt_firmware(section)

    def RestoreSig(self, section):
        """Restore the previously corrupted firmware section signature.

        @param section: A firmware section, either 'a' or 'b'.
        """
        self._bios_handler.restore_firmware(section)

    def CorruptBody(self, section, corrupt_all=False):
        """Corrupt the requested firmware section body.

        @param section: A firmware section, either 'a' or 'b'.
        @param corrupt_all (optional): Corrupt all bytes of the fw section,
                                       rather than just one byte.
        """
        self._bios_handler.corrupt_firmware_body(section, corrupt_all)

    def RestoreBody(self, section):
        """Restore the previously corrupted firmware section body.

        @param section: A firmware section, either 'a' or 'b'.
        """
        self._bios_handler.restore_firmware_body(section)

    def _modify_version(self, section, delta):
        """Modify firmware version for the requested section, by adding delta.

        The passed in delta, a positive or a negative number, is added to the
        original firmware version.
        """
        original_version = self.GetVersion(section)
        new_version = original_version + delta
        flags = self._bios_handler.get_section_flags(section)
        self._os_if.log('Setting firmware section %s version from %d to %d' %
                        (section, original_version, new_version))
        self._bios_handler.set_section_version(
                section, new_version, flags, write_through=True)

    def MoveVersionBackward(self, section):
        """Decrement firmware version for the requested section."""
        self._modify_version(section, -1)

    def MoveVersionForward(self, section):
        """Increase firmware version for the requested section."""
        self._modify_version(section, 1)

    def GetVersion(self, section):
        """Retrieve firmware version of a section."""
        return self._bios_handler.get_section_version(section)

    def GetDatakeyVersion(self, section):
        """Return firmware data key version."""
        return self._bios_handler.get_section_datakey_version(section)

    def GetKernelSubkeyVersion(self, section):
        """Return kernel subkey version."""
        return self._bios_handler.get_section_kernel_subkey_version(section)

    def DumpWhole(self, bios_path):
        """Dump the current BIOS firmware to a file, specified by bios_path.

        @param bios_path: The path of the BIOS image to be written.
        """
        self._bios_handler.dump_whole(bios_path)

    def WriteWhole(self, bios_path):
        """Write the firmware from bios_path to the current system.

        @param bios_path: The path of the source BIOS image.
        """
        self._bios_handler.new_image(bios_path)
        self._bios_handler.write_whole()


class CgptServicer(object):
    """Class to service all CGPT RPCs"""

    def __init__(self, os_if):
        """
        @type os_if: os_interface.OSInterface
        """
        self._os_if = os_if
        self._cgpt_handler = cgpt_handler.CgptHandler(self._os_if)

    def GetAttributes(self):
        """Get kernel attributes."""
        rootdev = self._os_if.get_root_dev()
        self._cgpt_handler.read_device_info(rootdev)
        return {
                'A': self._cgpt_handler.get_partition(rootdev, 'KERN-A'),
                'B': self._cgpt_handler.get_partition(rootdev, 'KERN-B')
        }

    def SetAttributes(self, a=None, b=None):
        """Set kernel attributes for either partition (or both)."""
        partitions = {'A': a, 'B': b}
        rootdev = self._os_if.get_root_dev()
        modifiable_attributes = self._cgpt_handler.ATTR_TO_COMMAND.keys()
        for partition_name in partitions.keys():
            partition = partitions[partition_name]
            if partition is None:
                continue
            attributes_to_set = {
                    key: partition[key]
                    for key in modifiable_attributes
            }
            if attributes_to_set:
                self._cgpt_handler.set_partition(
                        rootdev, 'KERN-%s' % partition_name, attributes_to_set)


class EcServicer(object):
    """Class to service all EC RPCs"""

    def __init__(self, os_if):
        """
        @type os_if: os_interface.OSInterface
        """
        self._os_if = os_if

        # This attribute is accessed via a property, so it can load lazily
        # when actually used by the test.
        self._real_ec_handler = None
        ec_status = self._os_if.run_shell_command_get_status('mosys ec info')
        if ec_status == 0:
            self._real_ec_handler = flashrom_handler.FlashromHandler(
                    self._os_if, 'ec_root_key.vpubk',
                    '/usr/share/vboot/devkeys', 'ec')

        else:
            self._os_if.log('No EC is reported by mosys (rc=%s).' % ec_status)

    @property
    def _ec_handler(self):
        """Return the EC flashrom handler, after initializing it if necessary

        @rtype: flashrom_handler.FlashromHandler
        """
        if not self._real_ec_handler:
            # No EC handler if board has no EC
            return None

        if not self._real_ec_handler.initialized:
            self._real_ec_handler.init()
        return self._real_ec_handler

    def Reload(self):
        """Reload the firmware image that may be changed."""
        self._ec_handler.new_image()

    def GetVersion(self):
        """Get EC version via mosys.

        @return: A string of the EC version.
        """
        return self._os_if.run_shell_command_get_output(
                'mosys ec info | sed "s/.*| //"')[0]

    def GetActiveHash(self):
        """Get hash of active EC RW firmware."""
        return self._os_if.run_shell_command_get_output(
                'ectool echash | grep hash: | sed "s/hash:\s\+//"')[0]

    def DumpWhole(self, ec_path):
        """Dump the current EC firmware to a file, specified by ec_path.

        @param ec_path: The path of the EC image to be written.
        """
        self._ec_handler.dump_whole(ec_path)

    def WriteWhole(self, ec_path):
        """Write the firmware from ec_path to the current system.

        @param ec_path: The path of the source EC image.
        """
        self._ec_handler.new_image(ec_path)
        self._ec_handler.write_whole()

    def CorruptBody(self, section):
        """Corrupt the requested EC section body.

        @param section: An EC section, either 'a' or 'b'.
        """
        self._ec_handler.corrupt_firmware_body(section, corrupt_all=True)

    def DumpFirmware(self, ec_path):
        """Dump the current EC firmware to a file, specified by ec_path.

        @param ec_path: The path of the EC image to be written.
        """
        self._ec_handler.dump_whole(ec_path)

    def SetWriteProtect(self, enable):
        """Enable write protect of the EC flash chip.

        @param enable: True if activating EC write protect. Otherwise, False.
        """
        if enable:
            self._ec_handler.enable_write_protect()
        else:
            self._ec_handler.disable_write_protect()

    def IsEfs(self):
        """Return True if the EC supports EFS."""
        return self._ec_handler.has_section_body('rw_b')

    def CopyRw(self, from_section, to_section):
        """Copy EC RW from from_section to to_section."""
        self._ec_handler.copy_from_to(from_section, to_section)

    def RebootToSwitchSlot(self):
        """Reboot EC to switch the active RW slot."""
        self._os_if.run_shell_command('ectool reboot_ec cold switch-slot')


class HostServicer(object):
    """Class to service all Host RPCs (used only for Android DUTs) """

    def __init__(self, os_if):
        """
        @type os_if: os_interface.OSInterface
        """
        self._os_if = os_if

    def RunShellCommand(self, command):
        """Run shell command on the host.

        @param command: A shell command to be run.
        """
        self._os_if.run_host_shell_command(command)

    def RunShellCommandGetOutput(self, command):
        """Run shell command and get its console output on the host.

        @param command: A shell command to be run.
        @return: A list of strings stripped of the newline characters.
        """
        return self._os_if.run_host_shell_command_get_output(command)


class KernelServicer(object):
    """Class to service all Kernel RPCs"""

    def __init__(self, os_if):
        """
        @type os_if: os_interface.OSInterface
        """
        self._os_if = os_if
        self._kernel_handler = kernel_handler.KernelHandler()
        self._kernel_handler.init(
                self._os_if,
                dev_key_path='/usr/share/vboot/devkeys',
                internal_disk=True)

    def CorruptSig(self, section):
        """Corrupt the requested kernel section.

        @param section: A kernel section, either 'a' or 'b'.
        """
        self._kernel_handler.corrupt_kernel(section)

    def RestoreSig(self, section):
        """Restore the requested kernel section (previously corrupted).

        @param section: A kernel section, either 'a' or 'b'.
        """
        self._kernel_handler.restore_kernel(section)

    def _modify_version(self, section, delta):
        """Modify kernel version for the requested section, by adding delta.

        The passed in delta, a positive or a negative number, is added to the
        original kernel version.
        """
        original_version = self._kernel_handler.get_version(section)
        new_version = original_version + delta
        self._os_if.log('Setting kernel section %s version from %d to %d' %
                        (section, original_version, new_version))
        self._kernel_handler.set_version(section, new_version)

    def MoveVersionBackward(self, section):
        """Decrement kernel version for the requested section."""
        self._modify_version(section, -1)

    def MoveVersionForward(self, section):
        """Increase kernel version for the requested section."""
        self._modify_version(section, 1)

    def GetVersion(self, section):
        """Return kernel version."""
        return self._kernel_handler.get_version(section)

    def GetDatakeyVersion(self, section):
        """Return kernel datakey version."""
        return self._kernel_handler.get_datakey_version(section)

    def DiffAB(self):
        """Compare kernel A with B.

        @return: True: if kernel A is different with B.
                 False: if kernel A is the same as B.
        """
        rootdev = self._os_if.get_root_dev()
        kernel_a = self._os_if.join_part(rootdev, '2')
        kernel_b = self._os_if.join_part(rootdev, '4')

        # The signature (some kind of hash) for the kernel body is stored in
        # the beginning. So compare the first 64KB (including header, preamble,
        # and signature) should be enough to check them identical.
        header_a = self._os_if.read_partition(kernel_a, 0x10000)
        header_b = self._os_if.read_partition(kernel_b, 0x10000)

        return header_a != header_b

    def ResignWithKeys(self, section, key_path=None):
        """Resign kernel with temporary key."""
        self._kernel_handler.resign_kernel(section, key_path)

    def Dump(self, section, kernel_path):
        """Dump the specified kernel to a file.

        @param section: The kernel to dump. May be A or B.
        @param kernel_path: The path to the kernel image to be written.
        """
        self._kernel_handler.dump_kernel(section, kernel_path)

    def Write(self, section, kernel_path):
        """Write a kernel image to the specified section.

        @param section: The kernel to dump. May be A or B.
        @param kernel_path: The path to the kernel image.
        """
        self._kernel_handler.write_kernel(section, kernel_path)

    def GetSha(self, section):
        """Return the SHA1 hash of the specified kernel section."""
        return self._kernel_handler.get_sha(section)


class RootfsServicer(object):
    """Class to service all RootFS RPCs"""

    def __init__(self, os_if):
        """
        @type os_if: os_interface.OSInterface
        """
        self._os_if = os_if
        self._rootfs_handler = rootfs_handler.RootfsHandler()
        self._rootfs_handler.init(self._os_if)

    def VerifyRootfs(self, section):
        """Verifies the integrity of the root FS.

        @param section: The rootfs to verify. May be A or B.
        """
        return self._rootfs_handler.verify_rootfs(section)


class RpcSettingsServicer(object):
    """Class to service RPCs for settings of the RPC server itself"""

    def __init__(self, os_if):
        """
        @type os_if: os_interface.OSInterface
        """
        self._os_if = os_if

    def EnableTestMode(self):
        """Enable test mode (avoids writing to flash or gpt)"""
        self._os_if.test_mode = True

    def DisableTestMode(self):
        """Disable test mode and return to normal operation"""
        self._os_if.test_mode = False


class SystemServicer(object):
    """Class to service all System RPCs"""

    def __init__(self, os_if):
        """
        @type os_if: os_interface.OSInterface
        """
        self._os_if = os_if
        self._key_checker = firmware_check_keys.firmwareCheckKeys()

    def IsAvailable(self):
        """Function for polling the RPC server availability.

        @return: Always True.
        """
        return True

    def HasHost(self):
        """Return True if a host is connected to DUT."""
        return self._os_if.has_host()

    def WaitForClient(self, timeout):
        """Wait for the client to come back online.

        @param timeout: Time in seconds to wait for the client SSH daemon to
                        come up.
        @return: True if succeed; otherwise False.
        """
        return self._os_if.wait_for_device(timeout)

    def WaitForClientOffline(self, timeout):
        """Wait for the client to come offline.

        @param timeout: Time in seconds to wait the client to come offline.
        @return: True if succeed; otherwise False.
        """
        return self._os_if.wait_for_no_device(timeout)

    def DumpLog(self, remove_log=False):
        """Dump the log file.

        @param remove_log: Remove the log file after dump.
        @return: String of the log file content.
        """
        with open(self._os_if.log_file) as f:
            log = f.read()
        if remove_log:
            os.remove(self._os_if.log_file)
        return log

    def RunShellCommand(self, command):
        """Run shell command.

        @param command: A shell command to be run.
        """
        self._os_if.run_shell_command(command)

    def RunShellCommandCheckOutput(self, command, success_token):
        """Run shell command and check its stdout for a string.

        @param command: A shell command to be run.
        @param success_token: A string to search the output for.
        @return: A Boolean indicating whether the success_token was found in
                the command output.
        """
        return self._os_if.run_shell_command_check_output(
                command, success_token)

    def RunShellCommandGetOutput(self, command, include_stderr=False):
        """Run shell command and get its console output.

        @param command: A shell command to be run.
        @return: A list of strings stripped of the newline characters.
        """
        return self._os_if.run_shell_command_get_output(command, include_stderr)

    def RunShellCommandGetStatus(self, command):
        """Run shell command and get its console status.

        @param command: A shell command to be run.
        @return: The returncode of the process
        @rtype: int
        """
        return self._os_if.run_shell_command_get_status(command)

    def GetPlatformName(self):
        """Get the platform name of the current system.

        @return: A string of the platform name.
        """
        # 'mosys platform name' sometimes fails. Let's get the verbose output.
        lines = self._os_if.run_shell_command_get_output(
                '(mosys -vvv platform name 2>&1) || echo Failed')
        if lines[-1].strip() == 'Failed':
            raise Exception('Failed getting platform name: ' +
                            '\n'.join(lines))
        return lines[-1]

    def DevTpmPresent(self):
        """Check if /dev/tpm0 is present.

        @return: Boolean true or false.
        """
        return os.path.exists('/dev/tpm0')

    def GetCrossystemValue(self, key):
        """Get crossystem value of the requested key.

        @param key: A crossystem key.
        @return: A string of the requested crossystem value.
        """
        return self._os_if.run_shell_command_get_output(
                'crossystem %s' % key)[0]

    def GetRootDev(self):
        """Get the name of root device without partition number.

        @return: A string of the root device without partition number.
        """
        return self._os_if.get_root_dev()

    def GetRootPart(self):
        """Get the name of root device with partition number.

        @return: A string of the root device with partition number.
        """
        return self._os_if.get_root_part()

    def SetTryFwB(self, count=1):
        """Set 'Try Firmware B' flag in crossystem.

        @param count: # times to try booting into FW B
        """
        self._os_if.cs.fwb_tries = count

    def SetFwTryNext(self, next, count=0):
        """Set fw_try_next to A or B.

        @param next: Next FW to reboot to (A or B)
        @param count: # of times to try booting into FW <next>
        """
        self._os_if.cs.fw_try_next = next
        if count:
            self._os_if.cs.fw_try_count = count

    def GetFwVboot2(self):
        """Get fw_vboot2."""
        try:
            return self._os_if.cs.fw_vboot2 == '1'
        except os_interface.OSInterfaceError:
            return False

    def RequestRecoveryBoot(self):
        """Request running in recovery mode on the restart."""
        self._os_if.cs.request_recovery()

    def GetDevBootUsb(self):
        """Get dev_boot_usb value which controls developer mode boot from USB.

        @return: True if enable, False if disable.
        """
        return self._os_if.cs.dev_boot_usb == '1'

    def SetDevBootUsb(self, value):
        """Set dev_boot_usb value which controls developer mode boot from USB.

        @param value: True to enable, False to disable.
        """
        self._os_if.cs.dev_boot_usb = 1 if value else 0

    def IsRemovableDeviceBoot(self):
        """Check the current boot device is removable.

        @return: True: if a removable device boots.
                 False: if a non-removable device boots.
        """
        root_part = self._os_if.get_root_part()
        return self._os_if.is_removable_device(root_part)

    def GetInternalDevice(self):
        """Get the internal disk by given the current disk."""
        root_part = self._os_if.get_root_part()
        return self._os_if.get_internal_disk(root_part)

    def CreateTempDir(self, prefix='backup_'):
        """Create a temporary directory and return the path."""
        return tempfile.mkdtemp(prefix=prefix)

    def RemoveFile(self, file_path):
        """Remove the file."""
        return self._os_if.remove_file(file_path)

    def RemoveDir(self, dir_path):
        """Remove the directory."""
        return self._os_if.remove_dir(dir_path)

    def CheckKeys(self, expected_sequence):
        """Check the keys sequence was as expected.

        @param expected_sequence: A list of expected key sequences.
        """
        return self._key_checker.check_keys(expected_sequence)


class TpmServicer(object):
    """Class to service all TPM RPCs"""

    def __init__(self, os_if):
        """
        @type os_if: os_interface.OSInterface
        """
        self._os_if = os_if

        # This attribute is accessed via a property, so it can load lazily
        # when actually used by the test.
        self._real_tpm_handler = tpm_handler.TpmHandler(self._os_if)

    @property
    def _tpm_handler(self):
        """Handler for the TPM

        @rtype: tpm_handler.TpmHandler
        """
        if not self._real_tpm_handler.initialized:
            self._real_tpm_handler.init()
        return self._real_tpm_handler

    def GetFirmwareVersion(self):
        """Retrieve tpm firmware body version."""
        return self._tpm_handler.get_fw_version()

    def GetFirmwareDatakeyVersion(self):
        """Retrieve tpm firmware data key version."""
        return self._tpm_handler.get_fw_key_version()

    def GetKernelVersion(self):
        """Retrieve tpm kernel body version."""
        return self._tpm_handler.get_kernel_version()

    def GetKernelDatakeyVersion(self):
        """Retrieve tpm kernel data key version."""
        return self._tpm_handler.get_kernel_key_version()

    def StopDaemon(self):
        """Stop tpm related daemon."""
        return self._tpm_handler.stop_daemon()

    def RestartDaemon(self):
        """Restart tpm related daemon which was stopped by stop_daemon()."""
        return self._tpm_handler.restart_daemon()


class UpdaterServicer(object):
    """Class to service all Updater RPCs"""

    def __init__(self, os_if):
        """
        @type os_if: os_interface.OSInterface
        """
        self._os_if = os_if
        self._updater = firmware_updater.FirmwareUpdater(self._os_if)

    def Cleanup(self):
        """Clean up the temporary directory"""
        self._updater.cleanup_temp_dir()

    def StopDaemon(self):
        """Stop update-engine daemon."""
        return self._updater.stop_daemon()

    def StartDaemon(self):
        """Start update-engine daemon."""
        return self._updater.start_daemon()

    def GetSectionFwid(self, target='bios', section=None):
        """Retrieve shellball's RW or RO fwid."""
        return self._updater.get_section_fwid(target, section)

    def GetAllFwids(self, target='bios'):
        """Retrieve shellball's RW and/or RO fwids for all sections."""
        return self._updater.get_all_fwids(target)

    def GetAllInstalledFwids(self, target='bios', filename=None):
        """Retrieve installed (possibly emulated) fwids for the target."""
        return self._updater.get_all_installed_fwids(target, filename)

    def ModifyFwids(self, target='bios', sections=None):
        """Modify the AP fwid in the image, but don't flash it."""
        return self._updater.modify_fwids(target, sections)

    def ModifyEcidAndFlashToBios(self):
        """Modify ecid, put it to AP firmware, and flash it to the system."""
        self._updater.modify_ecid_and_flash_to_bios()

    def GetEcHash(self):
        """Return the hex string of the EC hash."""
        blob = self._updater.get_ec_hash()
        # Format it to a hex string
        return ''.join('%02x' % ord(c) for c in blob)

    def ResignFirmware(self, version):
        """Resign firmware with version.

        @param version: new version number.
        """
        self._updater.resign_firmware(version)

    def ExtractShellball(self, append=None):
        """Extract shellball with the given append suffix.

        @param append: use for the shellball name.
        """
        return self._updater.extract_shellball(append)

    def RepackShellball(self, append=None):
        """Repack shellball with new fwid.

        @param append: use for the shellball name.
        """
        return self._updater.repack_shellball(append)

    def ResetShellball(self):
        """Revert to the stock shellball"""
        self._updater.reset_shellball()

    def RunFirmwareupdate(self, mode, append=None, options=()):
        """Run updater with the given options

        @param mode: mode for the updater
        @param append: extra string appended to shellball filename to run
        @param options: options for chromeos-firmwareupdate
        @return: returncode of the updater
        @rtype: int
        """
        return self._updater.run_firmwareupdate(mode, append, options)

    def RunAutoupdate(self, append):
        """Run chromeos-firmwareupdate with autoupdate mode."""
        options = ['--noupdate_ec', '--wp=1']
        self._updater.run_firmwareupdate(
                mode='autoupdate', append=append, options=options)

    def RunFactoryInstall(self):
        """Run chromeos-firmwareupdate with factory_install mode."""
        options = ['--noupdate_ec', '--wp=0']
        self._updater.run_firmwareupdate(
                mode='factory_install', options=options)

    def RunBootok(self, append):
        """Run chromeos-firmwareupdate with bootok mode."""
        self._updater.run_firmwareupdate(mode='bootok', append=append)

    def RunRecovery(self):
        """Run chromeos-firmwareupdate with recovery mode."""
        options = ['--noupdate_ec', '--nocheck_keys', '--force', '--wp=1']
        self._updater.run_firmwareupdate(mode='recovery', options=options)

    def CbfsSetupWorkDir(self):
        """Sets up cbfstool work directory."""
        return self._updater.cbfs_setup_work_dir()

    def CbfsExtractChip(self, fw_name):
        """Runs cbfstool to extract chip firmware.

        @param fw_name: Name of chip firmware to extract.
        @return: Boolean success status.
        """
        return self._updater.cbfs_extract_chip(fw_name)

    def CbfsGetChipHash(self, fw_name):
        """Gets the chip firmware hash blob.

        @param fw_name: Name of chip firmware whose hash blob to return.
        @return: Hex string of hash blob.
        """
        return self._updater.cbfs_get_chip_hash(fw_name)

    def CbfsReplaceChip(self, fw_name):
        """Runs cbfstool to replace chip firmware.

        @param fw_name: Name of chip firmware to extract.
        @return: Boolean success status.
        """
        return self._updater.cbfs_replace_chip(fw_name)

    def CbfsSignAndFlash(self):
        """Runs cbfs signer and flash it.

        @param fw_name: Name of chip firmware to extract.
        @return: Boolean success status.
        """
        return self._updater.cbfs_sign_and_flash()

    def GetTempPath(self):
        """Get updater's temp directory path."""
        return self._updater.get_temp_path()

    def GetKeysPath(self):
        """Get updater's keys directory path."""
        return self._updater.get_keys_path()

    def GetWorkPath(self):
        """Get updater's work directory path."""
        return self._updater.get_work_path()

    def GetBiosRelativePath(self):
        """Gets the relative path of the bios image in the shellball."""
        return self._updater.get_bios_relative_path()

    def GetEcRelativePath(self):
        """Gets the relative path of the ec image in the shellball."""
        return self._updater.get_ec_relative_path()

    def CopyBios(self, filename):
        """Make a copy of the shellball bios.bin"""
        return self._updater.copy_bios(filename)
