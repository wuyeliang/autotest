# Copyright (c) 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


from autotest_lib.client.common_lib import global_config
_CONFIG = global_config.global_config

# Names of the host attributes in the database that represent the values for
# the servo_host and servo_port for a servo connected to the DUT.
SERVO_HOST_ATTR = 'servo_host'
SERVO_PORT_ATTR = 'servo_port'
SERVO_BOARD_ATTR = 'servo_board'
# Model is inferred from host labels.
SERVO_MODEL_ATTR = 'servo_model'
SERVO_SERIAL_ATTR = 'servo_serial'
SERVO_ATTR_KEYS = (
        SERVO_BOARD_ATTR,
        SERVO_HOST_ATTR,
        SERVO_PORT_ATTR,
        SERVO_SERIAL_ATTR,
)

# Timeout value for stop/start servod process.
SERVOD_TEARDOWN_TIMEOUT = 3
SERVOD_QUICK_STARTUP_TIMEOUT = 20
SERVOD_STARTUP_TIMEOUT = 60

# pools that support dual v4. (go/cros-fw-lab-strategy)
POOLS_SUPPORT_DUAL_V4 = {'faft-cr50',
                         'faft-cr50-experimental',
                         'faft-cr50-tot',
                         'faft-cr50-debug',
                         'faft_cr50_debug'
                         'faft-pd-debug',
                         'faft_pd_debug'}

ENABLE_SSH_TUNNEL_FOR_SERVO = _CONFIG.get_config_value(
        'CROS', 'enable_ssh_tunnel_for_servo', type=bool, default=False)

SERVO_STATE_LABEL_PREFIX = 'servo_state'
SERVO_STATE_WORKING = 'WORKING'
SERVO_STATE_BROKEN = 'BROKEN'
SERVO_STATE_NOT_CONNECTED = 'NOT_CONNECTED'
SERVO_STATE_WRONG_CONFIG = 'WRONG_CONFIG'
SERVO_STATE_UNKNOWN = 'UNKNOWN'
