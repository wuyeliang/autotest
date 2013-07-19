# -*- coding: utf-8; tab-width: 4; python-indent: 4 -*-
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This is a factory test for audio quality. External equipment will send
# command through ethernet to configure the audio loop path. Note that it's
# External equipment's responsibility to capture and analyze the audio signal.

import binascii
import logging
import os
import re
import select
import socket
import subprocess
import tempfile
import threading
import time

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils
from autotest_lib.client.cros import factory_setup_modules
from autotest_lib.client.cros.audio import audio_helper
from cros.factory.event_log import Log
from cros.factory.goofy.goofy import CACHES_DIR
from cros.factory.test import factory
from cros.factory.test import test_ui
from cros.factory.test.event import Event
from cros.factory.test import ui as ful
from cros.factory.test import shopfloor
from cros.factory.utils import net_utils

SHOPFLOOR_TIMEOUT_SECS = 10 # Timeout for shopfloor connection.
SHOPFLOOR_RETRY_INTERVAL_SECS = 10 # Seconds to wait between retries.
INSERT_ETHERNET_DONGLE_TIMEOUT_SECS = 30 # Timeout for inserting dongle.
IP_SETUP_TIMEOUT_SECS = 10 # Timeout for setting IP address.

# Host test machine crossover connected to DUT, fix local ip and port for
# communication in between.
_HOST = ''
_PORT = 8888
_LOCAL_IP = '192.168.1.2'

# Label strings.
_LABEL_CONNECTED = test_ui.MakeLabel('Connected', u'已连线')
_LABEL_WAITING = test_ui.MakeLabel('Waiting for command', u'等待指令中')
_LABEL_AUDIOLOOP = test_ui.MakeLabel('Audio looping', u'音源回放中')
_LABEL_SPEAKER_MUTE_OFF = test_ui.MakeLabel('Speaker on', u'喇叭开启')
_LABEL_DMIC_ON = test_ui.MakeLabel('Dmic on', u'LCD mic开启')
_LABEL_PLAYTONE_LEFT = test_ui.MakeLabel('Playing tone to left channel',
                        u'播音至左声道')
_LABEL_PLAYTONE_RIGHT = test_ui.MakeLabel('Playing tone to right channel',
                         u'播音至右声道')
_LABEL_WAITING_ETHERNET = test_ui.MakeLabel(
    'Waiting for Ethernet connectivity to ShopFloor, countdown',
    u'等待网路介面卡连接到 ShopFloor，倒数')
_LABEL_WAITING_IP = test_ui.MakeLabel('Waiting for IP address',
    u'等待 IP 设定')
_LABEL_CONNECT_SHOPFLOOR = test_ui.MakeLabel('Connecting to ShopFloor...',
    u'连接到 ShopFloor 中...')
_LABEL_DOWNLOADING_PARAMETERS = test_ui.MakeLabel(
    'Downloading parameters', u'下载测试规格中')
_LABEL_REMOVE_ETHERNET = test_ui.MakeLabel(
    'Remove Ethernet connectivity, coutdown', u'移除网路介面卡，倒数')
_LABEL_WAITING_FIXTURE_ETHERNET = test_ui.MakeLabel(
    'Waiting for Ethernet connectivity to audio fixture, countdown',
    u'等待网路介面卡连接到 audio 置具，倒数')
_LABEL_READY = test_ui.MakeLabel('Ready for connection', u'準备完成,等待链接')
_LABEL_PHASE_LIST = [_LABEL_WAITING_ETHERNET, _LABEL_REMOVE_ETHERNET,
    _LABEL_WAITING_FIXTURE_ETHERNET]

# Regular expression to match external commands.
_LOOP_0_RE = re.compile("(?i)loop_0")
_LOOP_1_RE = re.compile("(?i)loop_1")
_LOOP_2_RE = re.compile("(?i)loop_2")
_LOOP_3_RE = re.compile("(?i)loop_3")
_XTALK_L_RE = re.compile("(?i)xtalk_l")
_XTALK_R_RE = re.compile("(?i)xtalk_r")
_MULTITONE_RE = re.compile("(?i)multitone")
_SEND_FILE_RE = re.compile("(?i)send_file")
_SWEEP_RE = re.compile("(?i)sweep")
_TEST_COMPLETE_RE = re.compile("(?i)test_complete")
_RESULT_PASS_RE = re.compile("(?i)result_pass")
_RESULT_FAIL_RE = re.compile("(?i)result_fail")
_VERSION_RE = re.compile("(?i)version")
_CONFIG_FILE_RE = re.compile("(?i)config_file")

