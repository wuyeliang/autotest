# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import firmware_hash
import glob
import imp
import logging
import os
import pprint
import re
from autotest_lib.client.bin import factory
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import flashrom_util
from autotest_lib.client.common_lib import gbb_util
from autotest_lib.client.common_lib import site_fmap
from autotest_lib.client.cros import vblock


class hardware_Components(test.test):
    version = 2
    # We divide all component IDs (cids) into 5 categories:
    #  - enumable: able to get the results by running specific commands;
    #  - PCI: PCI devices;
    #  - USB: USB devices;
    #  - probable: returns existed or not by given some pre-defined choices;
    #  - not test: only data, don't test them.
    _enumerable_cids = [
        'data_display_geometry',
        'hash_ec_firmware',
        'hash_ro_firmware',
        'part_id_3g',
        'part_id_audio_codec',
        'part_id_bluetooth',
        'part_id_chipset',
        'part_id_cpu',
        'part_id_display_panel',
        'part_id_dram',
        'part_id_ec_flash_chip',
        'part_id_embedded_controller',
        'part_id_ethernet',
        'part_id_flash_chip',
        'part_id_hwqual',
        'part_id_keyboard',
        'part_id_storage',
        'part_id_tpm',
        'part_id_usb_hosts',
        'part_id_vga',
        'part_id_webcam',
        'part_id_wireless',
        'vendor_id_touchpad',
        'version_rw_firmware',
        'version_3g_firmware',
        # gps is currently not supported.
        # 'part_id_gps',
    ]
    _probable_cids = [
        'key_recovery',
        'key_root',
        'part_id_cardreader',
        'part_id_chrontel',
    ]
    _not_test_cids = [
        'data_bitmap_fv',
        'data_recovery_url',
    ]
    _to_be_tested_cids_groups = [
        _enumerable_cids,
        _probable_cids,
    ]
    _not_present = 'Not Present'

    # Type id for connection management (compatible to flimflam)
    _type_3g = 'cellular'
    _type_ethernet = 'ethernet'
    _type_wireless = 'wifi'

    _flimflam_dir = '/usr/local/lib/flimflam/test'

    def import_flimflam_module(self):
      """ Tries to load flimflam module from current system """
      if not os.path.exists(self._flimflam_dir):
        DebugMsg('no flimflam installed in %s' % self._flimflam_dir)
        return None
      try:
        return imp.load_module('flimflam', *imp.find_module(
                'flimflam', [self._flimflam_dir]))
      except ImportError:
        ErrorMsg('Failed to import flimflam.')
      except:
        ErrorMsg('Failed to load flimflam.')
      return None

    def load_flimflam(self):
      """Gets information provided by flimflam (connection manager)

      Returns
      (None, None) if failed to load module, otherwise
      (connection_path, connection_info) where
       connection_path is a dict in {type: device_path},
       connection_info is a dict of {type: {attribute: value}}.
      """
      flimflam = self.import_flimflam_module()
      if not flimflam:
        return (None, None)
      path = {}
      info = {}
      info_attribute_names = {
        self._type_3g: ['Carrier', 'FirmwareRevision', 'HardwareRevision',
                        'ModelID', 'Manufacturer'],
      }
      devices = flimflam.FlimFlam().GetObjectList('Device')
      unpack = flimflam.convert_dbus_value
      for device in devices:
        # populate the 'path' collection
        prop = device.GetProperties()
        prop_type = unpack(prop['Type'])
        prop_path = unpack(prop['Interface'])
        if prop_type in path:
          WarningMsg('Multiple network devices with same type (%s) were found.'
                     'Target path changed from %s to %s.' %
                     (prop_type, path[prop_type], prop_path))
        path[prop_type] = '/sys/class/net/%s/device' % prop_path
        if prop_type not in info_attribute_names:
          continue
        # populate the 'info' collection
        info[prop_type] = dict((
            (key, unpack(prop['Cellular.%s' % key]))
            for key in info_attribute_names[prop_type]
            if ('Cellular.%s' % key) in prop))
      return (path, info)

    def _get_all_connection_info(self):
        """ Probes available connectivity and device information """
        connection_info = {
                self._type_wireless: '/sys/class/net/wlan0/device',
                self._type_ethernet: '/sys/class/net/eth0/device',
                # 3g(cellular) may also be /sys/class/net/usb0
                self._type_3g: '/sys/class/tty/ttyUSB0/device',
        }
        (path, _) = self.load_flimflam()
        if path is not None:
          # trust flimflam instead.
          for k in connection_info:
            connection_info[k] = (path[k] if k in path else '')
        return connection_info

    def _get_sysfs_device_info(self, path, primary, optional=[]):
        """Gets the device information of a sysfs node.

        Args
          path: the sysfs device path.
          primary: mandatory list of elements to read.
          optional: optional list of elements to read.

        Returns
          [primary_values_dict, optional_values_dict]
        """
        primary_values = {}
        optional_values = {}
        for element in primary:
            element_path = os.path.join(path, element)
            if not os.path.exists(element_path):
                return [None, None]
            primary_values[element] = utils.read_one_line(element_path)
        for element in optional:
            element_path = os.path.join(path, element)
            if os.path.exists(element_path):
                optional_values[element] = utils.read_one_line(element_path)
        return [primary_values, optional_values]

    def _get_pci_device_info(self, path):
        """ Returns a PCI 'vendor:device' component information. """
        # TODO(hungte) PCI has a 'rev' info which may be better added into info.
        (info, _) = self._get_sysfs_device_info(path, ['vendor', 'device'])
        return '%s:%s' % (info['vendor'].replace('0x', ''),
                          info['device'].replace('0x', '')) if info else None

    def _get_usb_device_info(self, path):
        """ Returns an USB 'idVendor:idProduct manufacturer product' info. """

        # USB in sysfs is hierarchy, and usually uses the 'interface' layer.
        # If we are in 'interface' layer, the product info is in real parent
        # folder.
        path = os.path.realpath(path)
        while path.find('/usb') > 0:
            if os.path.exists(os.path.join(path, 'idProduct')):
                break
            path = os.path.split(path)[0]
        optional_fields = []
        # uncomment the line below to allow having descriptive string
        # optional_fields = ['manufacturer', 'product']
        (info, optional) = self._get_sysfs_device_info(
                path, ['idVendor', 'idProduct'], optional_fields)
        if not info:
            return None
        info_string = '%s:%s' % (info['idVendor'].replace('0x', ''),
                                 info['idProduct'].replace('0x', ''))
        for field in optional_fields:
            if field in optional:
                info_string += ' ' + optional[field]
        return info_string

    def get_sysfs_device_id(self, path):
        """Gets a sysfs device identifier. (Currently supporting USB/PCI)
        Args
          path: a path to sysfs device (ex, /sys/class/net/wlan0/device)

        Returns
          An identifier string, or self._not_present if not available.
        """
        path = os.path.realpath(path)
        if not os.path.isdir(path):
            return self._not_present
        info = (self._get_pci_device_info(path) or
                self._get_usb_device_info(path))
        return info or self._not_present

    def get_all_enumerable_components(self):
        results = {}
        for cid in self._enumerable_cids:
            components = self.force_get_property('get_' + cid)
            if not isinstance(components, list):
                components = [ components ]
            results[cid] = components
        return results


    def check_enumerable_component(self, cid, exact_values, approved_values):
        if '*' in approved_values:
            return

        for value in exact_values:
            if value not in approved_values:
                if cid in self._failures:
                    self._failures[cid].append(value)
                else:
                    self._failures[cid] = [ value ]

    def check_probable_component(self, cid, approved_values):
        if '*' in approved_values:
            self._system[cid] = [ '*' ]
            return

        for value in approved_values:
            present = getattr(self, 'probe_' + cid)(value)
            if present:
                self._system[cid] = [ value ]
                return

        self._failures[cid] = [ 'No match' ]


    def get_data_display_geometry(self):
        # Get edid from driver. TODO(nsanders): this is driver specific.
        # TODO(waihong): read-edid is also x86 only.
        cmd = 'find /sys/devices/ -name edid | grep LVDS'
        edid_file = utils.system_output(cmd)

        cmd = ('cat ' + edid_file + ' | parse-edid | grep "Mode " | '
               'sed \'s/^.*"\(.*\)".*$/\\1/\'')
        data = utils.system_output(cmd).split()
        if not data:
            data = [ '' ]
        return data


    def get_hash_ec_firmware(self):
        """
        Returns a hash of Embedded Controller firmware parts,
        to confirm we have proper updated version of EC firmware.
        """
        return firmware_hash.get_ec_hash(exception_type=error.TestError)


    def get_hash_ro_firmware(self):
        """
        Returns a hash of Read Only (BIOS) firmware parts,
        to confirm we have proper keys / boot code / recovery image installed.
        """
        return firmware_hash.get_bios_ro_hash(exception_type=error.TestError)

    def get_part_id_3g(self):
        device_path = self._get_all_connection_info()[self._type_3g]
        return self.get_sysfs_device_id(device_path) or self._not_present

    def get_part_id_audio_codec(self):
        cmd = 'grep -R Codec: /proc/asound/* | head -n 1 | sed s/.\*Codec://'
        part_id = utils.system_output(cmd).strip()
        return part_id

    def get_part_id_bluetooth(self):
        return self.get_sysfs_device_id('/sys/class/bluetooth/hci0/device')

    def get_part_id_chipset(self):
        # Host bridge is always the first PCI device.
        return self.get_sysfs_device_id('/sys/bus/pci/devices/0000:00:00.0')

    def get_part_id_cpu(self):
        cmd = 'grep -m 1 \'model name\' /proc/cpuinfo | sed s/.\*://'
        part_id = utils.system_output(cmd).strip()
        return part_id


    def get_part_id_display_panel(self):
        cmd = 'find /sys/devices/ -name edid | grep LVDS'
        edid_file = utils.system_output(cmd)

        cmd = ('cat ' + edid_file + ' | parse-edid | grep ModelName | '
               'sed \'s/^.*ModelName "\(.*\)"$/\\1/\'')
        part_id = utils.system_output(cmd).strip()
        return part_id


    def get_part_id_embedded_controller(self):
        # example output:
        #  Found Nuvoton WPCE775x (id=0x05, rev=0x02) at 0x2e
        parts = []
        res = utils.system_output('superiotool', ignore_status=True).split('\n')
        for line in res:
            match = re.search(r'Found (.*) at', line)
            if match:
                parts.append(match.group(1))
        part_id = ", ".join(parts)
        return part_id

    def get_part_id_dram(self):
        grep_cmd = 'grep i2c_dev /proc/modules'
        i2c_loaded = (utils.system(grep_cmd, ignore_status=True) == 0)
        if not i2c_loaded:
            utils.system('modprobe i2c_dev')

        if os.path.exists('/tmp/mosys.log'):
            cmd = ('cat /tmp/mosys.log | grep size_mb | cut -f2 -d"|"')
        else:
            cmd = ('mosys -l memory spd print geometry | '
                   'grep size_mb | cut -f2 -d"|"')
        part_id = utils.system_output(cmd).strip()

        if not i2c_loaded:
            utils.system('modprobe -r i2c_dev')
        if part_id != '':
            return part_id
        else:
            return self._not_present

    def get_part_id_ethernet(self):
        device_path = self._get_all_connection_info()[self._type_ethernet]
        return self.get_sysfs_device_id(device_path) or self._not_present

    def get_part_id_flash_chip(self):
        # example output:
        #  Found chip "Winbond W25x16" (2048 KB, FWH) at physical address 0xfe
        parts = []
        lines = utils.system_output('flashrom -V -p internal:bus=spi',
                                    ignore_status=True).split('\n')
        for line in lines:
            match = re.search(r'Found chip "(.*)" .* at physical address ',
                              line)
            if match:
                parts.append(match.group(1))
        part_id = ", ".join(parts)
        return part_id


    def get_part_id_ec_flash_chip(self):
        # example output:
        #  Found chip "Winbond W25x10" (128 KB, SPI) at physical address ...
        parts = []
        lines = utils.system_output('flashrom -V -p internal:bus=lpc',
                                    ignore_status=True).split('\n')
        # Undo BBS register after call.
        utils.system('flashrom -p internal:bus=spi', ignore_status=True)
        for line in lines:
            match = re.search(r'Found chip "(.*)" .* at physical address ',
                              line)
            if match:
                parts.append(match.group(1))
        part_id = ", ".join(parts)
        return part_id


    def get_part_id_hwqual(self):
        hwid_file = '/sys/devices/platform/chromeos_acpi/HWID'
        if os.path.exists(hwid_file):
            part_id = utils.read_one_line(hwid_file)
            return part_id
        else:
            return self._not_present

    def get_part_id_keyboard(self):
        # VPD value "initial_locale"="en-US" should be listed.
        cmd = 'vpd -i RO_VPD -l | grep \"keyboard_layout\" | cut -f4 -d\'"\' '
        part_id = utils.system_output(cmd).strip()
        if part_id != '':
            return part_id
        else:
            return self._not_present

    def get_part_id_storage(self):
        cmd = ('cd $(find /sys/devices -name sda)/../..; '
               'cat vendor model | tr "\n" " " | sed "s/ \+/ /g"')
        part_id = utils.system_output(cmd).strip()
        return part_id


    def get_part_id_tpm(self):
        """
        Returns Manufacturer_info : Chip_Version
        """
        cmd = 'tpm_version'
        tpm_output = utils.system_output(cmd)
        tpm_lines = tpm_output.splitlines()
        tpm_dict = {}
        for tpm_line in tpm_lines:
            [key, colon, value] = tpm_line.partition(':')
            tpm_dict[key.strip()] = value.strip()
        part_id = ''
        key1, key2 = 'Manufacturer Info', 'Chip Version'
        if key1 in tpm_dict and key2 in tpm_dict:
            part_id = tpm_dict[key1] + ':' + tpm_dict[key2]
        return part_id

    def get_part_id_usb_hosts(self):
        usb_bus_list = glob.glob('/sys/bus/usb/devices/usb*')
        usb_host_list = [os.path.join(os.path.realpath(path), '..')
                         for path in usb_bus_list]
        usb_host_info = [self.get_sysfs_device_id(device)
                         for device in usb_host_list]
        usb_host_info.sort(reverse=True)
        # uncomment and use the line below if you want to list all USB buses
        # return ' '.join(usb_host_info)
        return usb_host_info[0] if usb_host_info else ''

    def get_part_id_vga(self):
        return self.get_sysfs_device_id('/sys/class/graphics/fb0/device')

    def get_part_id_webcam(self):
        return self.get_sysfs_device_id('/sys/class/video4linux/video0/device')

    def get_part_id_wireless(self):
        device_path = self._get_all_connection_info()[self._type_wireless]
        return self.get_sysfs_device_id(device_path) or self._not_present

    def get_closed_vendor_id_touchpad(self, vendor_name):
        """
        Using closed-source method to derive the vendor information
        given the vendor name.
        """
        part_id = ''
        if vendor_name.lower() == 'synaptics':
            detect_program = '/opt/Synaptics/bin/syndetect'
            model_string_str = 'Model String'
            firmware_id_str = 'Firmware ID'
            if os.path.exists(detect_program):
                data = utils.system_output(detect_program, ignore_status=True)
                properties = dict(map(str.strip, line.split('=', 1))
                                  for line in data.splitlines() if '=' in line)
                model = properties.get(model_string_str, 'UnknownModel')
                firmware_id = properties.get(firmware_id_str, 'UnknownFWID')
                # The pattern " on xxx Port" may vary by the detection approach,
                # so we need to strip it.
                model = re.sub(' on [^ ]* [Pp]ort$', '', model)
                # Format: Model #FirmwareId
                part_id = '%s #%s' % (model, firmware_id)
        return part_id


    def get_vendor_id_touchpad(self):
        # First, try to use closed-source method to probe touch pad
        part_id = self.get_closed_vendor_id_touchpad('Synaptics')
        if part_id != '':
            return part_id
        # If the closed-source method above fails to find vendor infomation,
        # try an open-source method.
        else:
            cmd_grep = 'grep -i Touchpad /proc/bus/input/devices | sed s/.\*=//'
            part_id = utils.system_output(cmd_grep).strip('"')
            return part_id


    def get_version_rw_firmware(self):
        """
        Returns the version of Read-Write (writable) firmware from VBOOT
        section. If A/B has different version, that means this system
        needs a reboot + firmwar update so return value is a "error report"
        in the form "A=x, B=y".
        """
        versions = [None, None]
        section_names = ['VBOOTA', 'VBOOTB']
        flashrom = flashrom_util.flashrom_util()
        if not flashrom.select_bios_flashrom():
            raise error.TestError('Cannot select BIOS flashrom')
        base_img = flashrom.read_whole()
        flashrom_size = len(base_img)
        # we can trust base image for layout, since it's only RW.
        layout = flashrom.detect_chromeos_bios_layout(flashrom_size, base_img)
        if not layout:
            raise error.TestError('Cannot detect ChromeOS flashrom layout')
        for index, name in enumerate(section_names):
            data = flashrom.get_section(base_img, layout, name)
            block = vblock.unpack_verification_block(data)
            ver = block['VbFirmwarePreambleHeader']['firmware_version']
            versions[index] = ver
        # we embed error reports in return value.
        assert len(versions) == 2
        if versions[0] != versions[1]:
            return 'A=%d, B=%d' % (versions[0], versions[1])
        return '%d' % (versions[0])

    def get_version_3g_firmware(self):
        vendor_cmd = ('modem status | '
                      'sed -n -e "/Manufacturer/s/.*Manufacturer: //p"')
        vendor = utils.system_output(vendor_cmd)
        modem_cmd = ('modem status | sed -n -e "/Modem/s/.*Modem: //p"')
        modem = utils.system_output(modem_cmd)
        if vendor == 'Samsung' and modem == 'GT-Y3300X':
            cmd = ("modem status | grep Version: -A 2 | tail -1 | "
                   "awk '{print $1}'")
            version = utils.system_output(cmd)
        elif vendor == 'Qualcomm Incorporated':
            cmd = ("modem status | awk '/Version: / {print $2}'")
            version = utils.system_output(cmd)
        else:
            version = 'Unknown'
        return version

    def probe_key_recovery(self, part_id):
        current_key = self._gbb.get_recoverykey()
        target_key = utils.read_file(part_id)
        return current_key.startswith(target_key)


    def probe_key_root(self, part_id):
        current_key = self._gbb.get_rootkey()
        target_key = utils.read_file(part_id)
        return current_key.startswith(target_key)


    def probe_part_id_cardreader(self, part_id):
        # A cardreader is always power off until a card inserted. So checking
        # it using log messages instead of lsusb can limit operator-attended.
        # But note that it does not guarantee the cardreader presented during
        # the time of the test.
        [vendor_id, product_id] = part_id.split(':')
        found_pattern = ('New USB device found, idVendor=%s, idProduct=%s' %
                         (vendor_id, product_id))
        cmd = 'grep -qs "%s" /var/log/messages*' % found_pattern
        return utils.system(cmd, ignore_status=True) == 0


    def probe_part_id_chrontel(self, part_id):
        if part_id == self._not_present:
            return True

        if part_id == 'ch7036':
            grep_cmd = 'grep i2c_dev /proc/modules'
            i2c_loaded = (utils.system(grep_cmd, ignore_status=True) == 0)
            if not i2c_loaded:
                utils.system('modprobe i2c_dev')

            probe_cmd = 'ch7036_monitor -p'
            present = (utils.system(probe_cmd, ignore_status=True) == 0)

            if not i2c_loaded:
                utils.system('modprobe -r i2c_dev')
            return present

        return False


    def force_get_property(self, property_name):
        """ Returns property value or empty string on error. """
        try:
            return getattr(self, property_name)()
        except error.TestError as e:
            logging.error("Test error in getting property %s", property_name,
                          exc_info=1)
            return ''
        except:
            logging.error("Exception getting property %s", property_name,
                          exc_info=1)
            return ''


    def pformat(self, obj):
        return "\n" + self._pp.pformat(obj) + "\n"


    def update_ignored_cids(self, ignored_cids):
        for cid in ignored_cids:
            for group in self._to_be_tested_cids_groups:
                if cid in group:
                    group.remove(cid)
                    break
            else:
                raise error.TestError('The ignored cid %s is not defined' % cid)
            self._not_test_cids.append(cid)


    def read_approved_from_file(self, filename):
        approved = eval(utils.read_file(filename))
        for group in self._to_be_tested_cids_groups + [ self._not_test_cids ]:
            for cid in group:
                if cid not in approved:
                    # If we don't have any listing for this type
                    # of part in HWID, it's not required.
                    factory.log('Bypassing unlisted cid %s' % cid)
                    approved[cid] = '*'
        return approved


    def select_correct_dbs(self, approved_dbs):
        os.chdir(self.bindir)
        id_hwqual = None
        try:
            id_hwqual = factory.get_shared_data('part_id_hwqual')
        except Exception, e:
            # hardware_Components may run without factory environment
            factory.log('Failed getting shared data, ignored: %s' % repr(e))
        if id_hwqual:
            # If HwQual ID is already specified, find the list with same ID.
            id_hwqual = id_hwqual.replace(' ', '_')
            approved_dbs = 'data_*/components_%s' % id_hwqual
        else:
            sample_approved_dbs = 'approved_components.default'
            if (not glob.glob(approved_dbs)) and glob.glob(sample_approved_dbs):
                # Fallback to the default (sample) version
                approved_dbs = sample_approved_dbs
                factory.log('Using default (sample) approved component list: %s'
                            % sample_approved_dbs)

        # approved_dbs supports shell-like filename expansion.
        existing_dbs = glob.glob(approved_dbs)
        if not existing_dbs:
            raise error.TestError('Unable to find approved db: %s' %
                                  approved_dbs)

        return existing_dbs


    def initialize(self):
        self._gbb = gbb_util.GBBUtility()
        self._pp = pprint.PrettyPrinter()


    def run_once(self, approved_dbs='approved_components', ignored_cids=[]):
        self.update_ignored_cids(ignored_cids)
        enumerable_system = self.get_all_enumerable_components()

        only_cardreader_failed = False
        all_failures = 'The following components are not matched.\n'
        correct_dbs = self.select_correct_dbs(approved_dbs)
        for db in correct_dbs:
            self._system = enumerable_system
            self._failures = {}
            approved = self.read_approved_from_file(db)
            factory.log('Approved DB: %s' % self.pformat(approved))

            for cid in self._enumerable_cids:
                self.check_enumerable_component(
                        cid, enumerable_system[cid], approved[cid])

            for cid in self._probable_cids:
                self.check_probable_component(cid, approved[cid])

            factory.log('System: %s' % self.pformat(self._system))

            outdb = 'system_%s' % os.path.basename(db).replace('approved_', '')
            outdb = os.path.join(self.resultsdir, outdb)
            utils.open_write_close(outdb, self.pformat(self._system))

            if self._failures:
                if self._failures.keys() == ['part_id_cardreader']:
                    only_cardreader_failed = True
                all_failures += 'For DB %s:' % db
                all_failures += self.pformat(self._failures)
            else:
                # If one of DBs is matched, record some data in shared_data.
                cids_need_to_be_record = ['part_id_hwqual']
                try:
                    for cid in cids_need_to_be_record:
                        factory.set_shared_data(cid, approved[cid][0])
                except Exception, e:
                    # hardware_Components may run without factory environment
                    factory.log('Failed setting shared data, ignored: %s' %
                                repr(e))
                return

        if only_cardreader_failed:
            all_failures = ('You may forget to insert an SD card.\n' +
                            all_failures)

        raise error.TestFail(all_failures)
