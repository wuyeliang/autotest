# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Expects to be run in an environment with sudo and no interactive password
# prompt, such as within the Chromium OS development chroot.


"""This file provides core logic for servo verify/repair process."""


import logging
import os
import re
import tarfile
import time
import traceback
import xmlrpclib

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import hosts
from autotest_lib.client.common_lib import lsbrelease_utils
from autotest_lib.client.common_lib.cros import retry
from autotest_lib.client.common_lib.cros.network import ping_runner
from autotest_lib.server.cros.servo import servo
from autotest_lib.server.hosts import servo_repair
from autotest_lib.server.hosts import base_servohost
from autotest_lib.server.hosts import servo_constants
from autotest_lib.client.common_lib import global_config

_CONFIG = global_config.global_config


class ServoHost(base_servohost.BaseServoHost):
    """Host class for a servo host(e.g. beaglebone, labstation)
     that with a servo instance for a specific port.

     @type _servo: servo.Servo | None
     """

    DEFAULT_PORT = int(os.getenv('SERVOD_PORT', '9999'))

    # Timeout for initializing servo signals.
    INITIALIZE_SERVO_TIMEOUT_SECS = 60

    # Ready test function
    SERVO_READY_METHOD = 'get_version'

    # Directory prefix on the servo host where the servod logs are stored.
    SERVOD_LOG_PREFIX = '/var/log/servod'

    # Exit code to use when symlinks for servod logs are not found.
    NO_SYMLINKS_CODE = 9

    # Directory in the job's results directory to dump the logs into.
    LOG_DIR = 'servod'

    # Prefix for joint loglevel files in the logs.
    JOINT_LOG_PREFIX = 'log'

    # Regex group to extract timestamp from logfile name.
    TS_GROUP = 'ts'

    # This regex is used to extract the timestamp from servod logs.
             # files always start with log.
    TS_RE = (r'log.'
             # The timestamp is of format %Y-%m-%d--%H-%M-%S.MS
             r'(?P<%s>\d{4}(\-\d{2}){2}\-(-\d{2}){3}.\d{3})'
             # The loglevel is optional depending on labstation version.
             r'(.(INFO|DEBUG|WARNING))?' % TS_GROUP)
    TS_EXTRACTOR = re.compile(TS_RE)

    # Regex group to extract MCU name from logline in servod logs.
    MCU_GROUP = 'mcu'

    # Regex group to extract logline from MCU logline in servod logs.
    LINE_GROUP = 'line'

    # This regex is used to extract the mcu and the line content from an
    # MCU logline in servod logs. e.g. EC or servo_v4 console logs.
    # Here is an example log-line:
    #
    # 2020-01-23 13:15:12,223 - servo_v4 - EC3PO.Console - DEBUG -
    # console.py:219:LogConsoleOutput - /dev/pts/9 - cc polarity: cc1
    #
    # Here is conceptually how they are formatted:
    #
    #  <time> - <MCU> - EC3PO.Console - <LVL> - <file:line:func> - <pts> -
    #  <output>
    #
              # The log format starts with a timestamp
    MCU_RE = (r'[\d\-]+ [\d:,]+ '
              # The mcu that is logging this is next.
              r'- (?P<%s>\w+) - '
              # Next, we have more log outputs before the actual line.
              # Information about the file line, logging function etc.
              # Anchor on EC3PO Console, LogConsoleOutput and dev/pts.
              # NOTE: if the log format changes, this regex needs to be
              # adjusted.
              r'EC3PO\.Console[\s\-\w\d:.]+LogConsoleOutput - /dev/pts/\d+ - '
              # Lastly, we get the MCU's console line.
              r'(?P<%s>.+$)' % (MCU_GROUP, LINE_GROUP))
    MCU_EXTRACTOR = re.compile(MCU_RE)

    # Suffix to identify compressed logfiles.
    COMPRESSION_SUFFIX = '.tbz2'

    # A suffix to mark servod log directories that came from instance that
    # ran during this servo_host, but are not the last one running e.g. when
    # an instance (on purpose, or due to a bug) restarted in the middle of the
    # run.
    OLD_LOG_SUFFIX = 'old'

    def _init_attributes(self):
        self._servo_state = None
        self.servo_port = None
        self.servo_board = None
        self.servo_model = None
        self.servo_serial = None
        self._servo = None
        self._servod_server_proxy = None
        self._initial_instance_ts = None
        # Flag to make sure that multiple calls to close do not result in the
        # logic executing multiple times.
        self._closed = False

    def _initialize(self, servo_host='localhost',
                    servo_port=DEFAULT_PORT, servo_board=None,
                    servo_model=None, servo_serial=None, is_in_lab=None,
                    *args, **dargs):
        """Initialize a ServoHost instance.

        A ServoHost instance represents a host that controls a servo.

        @param servo_host: Name of the host where the servod process
                           is running.
        @param servo_port: Port the servod process is listening on. Defaults
                           to the SERVOD_PORT environment variable if set,
                           otherwise 9999.
        @param servo_board: Board that the servo is connected to.
        @param servo_model: Model that the servo is connected to.
        @param is_in_lab: True if the servo host is in Cros Lab. Default is set
                          to None, for which utils.host_is_in_lab_zone will be
                          called to check if the servo host is in Cros lab.

        """
        super(ServoHost, self)._initialize(hostname=servo_host,
                                           is_in_lab=is_in_lab, *args, **dargs)
        self._init_attributes()
        self.servo_port = int(servo_port)
        self.servo_board = servo_board
        self.servo_model = servo_model
        self.servo_serial = servo_serial

        # The location of the log files on the servo host for this instance.
        self.remote_log_dir = '%s_%s' % (self.SERVOD_LOG_PREFIX,
                                         self.servo_port)
        # Path of the servo host lock file.
        self._lock_file = (self.TEMP_FILE_DIR + str(self.servo_port)
                           + self.LOCK_FILE_POSTFIX)
        # File path to declare a reboot request.
        self._reboot_file = (self.TEMP_FILE_DIR + str(self.servo_port)
                             + self.REBOOT_FILE_POSTFIX)

        # Lock the servo host if it's an in-lab labstation to prevent other
        # task to reboot it until current task completes. We also wait and
        # make sure the labstation is up here, in the case of the labstation is
        # in the middle of reboot.
        self._is_locked = False
        if (self.wait_up(self.REBOOT_TIMEOUT) and self.is_in_lab()
            and self.is_labstation()):
            self._lock()

        self._repair_strategy = (
                servo_repair.create_servo_repair_strategy())

    def __str__(self):
        return "<%s '%s:%s'>" % (
                type(self).__name__, self.hostname, self.servo_port)

    def connect_servo(self):
        """Establish a connection to the servod server on this host.

        Initializes `self._servo` and then verifies that all network
        connections are working.  This will create an ssh tunnel if
        it's required.

        As a side effect of testing the connection, all signals on the
        target servo are reset to default values, and the USB stick is
        set to the neutral (off) position.
        """
        servo_obj = servo.Servo(servo_host=self, servo_serial=self.servo_serial)
        self._servo = servo_obj
        timeout, _ = retry.timeout(
                servo_obj.initialize_dut,
                timeout_sec=self.INITIALIZE_SERVO_TIMEOUT_SECS)
        if timeout:
            raise hosts.AutoservVerifyError(
                    'Servo initialize timed out.')


    def disconnect_servo(self):
        """Disconnect our servo if it exists.

        If we've previously successfully connected to our servo,
        disconnect any established ssh tunnel, and set `self._servo`
        back to `None`.
        """
        if self._servo:
            # N.B. This call is safe even without a tunnel:
            # rpc_server_tracker.disconnect() silently ignores
            # unknown ports.
            self.rpc_server_tracker.disconnect(self.servo_port)
            self._servo = None


    def _create_servod_server_proxy(self):
        """Create a proxy that can be used to communicate with servod server.

        @returns: An xmlrpclib.ServerProxy that is connected to the servod
                  server on the host.
        """
        if (servo_constants.ENABLE_SSH_TUNNEL_FOR_SERVO
                and not self.is_localhost()):
            return self.rpc_server_tracker.xmlrpc_connect(
                    None, self.servo_port,
                    ready_test_name=self.SERVO_READY_METHOD,
                    timeout_seconds=60,
                    request_timeout_seconds=3600,
                    server_desc=str(self))
        else:
            remote = 'http://%s:%s' % (self.hostname, self.servo_port)
            return xmlrpclib.ServerProxy(remote)


    def get_servod_server_proxy(self):
        """Return a cached proxy if exists; otherwise, create a new one.

        @returns: An xmlrpclib.ServerProxy that is connected to the servod
                  server on the host.
        """
        # Single-threaded execution, no race
        if self._servod_server_proxy is None:
            self._servod_server_proxy = self._create_servod_server_proxy()
        return self._servod_server_proxy


    def verify(self, silent=False):
        """Update the servo host and verify it's in a good state.

        @param silent   If true, suppress logging in `status.log`.
        """
        message = 'Beginning verify for servo host %s port %s serial %s'
        message %= (self.hostname, self.servo_port, self.servo_serial)
        self.record('INFO', None, None, message)
        try:
            self._repair_strategy.verify(self, silent)
            self._servo_state = servo_constants.SERVO_STATE_WORKING
            self.record('INFO', None, None,
                        'ServoHost verify set servo_state as WORKING')
        except Exception as e:
            self._servo_state = servo_constants.SERVO_STATE_BROKEN
            self.record('INFO', None, None,
                        'ServoHost verify set servo_state as BROKEN')
            if self._is_critical_error(e):
                raise


    def get_image_name_from_usbkey(self, usbkey_dev):
        """Mount usb drive and check ChromeOS image name on it if there is
        one. This method assumes the image_usbkey_direction is already set
        to servo side.

        @param: usbkey_dev  usbkey dev path(e.g. /dev/sdb).

        @returns: image_name on the usbkey, e.g. nami-release/R82.10138.0.0,
                  or empty string if no test image detected, or unexpected
                  error occurred.
        @raises   AutoservRepairError if mount usb drive failed with no
                  specific device error, which usually means the usbkey is
                  not existing or in bad shape.
        """
        usb_mount_path = '/media/servo_usb/%s' % self.servo_port
        unmount_cmd = 'umount %s' % usb_mount_path
        # ChromeOS root fs is in /dev/sdx3
        mount_cmd = 'mount -o ro %s3 %s' % (usbkey_dev, usb_mount_path)
        # Unmount if there is an existing stale mount.
        self.run(unmount_cmd, ignore_status=True)
        # Create if the mount point is not existing.
        self.run('mkdir -p %s' % usb_mount_path)
        try:
            # Attempt to mount the usb drive.
            mount_result = self.run(mount_cmd, ignore_status=True)
            if mount_result.exit_status == 0:
                release_content = self.run(
                    'cat %s/etc/lsb-release' % usb_mount_path,
                    ignore_status=True).stdout.strip()

                if not re.search(r'RELEASE_TRACK=.*test', release_content):
                    logging.info('The image on usbkey is not a test image')
                    return ''

                return lsbrelease_utils.get_chromeos_release_builder_path(
                    lsb_release_content=release_content)
            elif (mount_result.exit_status == 32
                  and 'does not exist' in mount_result.stderr):
                ## probe_host_usb_dev() sometimes return stale record.
                raise hosts.AutoservRepairError('No usbkey detected on servo,'
                                                ' the usbkey may be either'
                                                ' missing or broken.',
                                                'missing usbkey')
            else:
                logging.error('Unexpected error occurred on mount usb'
                              ' drive, skipping usbkey validation.')
                return ''
        finally:
            logging.debug('Usbkey validation compeleted, unmounting the'
                          ' usb drive.')
            self.run(unmount_cmd, ignore_status=True)


    def validate_image_usbkey(self):
        """This method validate if there is a usbkey on servo that accessible
        to servohost. It will get the usb disk path, and then mount the usb,
        if image_name is provided, this method will also check if the image
        is already on the usb drive, so we can avoid unnecessary download and
        flash to usb device.

        @returns: image_name on the usbkey, e.g. nami-release/R82.10138.0.0,
                  or empty string if no test image detected, or unexpected
                  error occurred.
        @raises:  AutoservRepairError if the usbkey is not detected on servo.
        """
        logging.info('Validating image usbkey on servo.')
        usbkey_dev = None
        try:
            usbkey_dev = self._servo.probe_host_usb_dev()
        except Exception as e:
            # We don't want any unexpected or transient servo communicating
            # failure block usb repair, so capture all errors here.
            logging.error(e, exc_info=True)
            logging.error('Unexpected error occurred on get usbkey dev path,'
                          ' skipping usbkey validation.')
            return ''

        if not usbkey_dev:
            raise hosts.AutoservRepairError('No usbkey detected on servo, the'
                                            ' usbkey may be either missing or'
                                            ' broken.', 'missing usbkey')
        return self.get_image_name_from_usbkey(usbkey_dev)


    def repair(self, silent=False):
        """Attempt to repair servo host.

        @param silent   If true, suppress logging in `status.log`.
        """
        message = 'Beginning repair for servo host %s port %s serial %s'
        message %= (self.hostname, self.servo_port, self.servo_serial)
        self.record('INFO', None, None, message)
        try:
            self._repair_strategy.repair(self, silent)
            self._servo_state = servo_constants.SERVO_STATE_WORKING
            self.record('INFO', None, None,
                        'ServoHost repair set servo_state as WORKING')
            # If target is a labstation then try to withdraw any existing
            # reboot request created by this servo because it passed repair.
            if self.is_labstation():
                self.withdraw_reboot_request()
        except Exception as e:
            self._servo_state = servo_constants.SERVO_STATE_BROKEN
            self.record('INFO', None, None,
                        'ServoHost repair set servo_state as BROKEN')
            if self._is_critical_error(e):
                self.disconnect_servo()
                self.stop_servod()
                raise


    def _is_critical_error(self, error):
        if (isinstance(error, hosts.AutoservVerifyDependencyError)
            and not error.is_critical()):
            logging.warning('Non-critical verify failure(s) detected during'
                            ' verify/repair servo, servo connection will'
                            ' still up but may not fully functional.'
                            ' Some repair actions and servo depended'
                            ' tests may not run.')
            return False
        logging.info('Critical verify failure(s) detected during repair/verify'
                     ' servo. Disconnecting servo and stop servod, all repair '
                     'action and tests that depends on servo will not run.')
        return True


    def get_servo(self):
        """Get the cached servo.Servo object.

        @return: a servo.Servo object.
        @rtype: autotest_lib.server.cros.servo.servo.Servo
        """
        return self._servo


    def request_reboot(self):
        """Request servohost to be rebooted when it's safe to by touch a file.
        """
        logging.debug('Request to reboot servohost %s has been created by '
                      'servo with port # %s', self.hostname, self.servo_port)
        self.run('touch %s' % self._reboot_file, ignore_status=True)


    def withdraw_reboot_request(self):
        """Withdraw a servohost reboot request if exists by remove the flag
        file.
        """
        logging.debug('Withdrawing request to reboot servohost %s that created'
                      ' by servo with port # %s if exists.',
                      self.hostname, self.servo_port)
        self.run('rm -f %s' % self._reboot_file, ignore_status=True)


    def start_servod(self, quick_startup=False):
        """Start the servod process on servohost.
        """
        # Skip if running on the localhost.(crbug.com/1038168)
        if self.is_localhost():
            logging.debug("Servohost is a localhost, skipping start servod.")
            return

        cmd = 'start servod'
        if self.servo_board:
            cmd += ' BOARD=%s' % self.servo_board
            if self.servo_model:
                cmd += ' MODEL=%s' % self.servo_model
        else:
            logging.warning('Board for DUT is unknown; starting servod'
                            ' assuming a pre-configured board.')

        cmd += ' PORT=%d' % self.servo_port
        if self.servo_serial:
            cmd += ' SERIAL=%s' % self.servo_serial

        # Start servod with dual_v4 if the DUT/servo from designated pools.
        dut_host_info = self.get_dut_host_info()
        if dut_host_info:
            if bool(dut_host_info.pools &
                    servo_constants.POOLS_SUPPORT_DUAL_V4):
                logging.debug('The DUT is detected in following designated'
                              ' pools %s,starting servod with DUAL_V4 option.',
                              servo_constants.POOLS_SUPPORT_DUAL_V4)
                cmd += ' DUAL_V4=1'

        # Remove the symbolic links from the logs. This helps ensure that
        # a failed servod instantiation does not cause us to grab old logs
        # by mistake.
        self.remove_latest_log_symlinks()
        self.run(cmd, timeout=60)

        # There's a lag between when `start servod` completes and when
        # the _ServodConnectionVerifier trigger can actually succeed.
        # The call to time.sleep() below gives time to make sure that
        # the trigger won't fail after we return.

        # Normally servod on servo_v3 and labstation take ~10 seconds to ready,
        # But in the rare case all servo on a labstation are in heavy use they
        # may take ~30 seconds. So the timeout value will double these value,
        # and we'll try quick start up when first time initialize servohost,
        # and use standard start up timeout in repair.
        if quick_startup:
            timeout = servo_constants.SERVOD_QUICK_STARTUP_TIMEOUT
        else:
            timeout = servo_constants.SERVOD_STARTUP_TIMEOUT
        logging.debug('Wait %s seconds for servod process fully up.', timeout)
        time.sleep(timeout)
        # Cache the initial instance timestamp to check against servod restarts
        self._initial_instance_ts = self.get_instance_logs_ts()


    def stop_servod(self):
        """Stop the servod process on servohost.
        """
        # Skip if running on the localhost.(crbug.com/1038168)
        if self.is_localhost():
            logging.debug("Servohost is a localhost, skipping stop servod.")
            return

        logging.debug('Stopping servod on port %s', self.servo_port)
        self.run('stop servod PORT=%d' % self.servo_port,
                 timeout=60, ignore_status=True)
        logging.debug('Wait %s seconds for servod process fully teardown.',
                      servo_constants.SERVOD_TEARDOWN_TIMEOUT)
        time.sleep(servo_constants.SERVOD_TEARDOWN_TIMEOUT)


    def restart_servod(self, quick_startup=False):
        """Restart the servod process on servohost.
        """
        self.stop_servod()
        self.start_servod(quick_startup)


    def _extract_compressed_logs(self, logdir, relevant_files):
        """Decompress servod logs in |logdir|.

        @param logdir: directory containing compressed servod logs.
        @param relevant_files: list of files in |logdir| to consider.

        @returns: tuple, (tarfiles, files) where
                  tarfiles: list of the compressed filenames that have been
                            extracted and deleted
                  files:  list of the uncompressed files that were generated
        """
        # For all tar-files, first extract them to the directory, and
        # then let the common flow handle them.
        tarfiles = [cf for cf in relevant_files if
                    cf.endswith(self.COMPRESSION_SUFFIX)]
        files = []
        for f in tarfiles:
            norm_name = os.path.basename(f)[:-len(self.COMPRESSION_SUFFIX)]
            with tarfile.open(f) as tf:
                # Each tarfile has only one member, as
                # that's the compressed log.
                member = tf.members[0]
                # Manipulate so that it only extracts the basename, and not
                # the directories etc.
                member.name = norm_name
                files.append(os.path.join(logdir, member.name))
                tf.extract(member, logdir)
            # File has been extracted: remove the compressed file.
            os.remove(f)
        return tarfiles, files

    def _extract_mcu_logs(self, log_subdir):
        """Extract MCU (EC, Cr50, etc) console output from servod debug logs.

        Using the MCU_EXTRACTOR regex (above) extract and split out MCU console
        lines from the logs to generate invidiual console logs e.g. after
        this method, you can find an ec.txt and servo_v4.txt in |log_dir| if
        those MCUs had any console input/output.

        @param log_subdir: directory with log.DEBUG.txt main servod debug logs.
        """
        # Extract the MCU for each one. The MCU logs are only in the .DEBUG
        # files
        mcu_lines_file = os.path.join(log_subdir, 'log.DEBUG.txt')
        if not os.path.exists(mcu_lines_file):
            logging.info('No DEBUG logs found to extract MCU logs from.')
            return
        mcu_files = {}
        mcu_file_template = '%s.txt'
        with open(mcu_lines_file, 'r') as f:
            for line in f:
                match = self.MCU_EXTRACTOR.match(line)
                if match:
                    mcu = match.group(self.MCU_GROUP).lower()
                    line = match.group(self.LINE_GROUP)
                    if mcu not in mcu_files:
                        mcu_file = os.path.join(log_subdir,
                                                mcu_file_template % mcu)
                        mcu_files[mcu] = open(mcu_file, 'a')
                    fd = mcu_files[mcu]
                    fd.write(line + '\n')
        for f in mcu_files:
            mcu_files[f].close()


    def remove_latest_log_symlinks(self):
        """Remove the conveninence symlinks 'latest' servod logs."""
        symlink_wildcard = '%s/latest*' % self.remote_log_dir
        cmd = 'rm ' + symlink_wildcard
        self.run(cmd, stderr_tee=None, ignore_status=True)

    def probe_servod_restart(self, instance_ts, outdir):
        """Grab servod logs from previous instances if part of this session.

        If since the last time this host called start_servod() servod crashed
        and restarted, this helper finds those logs as well, and stores them
        with the |OLD_LOG_SUFFIX| to investigate if necessary.

        It also issues a panicinfo command to servo devices after the restart
        to try and collect reboot information for debugging.

        @param instance_ts: the log timestamp that the current instance uses
        @param outdir: directory to create a subdirectory into to place the
                       servod logs into.
        """
        if self._initial_instance_ts is None:
            logging.info('No log timestamp grabbed successfully on servod '
                         'startup. Cannot check device restarts. Ignoring.')
            return
        if instance_ts == self._initial_instance_ts:
            logging.debug('Servod appears to have run without restarting')
            return
        # Servod seems to have restarted (at least once). |_initial_instance_ts|
        # is the first timestamp, and instance_ts is the current timestamp. Find
        # all timestamps in between them, and grab the logs for each.
        tss = self._find_instance_timestamps_between(self._initial_instance_ts,
                                                     instance_ts)
        logging.info('Servod has restarted %d times between the start and the '
                     'end of this servo_host.', len(tss))
        logging.info('This might be an issue. Will extract all logs from each '
                     'instance.')
        logging.info('Logs that are not the currently running (about to turn '
                     'down) instance are maked with a .%s in their folder.',
                     self.OLD_LOG_SUFFIX)
        for ts in tss:
            self.get_instance_logs(ts, outdir, old=True)
        # Lastly, servod has restarted due to a potential issue. Try to get
        # panic information from servo micro and servo v4 for the current logs.
        for mcu in ['servo_micro', 'servo_v4']:
            ctrl = '%s_uart_cmd' % mcu
            if self._servo.has_control(ctrl):
                logging.info('Trying to retrieve %r panicinfo into logs', mcu)
                try:
                    self._servo.set_nocheck(ctrl, 'panicinfo')
                except error.TestFail as e:
                    logging.error('Failed to generate panicinfo for %r logs. '
                                  '%s', mcu, str(e))

    def grab_logs(self, outdir):
        """Retrieve logs from servo_host to |outdir|/servod_{port}.{ts}/.

        This method grabs all logs since servod was last restarted by this host
        i.e. if servod restarts in the middle of the run (intentionally or not)
        those logs will all be grabbed as well.

        @param outdir: directory to create a subdirectory into to place the
                       servod logs into.
        """
        instance_ts = self.get_instance_logs_ts()
        if instance_ts is not None:
            self.probe_servod_restart(instance_ts, outdir)
            self.get_instance_logs(instance_ts, outdir)

    def _find_instance_timestamps_between(self, start_ts, end_ts):
        """Find all log timestamps between [start_ts, end_ts).

        @param start_ts: str, earliest log timestamp of interest
        @param end_ts: str, latest log timestamp of interest

        @returns: list, all timestamps between start_ts and end_ts, end_ts
                  exclusive, on the servo_host. An empty list on errors
        """
        # Simply get all timestamp, and then sort and remove
        cmd = 'ls %s' % self.remote_log_dir
        res = self.run(cmd, stderr_tee=None, ignore_status=True)
        if res.exit_status != 0:
            # Here we failed to find anything.
            logging.info('Failed to find remote servod logs. Ignoring.')
            return []
        logfiles = res.stdout.strip().split()
        timestamps = set()
        for logfile in logfiles:
            ts_match = self.TS_EXTRACTOR.match(logfile)
            if not ts_match:
                # Simply ignore files that fail the check. It might be the
                # 'latest' symlinks or random files.
                continue
            timestamps.add(ts_match.group(self.TS_GROUP))
        # At this point we have all unique timestamps.
        timestamps = sorted(timestamps)
        for ts in [start_ts, end_ts]:
            if ts not in timestamps:
                logging.error('Timestamp %r not in servod logs. Cannot query '
                              'for timestamps in between %r and %r', ts,
                              start_ts, end_ts)
                return []
        return timestamps[timestamps.index(start_ts):timestamps.index(end_ts)]

    def get_instance_logs_ts(self):
        """Retrieve the currently running servod instance's log timestamp

        @returns: str, timestamp for current instance, or None on failure
        """
        # First, extract the timestamp. This cmd gives the real filename of
        # the latest aka current log file.
        cmd = ('if [ -f %(dir)s/latest.DEBUG ];'
               'then realpath %(dir)s/latest.DEBUG;'
               'elif [ -f %(dir)s/latest ];'
               'then realpath %(dir)s/latest;'
               'else exit %(code)d;'
               'fi' % {'dir': self.remote_log_dir,
                       'code': self.NO_SYMLINKS_CODE})
        res = self.run(cmd, stderr_tee=None, ignore_status=True)
        if res.exit_status != 0:
            if res.exit_status == self.NO_SYMLINKS_CODE:
                logging.warning('servod log latest symlinks not found. '
                                'This is likely due to an error starting up '
                                'servod. Ignoring..')
            else:
                logging.warning('Failed to find servod logs on servo host.')
                logging.warning(res.stderr.strip())
            return None
        fname = os.path.basename(res.stdout.strip())
        # From the fname, ought to extract the timestamp using the TS_EXTRACTOR
        ts_match = self.TS_EXTRACTOR.match(fname)
        if not ts_match:
            logging.warning('Failed to extract timestamp from servod log file '
                            '%r. Skipping. The servo host is using outdated '
                            'servod logging and needs to be updated.', fname)
            return None
        return ts_match.group(self.TS_GROUP)

    def get_instance_logs(self, instance_ts, outdir, old=False):
        """Collect all logs with |instance_ts| and dump into a dir in |outdir|

        This method first collects all logs on the servo_host side pertaining
        to this servod instance (port, instatiation). It glues them together
        into combined log.[level].txt files and extracts all available MCU
        console I/O from the logs into individual files e.g. servo_v4.txt

        All the output can be found in a directory inside |outdir| that
        this generates based on |LOG_DIR|, the servod port, and the instance
        timestamp on the servo_host side.

        @param instance_ts: log timestamp to grab logfiles for
        @param outdir: directory to create a subdirectory into to place the
                       servod logs into.
        @param old: bool, whether to append |OLD_LOG_SUFFIX| to output dir
        """
        # Create the local results log dir.
        log_dir = os.path.join(outdir, '%s_%s.%s' % (self.LOG_DIR,
                                                     str(self.servo_port),
                                                     instance_ts))
        if old:
          log_dir = '%s.%s' % (log_dir, self.OLD_LOG_SUFFIX)
        logging.info('Saving servod logs to %s.', log_dir)
        os.mkdir(log_dir)
        # Now, get all files with that timestamp.
        cmd = 'find %s -maxdepth 1 -name "log.%s*"' % (self.remote_log_dir,
                                                       instance_ts)
        res = self.run(cmd, stderr_tee=None, ignore_status=True)
        files = res.stdout.strip().split()
        try:
            self.get_file(files, log_dir, try_rsync=False)

        except error.AutoservRunError as e:
            result = e.result_obj
            if result.exit_status != 0:
                stderr = result.stderr.strip()
                logging.warning("Couldn't retrieve servod logs. Ignoring: %s",
                                stderr or '\n%s' % result)
            return
        local_files = [os.path.join(log_dir, f) for f in os.listdir(log_dir)]
        # TODO(crrev.com/c/1793030): remove no-level case once CL is pushed
        for level_name in ('DEBUG', 'INFO', 'WARNING', ''):
            # Create the joint files for each loglevel. i.e log.DEBUG
            joint_file = self.JOINT_LOG_PREFIX
            if level_name:
                joint_file = '%s.%s' % (self.JOINT_LOG_PREFIX, level_name)
            # This helps with some online tools to avoid complaints about an
            # unknown filetype.
            joint_file = joint_file + '.txt'
            joint_path = os.path.join(log_dir, joint_file)
            files = [f for f in local_files if level_name in f]
            if not files:
                # TODO(crrev.com/c/1793030): remove no-level case once CL
                # is pushed
                continue
            # Extract compressed logs if any.
            compressed, extracted = self._extract_compressed_logs(log_dir,
                                                                  files)
            files = list(set(files) - set(compressed))
            files.extend(extracted)
            # Need to sort. As they all share the same timestamp, and
            # loglevel, the index itself is sufficient. The highest index
            # is the oldest file, therefore we need a descending sort.
            def sortkey(f, level=level_name):
                """Custom sortkey to sort based on rotation number int."""
                if f.endswith(level_name): return 0
                return int(f.split('.')[-1])

            files.sort(reverse=True, key=sortkey)
            # Just rename the first file rather than building from scratch.
            os.rename(files[0], joint_path)
            with open(joint_path, 'a') as joint_f:
                for logfile in files[1:]:
                    # Transfer the file to the joint file line by line.
                    with open(logfile, 'r') as log_f:
                        for line in log_f:
                            joint_f.write(line)
                    # File has been written over. Delete safely.
                    os.remove(logfile)
            # Need to remove all files form |local_files| so we don't
            # analyze them again.
            local_files = list(set(local_files) - set(files) - set(compressed))
        # Lastly, extract MCU logs from the joint logs.
        self._extract_mcu_logs(log_dir)


    def _lock(self):
        """lock servohost by touching a file.
        """
        logging.debug('Locking servohost %s by touching %s file',
                      self.hostname, self._lock_file)
        self.run('touch %s' % self._lock_file, ignore_status=True)
        self._is_locked = True


    def _unlock(self):
        """Unlock servohost by removing the lock file.
        """
        logging.debug('Unlocking servohost by removing %s file',
                      self._lock_file)
        self.run('rm %s' % self._lock_file, ignore_status=True)
        self._is_locked = False


    def close(self):
        """Close the associated servo and the host object."""
        if self._closed:
            logging.debug('ServoHost is already closed.')
            return
        if self._servo:
            outdir = None if not self.job else self.job.resultdir
            # In some cases when we run as lab-tools, the job object is None.
            self._servo.close(outdir)

        if self.job and not self.is_localhost():
            # Grab all logs from this servod instance before stopping servod.
            # TODO(crbug.com/1011516): once enabled, remove the check against
            # localhost and instead check against log-rotiation enablement.
            try:
                self.grab_logs(self.job.resultdir)
            except error.AutoservRunError as e:
                logging.info('Failed to grab servo logs due to: %s. '
                             'This error is forgiven.', str(e))

        if self._is_locked:
            # Remove the lock if the servohost has been locked.
            try:
                self._unlock()
            except error.AutoservSSHTimeout:
                logging.error('Unlock servohost failed due to ssh timeout.'
                              ' It may caused by servohost went down during'
                              ' the task.')
        # We want always stop servod after task to minimum the impact of bad
        # servod process interfere other servods.(see crbug.com/1028665)
        try:
            self.stop_servod()
        except error.AutoservRunError as e:
            logging.info("Failed to stop servod due to:\n%s\n"
                         "This error is forgiven.", str(e))

        super(ServoHost, self).close()
        # Mark closed.
        self._closed = True


    def get_servo_state(self):
        if self._servo_state is None:
            return servo_constants.SERVO_STATE_UNKNOWN
        return self._servo_state


