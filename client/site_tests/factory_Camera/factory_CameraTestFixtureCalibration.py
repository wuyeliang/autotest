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
import json
import math
import numpy as np
import os
import time

import autotest_lib.client.cros.camera.perf_tester as camperf
import autotest_lib.client.cros.camera.renderer as renderer

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
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

_DEVICE_INDEX = -1

_PREFERRED_FPS = 15
_PREFERRED_INTERVAL = int(round(1000.0 / _PREFERRED_FPS))
_FPS_UPDATE_FACTOR = 0.1

_MESSAGE_STR = ('Fixture calibration under progress.<br>' +
                'Please move the test chart until it reports SUCCESS. ' +
                'Press any key to leave.<br>')

_TEST_CONFIG = {
    'register_grid': False,
    'min_corner_quality_ratio': 0.05,
    'min_square_size_ratio': 0.022,
    'min_corner_distance_ratio': 0.010,
    'max_image_shift': 0.001,
    'max_image_tilt': 0.15
    }


class factory_Camera(test.test):
    version = 1
    preserve_srcdir = True

    _DEVICE_INDEX = -1
    _TEST_CHART_FILE = 'test_chart.png'
    _TEST_SAMPLE_FILE = 'sample.png'

    _PACKET_SIZE = 65000

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
        renderer.DrawVC(img, success, tar_data)

        # Encode the image in the JPEG format.
        img = cv2.resize(img, None, fx=0.5, fy=0.5,
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
                 unit_test=False):
        factory.log('%s run_once' % self.__class__)

        self.show_fps = show_fps
        self.unit_test = unit_test

        # Prepare test data.
        os.chdir(self.srcdir)
        self.ref_data = camperf.PrepareTest(self._TEST_CHART_FILE)
        self.config = _TEST_CONFIG
        if self.unit_test:
            self.sample = cv2.imread(self._TEST_SAMPLE_FILE)

        # Initialize the camera with OpenCV.
        self.dev = dev = cv2.VideoCapture(_DEVICE_INDEX)
        if not dev.isOpened():
            raise IOError('Device #%s ' % _DEVICE_INDEX +
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
