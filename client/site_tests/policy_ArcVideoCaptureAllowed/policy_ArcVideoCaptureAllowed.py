# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils

from autotest_lib.client.common_lib.cros import arc
from autotest_lib.client.cros.enterprise import enterprise_policy_base


class policy_ArcVideoCaptureAllowed(
        enterprise_policy_base.EnterprisePolicyTest):
    """
    Test effect of the ArcVideoCaptureAllowed ChromeOS policy on ARC.

    This test will launch the ARC container via the ArcEnabled policy, then
    will check the behavior of the passthrough policy VideoCaptureAllowed.

    When the policy is set to False, Video Capture is not allowed. To test
    this, we will attemp to launch the ARC Camera, and check the logs to see
    if the Camera was launched or not.

    """
    version = 1

    def _launch_Arc_Cam(self):
        """Grant the Camera location permission, and launch the Camera app."""
        utils.poll_for_condition(
            lambda: self.did_cam_app_respond(),
            exception=error.TestFail('Camera APP did not respond.'),
            timeout=25,
            sleep_interval=5,
            desc='Wait for Camera to respond.')

    def _cam_closed(self):
        """Check if the camera got closed after it opened."""
        return arc.adb_shell("logcat -d | grep camera | grep Closing",
                             ignore_status=True)

    def _check_cam_status(self):
        """Returns the specified section from loggcat."""
        cam_device = arc.adb_shell("logcat -d | grep 'Camera device'",
                                   ignore_status=True)
        cam_disable = arc.adb_shell("logcat -d | grep 'disabled by policy'",
                                    ignore_status=True)
        return [cam_device, cam_disable]

    def did_cam_app_respond(self):
        """
        Check if the Camera app has responded to the start command via
        data in the logs being populated.

        @return: True/False, if the Camera has responded to the start command.

        """
        arc.adb_shell('pm grant com.google.android.GoogleCameraArc android.permission.ACCESS_COARSE_LOCATION')
        arc.adb_shell('am start -a android.media.action.IMAGE_CAPTURE')
        cam_logs = self._check_cam_status()
        if cam_logs[0] or cam_logs[1]:
            return True
        return False

    def _test_Arc_cam_status(self, case):
        """
        Test if the Arc Camera has been opened, or not.

        @param case: bool, value of the VideoCaptureAllowed policy.

        """
        #  Once the Camera is open, get the status from logcat.
        cam_device_resp, disabled_resp = self._check_cam_status()

        if case or case is None:
            if 'opened successfully' not in cam_device_resp or disabled_resp:
                raise error.TestFail(
                    'Camera did not launch when it should have.')
        else:
            if ('opened successfully' in cam_device_resp or
                'disabled by policy' not in disabled_resp):
                # Sometimes due to timing the camera will still open, but then
                # will quickly be closed. Check for this.
                utils.poll_for_condition(
                    lambda: self._cam_closed(),
                    exception=error.TestFail(
                        'Camera APP did not close or unstable.'),
                    timeout=15,
                    sleep_interval=3,
                    desc='Wait for Camera to close.')

    def run_once(self, case):
        """
        Setup and run the test configured for the specified test case.

        @param case: Name of the test case to run.

        """
        pol = {'ArcEnabled': True,
               'VideoCaptureAllowed': case}

        self.setup_case(user_policies=pol,
                        arc_mode='enabled',
                        use_clouddpc_test=False)

        # Allow the ARC container time to apply the policy...
        time.sleep(15)

        self._launch_Arc_Cam()
        self._test_Arc_cam_status(case)