# Common mixer settings for special audio configurations, board specific
# settings should goes to each test list.
_DMIC_SWITCH_MIXER_SETTINGS = []
_INIT_MIXER_SETTINGS = [{'name': '"HP/Speaker Playback Switch"',
                         'value': 'on'},
                        {'name': '"Master Playback Volume"',
                         'value': '90,90'}]
_UNMUTE_SPEAKER_MIXER_SETTINGS = [{'name': '"HP/Speaker Playback Switch"',
                                   'value': 'off'}]
_MUTE_LEFT_MIXER_SETTINGS = [{'name': '"Master Playback Switch"',
                              'value': 'off,on'}]
_MUTE_RIGHT_MIXER_SETTINGS = [{'name': '"Master Playback Switch"',
                               'value': 'on,off'}]

# Logs
_LABEL_FAIL_LOGS = 'Test fail, find more detail in log.'

# Setting
_INIT_COUNTDOWN = 3
_FIXTURE_PARAMETERS = ['audio_md5', 'audio.zip']

class factory_AudioQuality(test.test):
    version = 2
    preserve_srcdir = True

    def handle_connection(self, conn, *args):
        """
        Asynchronous handler for socket connection.
        Command Protocol:
          Command1[\x05]Data1[\x05]Data2[\x04][\x03]
        One line may contains many commands. and the last character must
        be Ascii code \x03.

        use Ascii code \x05 to seperate command and data
        use Ascii code \x04 to present the end of command
        use Ascii code \x03 to present the end of list of command

        When DUT received command, DUT should reply Active status immediately.
        Format is
          Command[\x05]Active[\x04][\x03]

        When DUT executed command, DUT should return result.
        Format is
          Command[\x05]Active_Status[\x05]Result[\x05]Result_String[\x05]
          Error_Code[\x04][\x03]
        Active_Status may be:
          Active_End: executed commmand successfully
          Active_Timeout: executed command timeout
        Result may be:
          Pass: result of command is pass
          Fail: result of command is fail
        Result_String and Error_Code could be any plaintext.
        If Result_String and Error_Code are empty, you can omit these.
        For Example: Command[\x05]Active_End[\x05]Pass[\x04][\x03]
        """
        while True:
            commands = ''
            while True:
                buf = conn.recv(1024)
                commands += buf
                if not buf or buf[-1] == '\x03':
                    break

            if commands:
                logging.info("Received command %s", repr(commands))
            else:
                break

            command_list = commands[0:-2].split('\x04')
            for command in command_list:
                if not command:
                    continue
                attr_list = command.split('\x05')
                instruction = attr_list[0]
                conn.send(instruction + '\x05' + 'Active' + '\x04\x03')

                for key in self._handlers.iterkeys():
                    if key.match(instruction):
                        logging.info('match command %s', instruction)
                        self._handlers[key](conn, attr_list)
                        break

                # Respond by the received command with '_OK' postfix.
                logging.info('Respond OK')

            if self._test_complete:
                logging.info('Test completed')
                time.sleep(3)
                if self._test_passed:
                    self.ui.Pass()
                else:
                    self.ui.Fail(_LABEL_FAIL_LOGS)
        logging.info("Connection disconnect")
        return False

    def start_loop(self):
        """
        Starts the internal audio loopback.
        """
        if self._use_sox_loop:
            cmdargs = [self._ah.sox_path, '-t', 'alsa', self._input_dev, '-t',
                    'alsa', self._output_dev]
            self._loop_process = subprocess.Popen(cmdargs)
        else:
            cmdargs = [self._ah.audioloop_path, '-i', self._input_dev, '-o',
                    self._output_dev, '-c', str(self._loop_buffer_count)]
            self._loop_process = subprocess.Popen(cmdargs)

    def restore_configuration(self):
        """
        Stops all the running process and restore the mute settings.
        """
        if self._multitone_job:
            utils.nuke_subprocess(self._multitone_job.sp)
            utils.join_bg_jobs([self._multitone_job], timeout=1)
            self._multitone_job = None

        if self._sweep_job:
            utils.nuke_subprocess(self._sweep_job.sp)
            utils.join_bg_jobs([self._sweep_job], timeout=1)
            self._sweep_job = None

        if self._tone_job:
            utils.nuke_subprocess(self._tone_job.sp)
            utils.join_bg_jobs([self._tone_job], timeout=1)
            self._tone_job = None

        if self._loop_process:
            self._loop_process.kill()
            self._loop_process = None
            logging.info("Stopped audio loop process")
        self._ah.set_mixer_controls(self._init_mixer_settings)

    def send_response(self, response, args):
        # because there will not have args from test_command
        if not args or not args[0] or not args[1][0]:
            return
        conn = args[0]
        command = args[1][0]
        if response:
            conn.send(command + '\x05' + 'Active_End' + '\x05' +
                'Pass' + '\x05' + response + '\x04\x03')
        else:
            conn.send(command + '\x05' + 'Active_End' + '\x05' +
                'Pass' + '\x04\x03')

    def handle_version(self, *args):
        file_path = os.path.join(self._caches_dir, self._parameters[0])
        md5_file = open(file_path, "rb")
        rawstring = md5_file.read()
        self.send_response(rawstring.strip(), args)
        return

    def handle_config_file(self, *args):
        file_path = os.path.join(self._caches_dir, self._parameters[1])
        config_file = open(file_path, "rb")
        rawstring = config_file.read()
        rawdata = self._parameters[1] + ';' + str(len(rawstring)) + ';' + (
                binascii.b2a_hex(rawstring))

        self.send_response(rawdata, args)
        return

    def handle_send_file(self, *args):
        conn = args[0]

        attr_list = args[1]
        file_name = attr_list[1]
        size = int(attr_list[2])
        received_data = attr_list[3].replace('\x00', ' ')

        logging.info("Received file %s with size %d" , file_name, size)

        # Dump another copy of logs
        logging.info(repr(received_data))

        """
        The result logs are stored in filename ending in _[0-9]+.txt.

        Its content looks like:
        Freq [Hz]   dBV         Phase [Deg]
        100.00      -60.01      3.00
        105.93      -64.04      33.85
        112.20      -68.47      92.10
        ...

        The column count is variable. There may be up to ten columns in the
        results. Each column contains 12 characters. Because the spaces on
        the right side of last colume are stripped. So the number of column
        is the length of line divides by 12 and plus one.

        Unfortunately, we cannot read the column names in the header row
        by splitting with spaces.
        """

        match = re.search(r"(\d+)_(\d+)_(\d+).txt", file_name)
        match2 = re.search(r"(\d+)_(\d+).txt", file_name)

        if match:
            """
            serial_number and timestamp are generated by camerea test fixture.
            We can use these two strings to lookup the raw logs on fixture.
            """
            serial_number, timestamp, test_index = match.groups()

            lines = received_data.splitlines()
            header_row = lines[0]

            table = []
            """
            record the maximum column_number, to add sufficient 'nan' to
            the end of list if the spaces in the end of line are stripped.
            """
            column_number = max([len(line)/12 + 1 for line in lines[1:]])
            for line in lines[1:]:
                x = []
                for i in range(column_number):
                    x.append(float(line[i*12:i*12 + 12].strip() or 'nan'))
                table.append(x)

            test_result = {}
            """
            Remarks:
            1. cros.factory.event_log requires special format for key string
            2. because the harmonic of some frequencies are not valid, we may
               have empty values in certain fields
            3. The missing fields are always in the last columns
            """
            frequencies = dict((row[0], row[1:]) for row in table)
            test_result['frequencies'] = frequencies
            test_result['header_row'] = header_row
            test_result['serial_number'] = serial_number
            test_result['timestamp'] = timestamp

            Log(('audio_quality_test_%s' % test_index), **test_result)
        elif match2:
            serial_number, timestamp = match2.groups()

            final_result = {}
            final_result['serial_number'] = serial_number
            final_result['timestamp'] = timestamp
            final_result['data'] = received_data.replace('\r', '')

            Log('audio_quality_final_result', **final_result)
        else:
            logging.info("Unrecognizable filename %s", file_name)

        self.send_response(None, args)

    def handle_result_pass(self, *args):
        self._test_passed = True
        self.send_response(None, args)

    def handle_result_fail(self, *args):
        self._test_passed = False
        self.send_response(None, args)

    def handle_test_complete(self, *args):
        """
        Handles test completion.
        Runs post test script before ends this test

        """
        self.on_test_complete()
        self._test_complete = True
        logging.info('%s run_once finished', self.__class__)
        self.send_response(None, args)

    def handle_loop_none(self, *args):
        self.restore_configuration()
        self.ui.CallJSFunction('setMessage', _LABEL_WAITING)
        self.send_response(None, args)

    def handle_loop(self, *args):
        self.restore_configuration()
        self.ui.CallJSFunction('setMessage', _LABEL_AUDIOLOOP)
        self.start_loop()

    def handle_multitone(self, *args):
        """Plays the multi-tone wav file"""
        self.restore_configuration()
        wav_path = os.path.join(self.srcdir, '10SEC.wav')
        cmdargs = ['aplay', wav_path]
        self._multitone_job = utils.BgJob(' '.join(cmdargs))
        self.send_response(None, args)

    def handle_sweep(self, *args):
        """Plays the sweep wav file"""
        self.restore_configuration()
        wav_path = os.path.join(self.srcdir, 'sweep.wav')
        cmdargs = ['aplay', wav_path]
        self._sweep_job = utils.BgJob(' '.join(cmdargs))
        self.send_response(None, args)

    def handle_loop_jack(self, *args):
        if self._use_multitone:
            self.handle_multitone()
        else:
            self.handle_loop()
        self.ui.CallJSFunction('setMessage', _LABEL_AUDIOLOOP)
        self.send_response(None, args)

    def handle_loop_from_dmic(self, *args):
        self.handle_loop()
        self.ui.CallJSFunction('setMessage', _LABEL_AUDIOLOOP +
                _LABEL_DMIC_ON)
        self._ah.set_mixer_controls(self._dmic_switch_mixer_settings)
        self.send_response(None, args)

    def handle_loop_speaker_unmute(self, *args):
        if self._use_multitone:
            self.handle_multitone()
        else:
            self.handle_loop()
        self.ui.CallJSFunction('setMessage', _LABEL_AUDIOLOOP +
                _LABEL_SPEAKER_MUTE_OFF)
        self.unmute_speaker()
        self.send_response(None, args)

    def handle_xtalk_left(self, *args):
        self.restore_configuration()
        self.ui.CallJSFunction('setMessage', _LABEL_PLAYTONE_LEFT)
        self._ah.set_mixer_controls(self._mute_left_mixer_settings)
        cmdargs = self._ah.get_play_sine_args(1, self._output_dev)
        self._tone_job = utils.BgJob(' '.join(cmdargs))
        self.send_response(None, args)

    def handle_xtalk_right(self, *args):
        self.restore_configuration()
        self.ui.CallJSFunction('setMessage', _LABEL_PLAYTONE_RIGHT)
        self._ah.set_mixer_controls(self._mute_right_mixer_settings)
        cmdargs = self._ah.get_play_sine_args(0, self._output_dev)
        self._tone_job = utils.BgJob(' '.join(cmdargs))
        self.send_response(None, args)

    def listen_forever(self, sock):
        fd = sock.fileno()
        while True:
            _rl, _, _ = select.select([fd], [], [])
            if fd in _rl:
                conn, addr = sock.accept()
                self.handle_connection(conn)

    def init_audio_server(self):
        """
        Initialize server and start listening for external commands.
        """
        if self._init_socket:
            self.ui.CallJSFunction('setMessage', _LABEL_READY)
            return
        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((_HOST, _PORT))
        sock.listen(1)
        logging.info("Listening at port %d", _PORT)

        self._listen_thread = threading.Thread(target=self.listen_forever,
                args=(sock,))
        self._listen_thread.start()

        self.ui.CallJSFunction('setMessage', _LABEL_READY)
        self._test_phase += 1
        self._init_socket = 1

    def unmute_speaker(self):
        self._ah.set_mixer_controls(self._unmute_speaker_mixer_settings)

    def on_test_complete(self):
        """
        Restores the original state before exiting the test.
        """
        utils.system('iptables -D INPUT -p tcp --dport %s -j ACCEPT' % _PORT)
        utils.system('ifconfig %s down' % self._eth)
        utils.system('ifconfig %s up' % self._eth)
        self.restore_configuration()
        self._ah.cleanup_deps(['sox', 'audioloop'])

    def check_eth_state(self):
        path = '/sys/class/net/%s/carrier' % self._eth
        output = None
        try:
            if os.path.exists(path):
                output = open(path).read()
        finally:
            if output:
                return output == '1\n'
            else:
                return False

    def test_command(self, event):
        logging.info('Get event %s', event)
        cmd = event.data.get('cmd', '')
        for key in self._handlers.iterkeys():
            if key.match(cmd):
                self._handlers[key]()
                break

    def reset_test_phase(self, event):
        self._test_phase = 0 if self._use_shopfloor else 2
        self.detect_network(None)

    def detect_network(self, event):
        self._eth = net_utils.FindUsableEthDevice()
        if self._test_phase == 0 or self._test_phase == 2:
            if self._eth:
                self.ui.CallJSFunction('setMessage', _LABEL_WAITING_IP)
                logging.info('Got %s for connection', self._eth)
                if self._test_phase == 0: #connect shopfloor
                    try:
                        net_utils.SendDhcpRequest()
                    except:
                        logging.info('DHCP Timeout')
                        self.ui.CallJSFunction('start_countdown',
                                _LABEL_PHASE_LIST[self._test_phase],
                                self._countdown)
                    else:
                        self.init_audio_parameter()
                elif self._test_phase == 2: #connect fixture
                    net_utils.SetEthernetIp(_LOCAL_IP, force=True)
                    self.init_audio_server()
            else:
                self.ui.CallJSFunction('start_countdown',
                        _LABEL_PHASE_LIST[self._test_phase], self._countdown)
        elif self._test_phase == 1:
            if not self._eth:
                self._test_phase += 1
            self.ui.CallJSFunction('start_countdown',
                    _LABEL_PHASE_LIST[self._test_phase], self._countdown)

    def get_shopfloor_connection(
            self, timeout_secs=SHOPFLOOR_TIMEOUT_SECS,
            retry_interval_secs=SHOPFLOOR_RETRY_INTERVAL_SECS):
        """
        Returns a shopfloor client object.

        Try forever until a connection of shopfloor is established.

        Args:
          timeout_secs: Timeout for shopfloor connection.
          retry_interval_secs: Seconds to wait between retries.
        """
        logging.info('Connecting to shopfloor...')
        while True:
            try:
                shopfloor_client = shopfloor.get_instance(
                    detect=True, timeout=timeout_secs)
                break
            except:  # pylint: disable=W0702
                logging.info('Unable to sync with shopfloor server')
            time.sleep(retry_interval_secs)
        return shopfloor_client

    def init_audio_parameter(self):
        """Downloads parameters from shopfloor and saved to state/caches."""
        logging.info('Start downloading parameters...')
        self.ui.CallJSFunction('setMessage', _LABEL_CONNECT_SHOPFLOOR)
        shopfloor_client = self.get_shopfloor_connection()
        logging.info('Syncing time with shopfloor...')
        goofy = factory.get_state_instance()
        goofy.SyncTimeWithShopfloorServer()

        self.ui.CallJSFunction('setMessage', _LABEL_DOWNLOADING_PARAMETERS)
        download_list = []
        for glob_expression in self._parameters:
            logging.info('Listing %s', glob_expression)
            download_list.extend(
                    shopfloor_client.ListParameters(glob_expression))
        logging.info('Download list prepared:\n%s',
                '\n'.join(download_list))
        assert len(download_list) > 0, 'No parameters found on shopfloor'
        # Download the list and saved to caches in state directory.
        for filepath in download_list:
            utils.system('mkdir -p ' + os.path.join(
                    self._caches_dir, os.path.dirname(filepath)))
            binary_obj = shopfloor_client.GetParameter(filepath)
            with open(os.path.join(self._caches_dir, filepath), 'wb') as fd:
                fd.write(binary_obj.data)

        self._test_phase += 1
        logging.info('Removing Ethernet device...')
        self.ui.CallJSFunction('start_countdown',
                _LABEL_PHASE_LIST[self._test_phase], self._countdown)

    def run_once(self, input_dev='hw:0,0', output_dev='hw:0,0', eth='eth0',
            dmic_switch_mixer_settings=_DMIC_SWITCH_MIXER_SETTINGS,
            init_mixer_settings=_INIT_MIXER_SETTINGS,
            unmute_speaker_mixer_settings=_UNMUTE_SPEAKER_MIXER_SETTINGS,
            mute_right_mixer_settings=_MUTE_RIGHT_MIXER_SETTINGS,
            mute_left_mixer_settings=_MUTE_LEFT_MIXER_SETTINGS,
            use_sox_loop=False, use_multitone=False, loop_buffer_count=10,
            countdown=_INIT_COUNTDOWN, parameters=_FIXTURE_PARAMETERS,
            use_shopfloor=True):
        logging.info('%s run_once', self.__class__)

        self._ah = audio_helper.AudioHelper(self)
        self._ah.setup_deps(['sox', 'audioloop'])
        self._input_dev = input_dev
        self._output_dev = output_dev
        self._eth = None
        self._test_complete = False
        self._test_passed = False
        self._use_sox_loop = use_sox_loop
        self._use_multitone = use_multitone
        self._loop_buffer_count = loop_buffer_count

        self._multitone_job = None
        self._sweep_job = None
        self._tone_job = None
        self._loop_process = None
        self._countdown = countdown
        self._parameters = parameters
        self._caches_dir = os.path.join(CACHES_DIR, 'parameters', 'audio')
        self._use_shopfloor = use_shopfloor
        """
        _test_phase
        0: wait ethernet to shopfloor server
        1: wait removing ethernet
        2: wait ethernet to audio fixture
        3: ready for test
        """
        self._test_phase = 0 if self._use_shopfloor else 2
        self._init_socket = 0

        # Mixer settings for different configurations.
        self._init_mixer_settings = init_mixer_settings
        self._unmute_speaker_mixer_settings = unmute_speaker_mixer_settings
        self._mute_left_mixer_settings = mute_left_mixer_settings
        self._mute_right_mixer_settings = mute_right_mixer_settings
        self._dmic_switch_mixer_settings = dmic_switch_mixer_settings

        self.ui = test_ui.UI()

        # Register commands to corresponding handlers.
        self._handlers = {}
        self._handlers[_SEND_FILE_RE] = self.handle_send_file
        self._handlers[_RESULT_PASS_RE] = self.handle_result_pass
        self._handlers[_RESULT_FAIL_RE] = self.handle_result_fail
        self._handlers[_TEST_COMPLETE_RE] = self.handle_test_complete
        self._handlers[_LOOP_0_RE] = self.handle_loop_none
        self._handlers[_LOOP_1_RE] = self.handle_loop_from_dmic
        self._handlers[_LOOP_2_RE] = self.handle_loop_speaker_unmute
        self._handlers[_LOOP_3_RE] = self.handle_loop_jack
        self._handlers[_XTALK_L_RE] = self.handle_xtalk_left
        self._handlers[_XTALK_R_RE] = self.handle_xtalk_right
        self._handlers[_MULTITONE_RE] = self.handle_multitone
        self._handlers[_SWEEP_RE] = self.handle_sweep
        self._handlers[_VERSION_RE] = self.handle_version
        self._handlers[_CONFIG_FILE_RE] = self.handle_config_file

        self.ui.AddEventHandler('detect_network', self.detect_network)
        self.ui.AddEventHandler('reset_test_phase',
                                self.reset_test_phase)
        self.ui.AddEventHandler('test_command', self.test_command)
        utils.system('iptables -A INPUT -p tcp --dport %s -j ACCEPT' % _PORT)

        self.ui.Run()
