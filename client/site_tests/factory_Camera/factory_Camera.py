# -*- coding: utf-8 -*-
#
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

try:
    import cv
    import cv2
except ImportError:
    pass

import base64
import logging
import os
import signal
import time

import autotest_lib.client.cros.camera.perf_tester as camperf
import autotest_lib.client.cros.camera.renderer as renderer

from autotest_lib.client.bin import test
from autotest_lib.client.cros import factory_setup_modules
from cros.factory.test import factory
from cros.factory.test.test_ui import UI

_HTML = r'''
<div id="Title"
style="
    text-align: center;
    font-weight: bold;
    font-size: 150%
">
Camera Test Fixture Calibration
</div>
<div id="test_message"
style="text-align: center; font-weight: normal">
</div>
<div id="test_status"
style="
    text-align: center;
    font-weight: bold;
    font-size: 150%
">
</div>
<div id="camera_image_wrapper"
style="text-align: center">
<img id="camera_image"></img>
</div>
'''

_JS = r'''
window.onload = RegisterCameraCallback();

function RegisterCameraCallback() {
    setTimeout("test.sendTestEvent('poll', {});", 60);
}

function ClearBuffer() {
    buf = ""
}

function AddBuffer(value) {
    buf += value
}

function UpdateView(msg, success) {
    var cam = document.getElementById("camera_image");
    cam.src = "data:image/jpeg;base64," + buf;
    var test_message = document.getElementById("test_message");
    test_message.innerHTML = msg;
    var test_status = document.getElementById("test_status");
    if (success) {
        test_status.style.color = "green";
        test_status.innerHTML = "SUCCESS";
    } else {
        test_status.style.color = "red";
        test_status.innerHTML = "FAIL";
    }

    setTimeout("test.sendTestEvent('poll', {});", 30)
}
'''

_PREFERRED_FPS = 15
_PREFERRED_INTERVAL = int(round(1000.0 / _PREFERRED_FPS))
_FPS_UPDATE_FACTOR = 0.1

_MESSAGE_STR = ('Fixture calibration under progress.<br>' +
                'Please adjust the fixture until it reports SUCCESS, ' +
                'then exit the test manually.')

_TEST_CONFIG = {
    'register_grid': False,
    'min_corner_quality_ratio': 0.05,
    'min_square_size_ratio': 0.022,
    'min_corner_distance_ratio': 0.010,
    'max_image_shift': 0.003,
    'max_image_tilt': 0.25
    }


class factory_Camera(test.test):
    version = 1
    preserve_srcdir = True

    _PACKET_SIZE = 65000

    def get_test_chart_file(self):
        return 'test_chart_%s.png' % self.test_chart_version

    def get_test_sample_file(self):
        return 'sample_%s.png' % self.test_chart_version

    def register_events(self, events):
        for event in events:
            assert hasattr(self, event)
            factory.console.info('Register event %s' % event)
            self.ui.AddEventHandler(event, getattr(self, event))

    def update_view(self, data, msg, success):
        '''Call javascripts to update the screen.'''
        self.ui.CallJSFunction("ClearBuffer", "")
        # Send the data in 64K packets due to the socket packet size limit.
        data_len = len(data)
        p = 0
        while p < data_len:
            if p + self._PACKET_SIZE > data_len:
                self.ui.CallJSFunction("AddBuffer", data[p:data_len-1])
                p = data_len
            else:
                self.ui.CallJSFunction("AddBuffer",
                                         data[p:p+self._PACKET_SIZE])
                p += self._PACKET_SIZE
        self.ui.CallJSFunction("UpdateView", msg, success)

    def poll(self, event):
        '''Captures an image and displays it.'''
        msg = _MESSAGE_STR
        # Read image from camera.
        ret, img = self.dev.read()
        if not ret:
            raise IOError("Error while capturing. Camera disconnected?")
        if self.unit_test:
            img = self.sample.copy()

        # Analysize the image and draw overlays.
        target = cv2.cvtColor(img, cv.CV_BGR2GRAY)
        success, tar_data = camperf.CheckVisualCorrectness(
            target, self.ref_data, corner_only=True, **self.config)

        if hasattr(tar_data, 'shift'):
            factory.log("Image shift: %0.3f (%.02f, %0.02f)" %
                        (tar_data.shift, tar_data.v_shift[0],
                         tar_data.v_shift[1]))
        if hasattr(tar_data, 'tilt'):
            factory.log("Image tilt: %0.2f" % tar_data.tilt)
        factory.log('FPS = ' + ('%.2f\n' % self.current_fps))

        renderer.DrawVC(img, success, tar_data)

        # Encode the image in the JPEG format.
        # TODO: add an option of resizing or not
        img = cv2.resize(img, None, fx=self.resize_ratio, fy=self.resize_ratio,
                         interpolation=cv2.INTER_AREA)
        cv2.imwrite('temp.jpg', img)
        with open('temp.jpg', 'r') as fd:
            img_data = base64.b64encode(fd.read()) + "="
        #img_data = base64.b64encode(cv.EncodeImage('.jpg', img).tostring()) + \
        #           "="

        # Update FPS if required.
        if self.show_fps:
            current_time = time.clock()
            self.current_fps = (self.current_fps * (1 - _FPS_UPDATE_FACTOR) +
                                1.0 / (current_time - self.last_capture_time) *
                                _FPS_UPDATE_FACTOR)
            self.last_capture_time = current_time
            msg += 'FPS = ' + '%.2f\n' % self.current_fps

        # Update the HTML with javascript.
        self.update_view(img_data, msg, success)
        return

    def run_once(self, res_width=1280, res_height=720, show_fps=True,
                 test_chart_version = 'A',
                 resize_ratio=1.0, device_index=-1, unit_test=False):
        factory.log('%s run_once' % self.__class__)

        # Set default signal handlers.
        signal_handler = lambda signum, frame: sys.exit(0)
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        # Set logging level. Otherwise, send preview data to AddBuffer() will
        # log the whole image preview data to factory log under the default log
        # level of autotest.
        logging.getLogger().setLevel(logging.INFO)

        self.show_fps = show_fps
        self.test_chart_version = test_chart_version
        self.unit_test = unit_test
        self.resize_ratio = resize_ratio

        # Prepare test data.
        os.chdir(self.srcdir)
        self.ref_data = camperf.PrepareTest(self.get_test_chart_file())
        self.config = _TEST_CONFIG
        if self.unit_test:
            self.sample = cv2.imread(self.get_test_sample_file())

        self.dev = dev = cv2.VideoCapture(device_index)
        if not dev.isOpened():
            raise IOError('Device #%s ' % device_index +
                          'does not support video capture interface')
        dev.set(cv.CV_CAP_PROP_FRAME_WIDTH, res_width)
        dev.set(cv.CV_CAP_PROP_FRAME_HEIGHT, res_height)

        if self.show_fps:
            self.last_capture_time = time.clock()
            self.current_fps = _PREFERRED_FPS

        self.ui = UI()
        self.ui.SetHTML(_HTML)
        self.ui.RunJS(_JS)
        self.register_events(['poll'])
        self.ui.Run()

        factory.log('%s run_once finished' % self.__class__)
