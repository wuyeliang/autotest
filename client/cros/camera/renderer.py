# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Import guard for OpenCV.
try:
    import cv
    import cv2
except ImportError:
    pass

import math
import numpy as np

# Color constants.
_COLORS = {
    'important': (0, 0, 255),
    'corner': (0, 255, 255),
    'success': (0, 255, 0),
    'deviation': (255, 0, 255),
    }


def _DrawLineByAngle(img, origin, length, angle, color,
                     thickness):
    '''Draw a line by specifying the origin, length and angle.'''
    dx1 = length * math.cos(angle)
    dy1 = length * math.sin(angle)
    cv2.line(img, origin, (origin[0] + dx1, origin[1] + dy1), color,
             thickness)


def _DrawArrowTip(img, tip, direction, tip_length, tip_angle, color,
                  thickness):
    '''Draw an arrow tip.'''
    theta1 = math.radians(direction + 180 + tip_angle)
    _DrawLineByAngle(img, tip, tip_length, theta1, color, thickness)
    theta2 = math.radians(direction + 180 - tip_angle)
    _DrawLineByAngle(img, tip, tip_length, theta2, color, thickness)


def _DrawArcWithArrow(img, center, radius, start_angle, delta_angle,
                        tip_length, tip_angle, color, thickness):
    '''Draw an arc with an arrow tip on one end.'''
    # Draw arc.
    cv2.ellipse(img, center, (radius, radius), start_angle,
                (0 if delta_angle > 0 else -delta_angle),
                (-delta_angle if delta_angle > 0 else 0), color, thickness)

    # Draw arrow tip.
    # The minus sign is because the y axis is reversed for the actual image.
    tip_point_angle = -(start_angle + delta_angle)
    tip = (center[0] + radius * math.cos(math.radians(tip_point_angle)),
           center[1] + radius * math.sin(math.radians(tip_point_angle)))
    _DrawArrowTip(img, tip,
                  tip_point_angle - (90 if delta_angle > 0 else -90),
                  tip_length, tip_angle, color, thickness)


def DrawVC(img, success, result):
    '''Draw the result of the visual correctness test on the test image.'''
    if hasattr(result, 'sample_corners'):
        # Draw all corners.
        for point in result.sample_corners:
            cv2.circle(img, (point[0], point[1]), 2, _COLORS['corner'],
                       thickness=-1)

        if hasattr(result, 'shift'):
            # Draw the four corners of the corner grid.
            for point in result.four_corners:
                cv2.circle(img, (point[0], point[1]), 4,
                           _COLORS[('success' if success else 'important')],
                           thickness = -1)

            # Draw the center and the shift vector.
            center = ((img.shape[1] - 1) / 2.0, (img.shape[0] - 1) / 2.0)
            tip = np.array(center) + result.v_shift
            cv2.line(img, center, (tip[0], tip[1]),
                     _COLORS['deviation'], thickness=2)
            diag_len = math.sqrt(img.shape[0] ** 2 + img.shape[1] ** 2)
            angle = math.atan2(result.v_shift[1], result.v_shift[0])
            _DrawArrowTip(img, (tip[0], tip[1]), math.degrees(angle),
                          result.shift * diag_len * 0.3, 60,
                          _COLORS['deviation'], thickness=2)
            cv2.circle(img, center, 4,
                       _COLORS[('success' if success else 'important')],
                       thickness=-1)

            # Draw the rotation indicator.
            radius = max(img.shape) / 4
            # Boost the amount so it is more easily visible.
            angle = max(-90, min(90, result.tilt * 10))
            tip_length = abs(math.radians(angle)) * radius * 0.3
            tip_angle = 60
            _DrawArcWithArrow(img, center, radius, 0, angle,
                              tip_length, tip_angle,
                              _COLORS['deviation'], thickness=2)
            _DrawArcWithArrow(img, center, radius, 180, angle,
                              tip_length, tip_angle,
                              _COLORS['deviation'], thickness=2)