def make_servo_hostname(dut_hostname):
    """Given a DUT's hostname, return the hostname of its servo.

    @param dut_hostname: hostname of a DUT.

    @return hostname of the DUT's servo.

    """
    host_parts = dut_hostname.split('.')
    host_parts[0] = host_parts[0] + '-servo'
    return '.'.join(host_parts)


def servo_host_is_up(servo_hostname):
    """Given a servo host name, return if it's up or not.

    @param servo_hostname: hostname of the servo host.

    @return True if it's up, False otherwise
    """
    # Technically, this duplicates the SSH ping done early in the servo
    # proxy initialization code.  However, this ping ends in a couple
    # seconds when if fails, rather than the 60 seconds it takes to decide
    # that an SSH ping has timed out.  Specifically, that timeout happens
    # when our servo DNS name resolves, but there is no host at that IP.
    logging.info('Pinging servo host at %s', servo_hostname)
    ping_config = ping_runner.PingConfig(
            servo_hostname, count=3,
            ignore_result=True, ignore_status=True)
    return ping_runner.PingRunner().ping(ping_config).received > 0


def _map_afe_board_to_servo_board(afe_board):
    """Map a board we get from the AFE to a servo appropriate value.

    Many boards are identical to other boards for servo's purposes.
    This function makes that mapping.

    @param afe_board string board name received from AFE.
    @return board we expect servo to have.

    """
    KNOWN_SUFFIXES = ['-freon', '_freon', '_moblab', '-cheets']
    BOARD_MAP = {'gizmo': 'panther'}
    mapped_board = afe_board
    if afe_board in BOARD_MAP:
        mapped_board = BOARD_MAP[afe_board]
    else:
        for suffix in KNOWN_SUFFIXES:
            if afe_board.endswith(suffix):
                mapped_board = afe_board[0:-len(suffix)]
                break
    if mapped_board != afe_board:
        logging.info('Mapping AFE board=%s to %s', afe_board, mapped_board)
    return mapped_board


