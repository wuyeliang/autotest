# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.import json

import json
import logging
import requests

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import constants as cros_constants
from autotest_lib.client.cros.multimedia import local_facade_factory
from autotest_lib.client.cros.video import helper_logger
from collections import namedtuple
from string import Template


class video_AVAnalysis(test.test):
    """This test plays a video on DUT so it can be recorded.

    The recording will be carried out by a recording server connected
    to this DUT via HDMI cable (hence dependency on cros_av_analysis label.
    The recording will then be uploaded to Google Cloud storage and analyzed
    for performance and quality metrics.
    """
    version = 1
    _CONFIG_TEMPLATE = Template("""project_id: $project_id
            project_name: "$project_name"
            reference_video_id: $vid_id
            reference_video_name: "$vid_name"
            test_video_location: "$filepath"
            triggered_by: "$triggered_by"
            run_information {{
                device: "$board"
                build: "$build"
                profile: "profile"
                extra_information {{
                    key: "extra_info_key"
                    value: "extra_info_value"
                }}
            }}
            extra_results {{
                name: "extra_result_name"
                value: 10.0
            }}
            job_settings {{
                freezing_smoothness: $check_smoothness
                psnr_ssim: $check_psnr
                av_sync: $check_sync
                audio: $check_audio
                color: $check_color
            }}""")
    dut_info = namedtuple('dut_info', 'ip, board, build')
    srv_info = namedtuple('srv_info', 'ip, port, path')
    rec_info = namedtuple('rec_info', ('vid_name, duration, project_id, '
                                       ' project_name, bucket_name'))
    tst_info = namedtuple('tst_info', ('check_smoothness, check_psnr, '
                                       'check_sync, check_audio, check_color, '
                                       'vid_id, vid_name'))

    def gather_config_info(self):
        """Gathers info relevant for AVAS config file creation.

        Method might seem weird, but it isolates values that at some
        point could be gathered from a config or setting file instead
        to provide more flexibility.
        """
        self.dut_info.board = utils.get_board()
        self.dut_info.build = utils.get_chromeos_version()

        self.rec_info.vid_name = '{0}_{1}_{2}.mp4'.format(
            self.dut_info.build, self.dut_info.board, 'vp9')
        self.rec_info.duration = '5'
        self.rec_info.project_id = '40'
        self.rec_info.project_name = 'cros-av'
        self.rec_info.bucket_name = 'cros-av-analysis'

        self.tst_info.check_smoothness = 'true'
        self.tst_info.check_psnr = 'true'
        self.tst_info.check_sync = 'false'
        self.tst_info.check_audio = 'false'
        self.tst_info.check_color = 'false'
        self.tst_info.vid_id = '417'
        self.tst_info.vid_name = 'cros_vp9_720_60'

    def gather_runtime_info(self):
        """Gathers pieces of info required for test execution"""
        self.dut_info.ip = utils.get_ip_address()
        self.srv_info.ip = self.get_server_ip(self.dut_info.ip)
        logging.debug('----------I-P------------')
        logging.debug(self.dut_info.ip)
        logging.debug(self.srv_info.ip)
        self.srv_info.port = '5000'
        self.srv_info.path = 'record_and_upload'

    def get_server_ip(self, dut_ip):
        """Returns recorder server IP address.

        This method uses DUT IP to calculate IP of recording server. Note that
        we rely on a protocol here, when the lab is setup, DUTs and recorders
        are assigned IPs in pairs and the server is always one lower. As in,
        in a V4 address, the last integer segment is less than DUTs last int
        segment by 1.

        @param dut_ip: IP address of DUT.
        """
        segments = dut_ip.split('.')
        if len(segments) != 4:
            raise Exception('IP address of DUT did not have 4 segments')
        last_segment = int(segments[3])
        if last_segment > 255 or last_segment < 1:
            raise Exception('Value of last IP segment of DUT is invalid')

        last_segment = last_segment - 1
        segments[3] = str(last_segment)
        server_ip = '.'.join(segments)
        return server_ip

    def start_recording(self):
        """Starts recording on recording server.

        Makes an http POST request to the recording server to start
        recording and processes the response. The body of the post
        contains config file data.
        """
        destination = 'http://{0}:{1}/{2}'.format(self.srv_info.ip,
                                                  self.srv_info.port,
                                                  self.srv_info.path)
        query_params = {'filename': self.rec_info.vid_name,
                        'duration': self.rec_info.duration}
        config_text = self.get_config_string()
        response = requests.post(destination, params=query_params,
                                 data=config_text, timeout=60)
        status_code = json.loads(response)

        if status_code != 0:
            raise error.TestFail('Recording server failed with status code: ' +
                                 str(status_code))

    def get_config_string(self):
        """Write up config text so that AVAS can correctly process video."""
        path_prefix = '/bigstore/cros-av-analysis/{0}'
        filepath = path_prefix.format(self.rec_info.vid_name)
        config_dict = {'filepath': filepath, 'triggered_by': 'vsuley'}
        config_dict.update(vars(self.rec_info))
        config_dict.update(vars(self.dut_info))
        config_dict.update(vars(self.tst_info))
        config = self._CONFIG_TEMPLATE.substitute(config_dict)
        return config

    def run_once(self, video, arc_mode=False):
        """Plays video on DUT for recording & analysis."""
        self.gather_config_info()
        self.gather_runtime_info()
        with chrome.Chrome(
                extra_browser_args=helper_logger.chrome_vmodule_flag(),
                extension_paths=[cros_constants.DISPLAY_TEST_EXTENSION],
                autotest_ext=True,
                arc_mode="disabled",
                init_network_controller=True) as cr:
            factory = local_facade_factory.LocalFacadeFactory(cr)
            display_facade = factory.create_display_facade()
            logging.debug('Setting mirrorred to True')
            display_facade.set_mirrored(True)
            display_facade.set_fullscreen(True)
            tab1 = cr.browser.tabs.New()
            tab1.Navigate(video)
            tab1.WaitForDocumentReadyStateToBeComplete()
            self.start_recording()
