# Copyright (c) 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Attenuator hostnames with fixed loss overhead on a given antenna line. """

# This map represents the fixed loss overhead on a given antenna line.
# The map maps from:
#     attenuator hostname -> attenuator number -> frequency -> loss in dB.
HOST_FIXED_ATTENUATIONS = {
        'chromeos1-dev-host4-attenuator': {
                0: {2437: 53, 5220: 59, 5765: 59},
                1: {2437: 56, 5220: 56, 5765: 56},
                2: {2437: 53, 5220: 59, 5765: 59},
                3: {2437: 57, 5220: 56, 5765: 56}},
        'chromeos1-test-host2-attenuator': {
                0: {2437: 53, 5220: 59, 5765: 58},
                1: {2437: 57, 5220: 57, 5765: 59},
                2: {2437: 53, 5220: 59, 5765: 58},
                3: {2437: 57, 5220: 57, 5765: 59}},
        'chromeos15-row3-rack11-host1-attenuator': {
                0: {2437: 53, 5220: 58, 5765: 57},
                1: {2437: 56, 5220: 56, 5765: 58},
                2: {2437: 53, 5220: 58, 5765: 57},
                3: {2437: 56, 5220: 56, 5765: 57}},
        'chromeos15-row3-rack11-host2-attenuator': {
                0: {2437: 53, 5220: 58, 5765: 56},
                1: {2437: 56, 5220: 56, 5765: 58},
                2: {2437: 53, 5220: 59, 5765: 56},
                3: {2437: 56, 5220: 56, 5765: 56}},
        'chromeos15-row3-rack11-host3-attenuator': {
                0: {2437: 52, 5220: 57, 5765: 59},
                1: {2437: 55, 5220: 55, 5765: 54},
                2: {2437: 52, 5220: 57, 5765: 59},
                3: {2437: 55, 5220: 55, 5765: 54}},
        'chromeos15-row3-rack11-host4-attenuator': {
                0: {2437: 52, 5220: 58, 5765: 59},
                1: {2437: 56, 5220: 56, 5765: 55},
                2: {2437: 52, 5220: 57, 5765: 59},
                3: {2437: 56, 5220: 56, 5765: 55}},
        'chromeos15-row3-rack11-host5-attenuator': {
                0: {2437: 53, 5220: 58, 5765: 58},
                1: {2437: 55, 5220: 56, 5765: 55},
                2: {2437: 53, 5220: 58, 5765: 59},
                3: {2437: 56, 5220: 55, 5765: 55}},
        'chromeos15-row3-rack11-host6-attenuator': {
                0: {2437: 52, 5220: 58, 5765: 59},
                1: {2437: 55, 5220: 55, 5765: 54},
                2: {2437: 52, 5220: 57, 5765: 59},
                3: {2437: 55, 5220: 55, 5765: 54}},
        'chromeos15-row3-rack12-host1-attenuator': {
                0: {2437: 53, 5220: 59, 5765: 58},
                1: {2437: 55, 5220: 57, 5765: 55},
                2: {2437: 57, 5220: 59, 5765: 58},
                3: {2437: 55, 5220: 56, 5765: 55}},
        'chromeos15-row3-rack12-host2-attenuator': {
                0: {2437: 52, 5220: 59, 5765: 56},
                1: {2437: 55, 5220: 56, 5765: 55},
                2: {2437: 52, 5220: 59, 5765: 57},
                3: {2437: 55, 5220: 56, 5765: 55}},
        'chromeos15-row3-rack12-host3-attenuator': {
                0: {2437: 52, 5220: 58, 5765: 57},
                1: {2437: 55, 5220: 57, 5765: 55},
                2: {2437: 52, 5220: 59, 5765: 59},
                3: {2437: 55, 5220: 59, 5765: 55}},
        'chromeos15-row3-rack12-host4-attenuator': {
                0: {2437: 52, 5220: 58, 5765: 56},
                1: {2437: 55, 5220: 56, 5765: 55},
                2: {2437: 52, 5220: 58, 5765: 56},
                3: {2437: 55, 5220: 56, 5765: 56}},
        'chromeos15-row3-rack12-host5-attenuator': {
                0: {2437: 53, 5220: 59, 5765: 58},
                1: {2437: 55, 5220: 56, 5765: 55},
                2: {2437: 52, 5220: 59, 5765: 59},
                3: {2437: 55, 5220: 56, 5765: 55}},
        'chromeos15-row3-rack12-host6-attenuator': {
                0: {2437: 52, 5220: 59, 5765: 57},
                1: {2437: 55, 5220: 56, 5765: 55},
                2: {2437: 52, 5220: 58, 5765: 56},
                3: {2437: 55, 5220: 56, 5765: 55}},
        'chromeos15-row3-rack13-host1-attenuator': {
                0: {2437: 59, 5220: 59, 5765: 59},
                1: {2437: 52, 5220: 54, 5765: 54},
                2: {2437: 59, 5220: 59, 5765: 59},
                3: {2437: 52, 5220: 54, 5765: 54}},
        'chromeos15-row3-rack13-host2-attenuator': {
                0: {2437: 64, 5220: 62, 5765: 62},
                1: {2437: 58, 5220: 57, 5765: 57},
                2: {2437: 64, 5220: 62, 5765: 62},
                3: {2437: 58, 5220: 57, 5765: 57}},
        'chromeos15-row3-rack13-host3-attenuator': {
                0: {2437: 60, 5220: 58, 5765: 58},
                1: {2437: 52, 5220: 57, 5765: 57},
                2: {2437: 60, 5220: 58, 5765: 58},
                3: {2437: 52, 5220: 57, 5765: 57}},
        'chromeos15-row3-rack13-host4-attenuator': {
                0: {2437: 52, 5220: 58, 5765: 58},
                1: {2437: 59, 5220: 60, 5765: 60},
                2: {2437: 52, 5220: 58, 5765: 58},
                3: {2437: 59, 5220: 60, 5765: 60}},
        'chromeos15-row3-rack13-host5-attenuator': {
                0: {2437: 58, 5220: 60, 5765: 60},
                1: {2437: 53, 5220: 58, 5765: 58},
                2: {2437: 58, 5220: 60, 5765: 60},
                3: {2437: 53, 5220: 58, 5765: 58}},
        'chromeos15-row3-rack13-host6-attenuator': {
                0: {2437: 52, 5220: 56, 5765: 58},
                1: {2437: 53, 5220: 56, 5765: 57},
                2: {2437: 52, 5220: 56, 5765: 58},
                3: {2437: 53, 5220: 56, 5765: 57}},
        'chromeos15-row3-rack14-host1-attenuator': {
                0: {2437: 53, 5220: 56, 5765: 56},
                1: {2437: 52, 5220: 56, 5765: 56},
                2: {2437: 53, 5220: 56, 5765: 56},
                3: {2437: 52, 5220: 56, 5765: 56}},
        'chromeos15-row3-rack14-host2-attenuator': {
                0: {2437: 59, 5220: 59, 5765: 59},
                1: {2437: 59, 5220: 60, 5765: 60},
                2: {2437: 59, 5220: 59, 5765: 59},
                3: {2437: 59, 5220: 60, 5765: 60}},
        'chromeos15-row3-rack14-host3-attenuator': {
                0: {2437: 52, 5220: 56, 5765: 56},
                1: {2437: 64, 5220: 63, 5765: 63},
                2: {2437: 52, 5220: 56, 5765: 56},
                3: {2437: 64, 5220: 63, 5765: 63}},
        'chromeos15-row3-rack14-host4-attenuator': {
                0: {2437: 52, 5220: 55, 5765: 55},
                1: {2437: 58, 5220: 58, 5765: 58},
                2: {2437: 52, 5220: 55, 5765: 55},
                3: {2437: 58, 5220: 58, 5765: 58}},
        'chromeos15-row3-rack14-host5-attenuator': {
                0: {2437: 57, 5220: 58, 5765: 58},
                1: {2437: 52, 5220: 55, 5765: 55},
                2: {2437: 57, 5220: 58, 5765: 58},
                3: {2437: 52, 5220: 55, 5765: 55}},
        'chromeos15-row3-rack14-host6-attenuator': {
                0: {2437: 57, 5220: 57, 5765: 57},
                1: {2437: 52, 5220: 55, 5765: 55},
                2: {2437: 57, 5220: 57, 5765: 57},
                3: {2437: 52, 5220: 55, 5765: 55}},
}