def get_servo_args_for_host(dut_host):
    """Return servo data associated with a given DUT.

    @param dut_host   Instance of `Host` on which to find the servo
                      attributes.
    @return `servo_args` dict with host and an optional port.
    """
    info = dut_host.host_info_store.get()
    servo_args = {k: v for k, v in info.attributes.iteritems()
                  if k in servo_constants.SERVO_ATTR_KEYS}

    if servo_constants.SERVO_PORT_ATTR in servo_args:
        try:
            servo_args[servo_constants.SERVO_PORT_ATTR] = int(
                servo_args[servo_constants.SERVO_PORT_ATTR])
        except ValueError:
            logging.error('servo port is not an int: %s',
                          servo_args[servo_constants.SERVO_PORT_ATTR])
            # Reset servo_args because we don't want to use an invalid port.
            servo_args.pop(servo_constants.SERVO_HOST_ATTR, None)

    if info.board:
        servo_board = _map_afe_board_to_servo_board(info.board)
        servo_args[servo_constants.SERVO_BOARD_ATTR] = servo_board
    if info.model:
        servo_args[servo_constants.SERVO_MODEL_ATTR] = info.model
    return servo_args if servo_constants.SERVO_HOST_ATTR in servo_args else None


def _tweak_args_for_ssp_moblab(servo_args):
    if (servo_args[servo_constants.SERVO_HOST_ATTR]
            in ['localhost', '127.0.0.1']):
        servo_args[servo_constants.SERVO_HOST_ATTR] = _CONFIG.get_config_value(
                'SSP', 'host_container_ip', type=str, default=None)


def create_servo_host(dut, servo_args, try_lab_servo=False,
                      try_servo_repair=False, dut_host_info=None):
    """Create a ServoHost object for a given DUT, if appropriate.

    This function attempts to create and verify or repair a `ServoHost`
    object for a servo connected to the given `dut`, subject to various
    constraints imposed by the parameters:
      * When the `servo_args` parameter is not `None`, a servo
        host must be created, and must be checked with `repair()`.
      * Otherwise, if a servo exists in the lab and `try_lab_servo` is
        true:
          * If `try_servo_repair` is true, then create a servo host and
            check it with `repair()`.
          * Otherwise, if the servo responds to `ping` then create a
            servo host and check it with `verify()`.

    In cases where `servo_args` was not `None`, repair failure
    exceptions are passed back to the caller; otherwise, exceptions
    are logged and then discarded.  Note that this only happens in cases
    where we're called from a test (not special task) control file that
    has an explicit dependency on servo.  In that case, we require that
    repair not write to `status.log`, so as to avoid polluting test
    results.

    TODO(jrbarnette):  The special handling for servo in test control
    files is a thorn in my flesh; I dearly hope to see it cut out before
    my retirement.

    Parameters for a servo host consist of a host name, port number, and
    DUT board, and are determined from one of these sources, in order of
    priority:
      * Servo attributes from the `dut` parameter take precedence over
        all other sources of information.
      * If a DNS entry for the servo based on the DUT hostname exists in
        the CrOS lab network, that hostname is used with the default
        port and the DUT's board.
      * If no other options are found, the parameters will be taken
        from the `servo_args` dict passed in from the caller.

    @param dut            An instance of `Host` from which to take
                          servo parameters (if available).
    @param servo_args     A dictionary with servo parameters to use if
                          they can't be found from `dut`.  If this
                          argument is supplied, unrepaired exceptions
                          from `verify()` will be passed back to the
                          caller.
    @param try_lab_servo  If not true, servo host creation will be
                          skipped unless otherwise required by the
                          caller.
    @param try_servo_repair  If true, check a servo host with
                          `repair()` instead of `verify()`.

    @returns: A ServoHost object or None. See comments above.

    """
    servo_dependency = servo_args is not None
    if dut is not None and (try_lab_servo or servo_dependency):
        servo_args_override = get_servo_args_for_host(dut)
        if servo_args_override is not None:
            if utils.in_moblab_ssp():
                _tweak_args_for_ssp_moblab(servo_args_override)
            logging.debug(
                    'Overriding provided servo_args (%s) with arguments'
                    ' determined from the host (%s)',
                    servo_args,
                    servo_args_override,
            )
            servo_args = servo_args_override

    if servo_args is None:
        logging.debug('No servo_args provided, and failed to find overrides.')
        if try_lab_servo or servo_dependency:
            return None, servo_constants.SERVO_STATE_NOT_CONNECTED
        else:
            # For regular test case which not required the servo
            return None, None

    servo_hostname = servo_args.get(servo_constants.SERVO_HOST_ATTR)
    servo_port = servo_args.get(servo_constants.SERVO_PORT_ATTR)
    if not _is_servo_host_information_exist(servo_hostname, servo_port):
        logging.debug(
            'Servo connection info missed hostname: %s , port: %s',
            servo_hostname, servo_port)
        return None, servo_constants.SERVO_STATE_NOT_CONNECTED
    if not is_servo_host_information_valid(servo_hostname, servo_port):
        logging.debug(
            'Servo connection info is incorrect hostname: %s , port: %s',
            servo_hostname, servo_port)
        return None, servo_constants.SERVO_STATE_WRONG_CONFIG
    if (not servo_dependency and not try_servo_repair and
            not servo_host_is_up(servo_hostname)):
        logging.debug('ServoHost is not up.')
        return None, servo_constants.SERVO_STATE_BROKEN

    newhost = ServoHost(**servo_args)
    try:
        newhost.restart_servod(quick_startup=True)
    except error.AutoservSSHTimeout:
        logging.warning("Restart servod failed due ssh connection "
                        "to servohost timed out. This error is forgiven"
                        " here, we will retry in servo repair process.")
    except error.AutoservRunError as e:
        logging.warning("Restart servod failed due to:\n%s\n"
                        "This error is forgiven here, we will retry"
                        " in servo repair process.", str(e))

    # TODO(gregorynisbet): Clean all of this up.
    logging.debug('create_servo_host: attempt to set info store on '
                  'servo host')
    try:
        if dut_host_info is None:
            logging.debug('create_servo_host: dut_host_info is '
                          'None, skipping')
        else:
            newhost.set_dut_host_info(dut_host_info)
            logging.debug('create_servo_host: successfully set info '
                          'store')
    except Exception:
        logging.error("create_servo_host: (%s)", traceback.format_exc())

    # Note that the logic of repair() includes everything done
    # by verify().  It's sufficient to call one or the other;
    # we don't need both.
    if servo_dependency:
        newhost.repair(silent=True)
        return newhost, newhost.get_servo_state()

    if try_servo_repair:
        try:
            newhost.repair()
        except Exception:
            logging.exception('servo repair failed for %s', newhost.hostname)
    else:
        try:
            newhost.verify()
        except Exception:
            logging.exception('servo verify failed for %s', newhost.hostname)
    return newhost, newhost.get_servo_state()


def _is_servo_host_information_exist(hostname, port):
    if hostname is None or len(hostname.strip()) == 0:
        return False
    if port is None:
        return False
    if not type(port) is int:
        try:
            int(port)
        except ValueError:
            return False

    return True


def is_servo_host_information_valid(hostname, port):
    if not _is_servo_host_information_exist(hostname, port):
        return False
    # checking range and correct of the port
    port_int = int(port)
    if port_int < 1 or port_int > 65000:
        return False
    # we expecting host contain only latters, digits and '-' or '_'
    if not re.match('[a-zA-Z0-9-_\.]*$', hostname) or len(hostname) < 5:
        return False
    return True
