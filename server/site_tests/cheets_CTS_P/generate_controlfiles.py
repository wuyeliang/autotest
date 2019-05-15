#!/usr/bin/env python
# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import collections
import contextlib
import logging
import os
import re
import shutil
import stat
import subprocess
import tempfile
import textwrap
import zipfile
# Use 'sudo pip install jinja2' to install.
from jinja2 import Template

# TODO(ihf): Assign better TIME to control files. Scheduling uses this to run
# LENGTHY first, then LONG, MEDIUM etc. But we need LENGTHY for the collect
# job, downgrade all others. Make sure this still works in CQ/smoke suite.
_CONTROLFILE_TEMPLATE = Template(
    textwrap.dedent("""\
    # Copyright 2018 The Chromium OS Authors. All rights reserved.
    # Use of this source code is governed by a BSD-style license that can be
    # found in the LICENSE file.

    # This file has been automatically generated. Do not edit!

    AUTHOR = 'ARC++ Team'
    NAME = '{{name}}'
    ATTRIBUTES = '{{attributes}}'
    DEPENDENCIES = '{{dependencies}}'
    JOB_RETRIES = {{job_retries}}
    TEST_TYPE = 'server'
    TIME = '{{test_length}}'
    MAX_RESULT_SIZE_KB = {{max_result_size_kb}}
    {%- if sync_count and sync_count > 1 %}
    SYNC_COUNT = {{sync_count}}
    {%- endif %}
    {%- if priority %}
    PRIORITY = {{priority}}
    {%- endif %}
    DOC = '{{DOC}}'
    {% if sync_count and sync_count > 1 %}
    from autotest_lib.server import utils as server_utils
    def run_CTS(ntuples):
        host_list = [hosts.create_host(machine) for machine in ntuples]
    {% else %}
    def run_CTS(machine):
        host_list = [hosts.create_host(machine)]
    {%- endif %}
        job.run_test(
            'cheets_CTS_P',
    {%- if camera_facing %}
            camera_facing='{{camera_facing}}',
            cmdline_args=args,
    {%- endif %}
            hosts=host_list,
            iterations=1,
    {%- if max_retries != None %}
            max_retry={{max_retries}},
    {%- endif %}
            needs_push_media={{needs_push_media}},
            tag='{{tag}}',
            test_name='{{name}}',
            run_template={{run_template}},
            retry_template={{retry_template}},
            target_module={% if target_module %}'{{target_module}}'{% else %}None{%endif%},
            target_plan={% if target_plan %}'{{target_plan}}'{% else %}None{% endif %},
            bundle='{{abi}}',
    {%- if uri %}
            uri='{{uri}}',
    {%- endif %}
    {%- for arg in extra_args %}
            {{arg}},
    {%- endfor %}
            timeout={{timeout}})

    {% if sync_count and sync_count > 1 -%}
    ntuples, failures = server_utils.form_ntuples_from_machines(machines,
                                                                SYNC_COUNT)
    # Use log=False in parallel_simple to avoid an exception in setting up
    # the incremental parser when SYNC_COUNT > 1.
    parallel_simple(run_CTS, ntuples, log=False)
    {% else -%}
    parallel_simple(run_CTS, machines)
    {% endif %}
"""))

_ALL = 'all'
# The dashboard suppresses upload to APFE for GS directories (based on autotest
# tag) that contain 'tradefed-run-collect-tests'. b/119640440
# Do not change the name/tag without adjusting the dashboard.
_COLLECT = 'tradefed-run-collect-tests-only-internal'
_PUBLIC_COLLECT = 'tradefed-run-collect-tests-only'
_CTS_QUAL_RETRIES = 9
_CTS_MAX_RETRIES = {
    # TODO(ihf): Remove all once Nocturne stable.
    'CtsAccessibilityServiceTestCases':  12,
    'CtsActivityManagerDeviceTestCases': 12,
    'CtsDeqpTestCases':   _CTS_QUAL_RETRIES,
    'CtsGraphicsTestCases':              12,
    'CtsIncidentHostTestCases':          12,
    'CtsSensorTestCases':                30,  # TODO(ihf): Lower this once flakes are fixed.
}

# TODO(ihf): Update timeouts once P is more stable.
# Timeout in hours.
_CTS_TIMEOUT = {
    'CtsAccessibilityServiceTestCases':  3.0,  # TODO(ihf): Remove once Nocturne stable.
    'CtsActivityManagerDeviceTestCases': 3.0,
    'CtsAppSecurityHostTestCases':       1.5,
    'CtsDeqpTestCases':                 30.0,
    'CtsDeqpTestCases.dEQP-EGL'  :       2.0,
    'CtsDeqpTestCases.dEQP-GLES2':       2.0,
    'CtsDeqpTestCases.dEQP-GLES3':       6.0,
    'CtsDeqpTestCases.dEQP-GLES31':      6.0,
    'CtsDeqpTestCases.dEQP-VK':         15.0,
    'CtsDevicePolicyManagerTestCases':   2.0,
    'CtsFileSystemTestCases':            2.5,
    'CtsHardwareTestCases':              3.0,
    'CtsIcuTestCases':                   2.0,
    'CtsLibcoreOjTestCases':             1.5,
    'CtsLibcoreTestCases':               1.5,
    # Media might be reduced to 12h?
    'CtsMediaBitstreamsTestCases':      16.0,
    'CtsMediaStressTestCases':          16.0,
    'CtsMediaTestCases':                16.0,
    'CtsPrintTestCases':                 3.0,
    'CtsSecurityHostTestCases':          1.5,
    'CtsSecurityTestCases':              2.0,
    'CtsSensorTestCases':                3.0,  # TODO(ihf): Remove once Nocturne stable.
    'CtsShortcutHostTestCases':          1.5,
    'CtsThemeHostTestCases':             6.0,
    'CtsWidgetTestCases':                2.0,
    'vm-tests-tf':                       2.0,
    # Without media kevin runs 40h. :-(
    # Never seen this finish on grunt.
    _ALL:                               60.0,
    _COLLECT:                            2.0,
    _PUBLIC_COLLECT:                     2.0,
}

# Any test that runs as part as blocking BVT needs to be stable and fast. For
# this reason we enforce a tight timeout on these modules/jobs.
# Timeout in hours. (0.1h = 6 minutes)
_BVT_TIMEOUT = 0.1
# We allow a very long runtime for qualification (2 days).
_QUAL_TIMEOUT = 48

_QUAL_BOOKMARKS = sorted([
    'A',  # A bookend to simplify partition algorithm.
    'CtsAccessibilityServiceTestCases',  # TODO(ihf) remove when b/121291711 fixed. This module causes problems. Put it into its own control file.
    'CtsAccessibilityServiceTestCasesz',
    'CtsActivityManagerDevice',  # Runs long enough. (3h)
    'CtsActivityManagerDevicez',
    'CtsDeqpTestCases',
    'CtsDeqpTestCasesz',  # Put Deqp in one control file. Long enough, fairly stable.
    'CtsFileSystemTestCases',  # Runs long enough. (3h)
    'CtsFileSystemTestCasesz',
    'CtsMediaBitstreamsTestCases',  # Put each Media module in its own control file. Long enough.
    'CtsMediaHostTestCases',
    'CtsMediaStressTestCases',
    'CtsMediaTestCases',
    'CtsMediaTestCasesz',
    'CtsJvmti',
    'CtsSecurityHostTestCases',  # TODO(ihf): remove when passing cleanly.
    'CtsSecurityHostTestCasesz',
    'CtsSensorTestCases',  # TODO(ihf): Remove when not needing 30 retries.
    'CtsSensorTestCasesz',
    'CtsViewTestCases',  # TODO(b/126741318): Fix performance regression and remove this.
    'CtsViewTestCasesz',
    'zzzzz'  # A bookend to simplify algorithm.
])

_SMOKE = [
    'CtsAccountManagerTestCases',
    'CtsAdminTestCases',
]

_BVT_ARC = [
    'CtsAccelerationTestCases',
    'CtsAdminTestCases',
]

_BVT_PERBUILD = [
    'CtsAccountManagerTestCases',
    'CtsBluetoothTestCases',
    'CtsGraphicsTestCases',
    'CtsJankDeviceTestCases',
    'CtsOpenGLTestCases',
    'CtsOpenGlPerf2TestCases',
    'CtsPermission2TestCases',
    'CtsSimpleperfTestCases',
    'CtsSpeechTestCases',
    'CtsTelecomTestCases',
    'CtsTelephonyTestCases',
    'CtsThemeDeviceTestCases',
    'CtsTransitionTestCases',
    'CtsTvTestCases',
    'CtsUiAutomationTestCases',
    'CtsUsbTests',
    'CtsVoiceSettingsTestCases',
]

# The suite is divided based on the run-time hint in the *.config file.
VMTEST_INFO_SUITES = collections.OrderedDict()
# This is the default suite for all the modules that are not specified below.
VMTEST_INFO_SUITES['vmtest-informational1'] = []
VMTEST_INFO_SUITES['vmtest-informational2'] = [
    'CtsMediaTestCases', 'CtsMediaStressTestCases', 'CtsHardwareTestCases'
]
VMTEST_INFO_SUITES['vmtest-informational3'] = [
    'CtsThemeHostTestCases', 'CtsHardwareTestCases', 'CtsLibcoreTestCases'
]
VMTEST_INFO_SUITES['vmtest-informational4'] = ['']

# Modules that are known to download and/or push media file assets.
_MEDIA_MODULES = [
    'CtsMediaTestCases',
    'CtsMediaStressTestCases',
    'CtsMediaBitstreamsTestCases',
]
_NEEDS_PUSH_MEDIA = _MEDIA_MODULES + [_ALL]

# Run `eject` for (and only for) each device with RM=1 in lsblk output.
_EJECT_REMOVABLE_DISK_COMMAND = (
    "\'lsblk -do NAME,RM | sed -n s/1$//p | xargs -n1 eject\'")
# Behave more like in the verififed mode.
_SECURITY_PARANOID_COMMAND = (
    "\'echo 3 > /proc/sys/kernel/perf_event_paranoid\'")
# TODO(kinaba): Come up with a less hacky way to handle the situation.
# {0} is replaced with the retry count. Writes either 1 (required by
# CtsSimpleperfTestCases) or 3 (CtsSecurityHostTestCases).
_ALTERNATING_PARANOID_COMMAND = (
    "\'echo $(({0} % 2 * 2 + 1)) > /proc/sys/kernel/perf_event_paranoid\'")
# Expose /proc/config.gz
_CONFIG_MODULE_COMMAND = "\'modprobe configs\'"

# TODO(b/126741318): Fix performance regression and remove this.
_SLEEP_60_COMMAND = "\'sleep 60\'"

# Preconditions applicable to public and internal tests.
_PRECONDITION = {
    'CtsSecurityHostTestCases': [
        _SECURITY_PARANOID_COMMAND, _CONFIG_MODULE_COMMAND
    ],
    # Tests are performance-sensitive, workaround to avoid CPU load on login.
    # TODO(b/126741318): Fix performance regression and remove this.
    'CtsViewTestCases': [_SLEEP_60_COMMAND],
}
_LOGIN_PRECONDITION = {
    'CtsAppSecurityHostTestCases': [_EJECT_REMOVABLE_DISK_COMMAND],
    'CtsJobSchedulerTestCases': [_EJECT_REMOVABLE_DISK_COMMAND],
    'CtsMediaTestCases': [_EJECT_REMOVABLE_DISK_COMMAND],
    'CtsOsTestCases': [_EJECT_REMOVABLE_DISK_COMMAND],
    'CtsProviderTestCases': [_EJECT_REMOVABLE_DISK_COMMAND],
}

_WIFI_CONNECT_COMMANDS = [
    # These need to stay in order. And the escaping is crazy, I know.
    """
    \'/usr/local/autotest/cros/scripts/wifi connect %s %s\' % (ssid, wifipass),
    '/usr/local/autotest/cros/scripts/reorder-services-moblab.sh wifi\'
"""
]

# Preconditions applicable to public tests.
_PUBLIC_PRECONDITION = {
    'CtsSecurityHostTestCases': [
        _SECURITY_PARANOID_COMMAND, _CONFIG_MODULE_COMMAND
    ],
    'CtsUsageStatsTestCases': _WIFI_CONNECT_COMMANDS,
    'CtsNetTestCases': _WIFI_CONNECT_COMMANDS,
    'CtsLibcoreTestCases': _WIFI_CONNECT_COMMANDS,
}

_PUBLIC_DEPENDENCIES = {
    'CtsCameraTestCases': ['lighting'],
    'CtsMediaTestCases': ['noloopback'],
}

# This information is changed based on regular analysis of the failure rate on
# partner moblabs.
_PUBLIC_MODULE_RETRY_COUNT = {
    'CtsAccessibilityServiceTestCases':  12,
    'CtsActivityManagerDeviceTestCases': 12,
    'CtsBluetoothTestCases':             10,
    'CtsFileSystemTestCases':            10,
    'CtsGraphicsTestCases':              12,
    'CtsIncidentHostTestCases':          12,
    'CtsNetTestCases':                   10,
    'CtsSecurityHostTestCases':          10,
    'CtsSensorTestCases':                12,
    'CtsUsageStatsTestCases':            10,
    _PUBLIC_COLLECT: 0,
}

# This information is changed based on regular analysis of the job run time on
# partner moblabs.

_TEST_LENGTH = {1: 'FAST', 2: 'SHORT', 3: 'MEDIUM', 4: 'LONG', 5: 'LENGTHY'}
_OVERRIDE_TEST_LENGTH = {
    'CtsDeqpTestCases': 4,  # LONG
    'CtsMediaTestCases': 4,
    'CtsMediaStressTestCases': 4,
    'CtsSecurityTestCases': 4,
    'CtsCameraTestCases': 4,
    _ALL: 4,
    # Even though collect tests doesn't run very long, it must be the very first
    # job executed inside of the suite. Hence it is the only 'LENGTHY' test.
    _COLLECT: 5,  # LENGTHY
}

# Enabling --logcat-on-failure can extend total run time significantly if
# individual tests finish in the order of 10ms or less (b/118836700). Specify
# modules here to not enable the flag.
_DISABLE_LOGCAT_ON_FAILURE = set([
    'all',
    'CtsDeqpTestCases',
    'CtsDeqpTestCases.dEQP-EGL',
    'CtsDeqpTestCases.dEQP-GLES2',
    'CtsDeqpTestCases.dEQP-GLES3',
    'CtsDeqpTestCases.dEQP-GLES31',
    'CtsDeqpTestCases.dEQP-VK',
])

_EXTRA_MODULES = {
    'CtsDeqpTestCases' : set([
        'CtsDeqpTestCases.dEQP-EGL',
        'CtsDeqpTestCases.dEQP-GLES2',
        'CtsDeqpTestCases.dEQP-GLES3',
        'CtsDeqpTestCases.dEQP-GLES31',
        'CtsDeqpTestCases.dEQP-VK'
    ])
}

# Moblab wants to shard dEQP really finely. This isn't needed anymore as it got
# faster, but I guess better safe than sorry.
_PUBLIC_EXTRA_MODULES = {
    'CtsDeqpTestCases' : [
        'CtsDeqpTestCases.dEQP-EGL',
        'CtsDeqpTestCases.dEQP-GLES2',
        'CtsDeqpTestCases.dEQP-GLES3',
        'CtsDeqpTestCases.dEQP-GLES31',
        'CtsDeqpTestCases.dEQP-VK.api',
        'CtsDeqpTestCases.dEQP-VK.binding_model',
        'CtsDeqpTestCases.dEQP-VK.clipping',
        'CtsDeqpTestCases.dEQP-VK.compute',
        'CtsDeqpTestCases.dEQP-VK.device_group',
        'CtsDeqpTestCases.dEQP-VK.draw',
        'CtsDeqpTestCases.dEQP-VK.dynamic_state',
        'CtsDeqpTestCases.dEQP-VK.fragment_operations',
        'CtsDeqpTestCases.dEQP-VK.geometry',
        'CtsDeqpTestCases.dEQP-VK.glsl',
        'CtsDeqpTestCases.dEQP-VK.image',
        'CtsDeqpTestCases.dEQP-VK.info',
        'CtsDeqpTestCases.dEQP-VK.memory',
        'CtsDeqpTestCases.dEQP-VK.multiview',
        'CtsDeqpTestCases.dEQP-VK.pipeline',
        'CtsDeqpTestCases.dEQP-VK.protected_memory',
        'CtsDeqpTestCases.dEQP-VK.query_pool',
        'CtsDeqpTestCases.dEQP-VK.rasterization',
        'CtsDeqpTestCases.dEQP-VK.renderpass',
        'CtsDeqpTestCases.dEQP-VK.renderpass2',
        'CtsDeqpTestCases.dEQP-VK.robustness',
        'CtsDeqpTestCases.dEQP-VK.sparse_resources',
        'CtsDeqpTestCases.dEQP-VK.spirv_assembly',
        'CtsDeqpTestCases.dEQP-VK.ssbo',
        'CtsDeqpTestCases.dEQP-VK.subgroups',
        'CtsDeqpTestCases.dEQP-VK.synchronization',
        'CtsDeqpTestCases.dEQP-VK.tessellation',
        'CtsDeqpTestCases.dEQP-VK.texture',
        'CtsDeqpTestCases.dEQP-VK.ubo',
        'CtsDeqpTestCases.dEQP-VK.wsi',
        'CtsDeqpTestCases.dEQP-VK.ycbcr'
    ]
}

_EXTRA_COMMANDLINE = {
    'CtsDeqpTestCases.dEQP-EGL': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-EGL.*'
    ],
    'CtsDeqpTestCases.dEQP-GLES2': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-GLES2.*'
    ],
    'CtsDeqpTestCases.dEQP-GLES3': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-GLES3.*'
    ],
    'CtsDeqpTestCases.dEQP-GLES31': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-GLES31.*'
    ],
    'CtsDeqpTestCases.dEQP-VK': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.api': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.api.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.binding_model': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.binding_model.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.clipping': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.clipping.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.compute': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.compute.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.device_group': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.device_group*'  # Not ending on .* like most others!
    ],
    'CtsDeqpTestCases.dEQP-VK.draw': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.draw.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.dynamic_state': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.dynamic_state.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.fragment_operations': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.fragment_operations.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.geometry': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.geometry.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.glsl': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.glsl.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.image': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.image.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.info': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.info*'  # Not ending on .* like most others!
    ],
    'CtsDeqpTestCases.dEQP-VK.memory': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.memory.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.multiview': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.multiview.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.pipeline': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.pipeline.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.protected_memory': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.protected_memory.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.query_pool': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.query_pool.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.rasterization': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.rasterization.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.renderpass': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.renderpass.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.renderpass2': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.renderpass2.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.robustness': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.robustness.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.sparse_resources': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.sparse_resources.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.spirv_assembly': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.spirv_assembly.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.ssbo': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.ssbo.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.subgroups': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.subgroups.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.synchronization': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.synchronization.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.tessellation': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.tessellation.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.texture': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.texture.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.ubo': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.ubo.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.wsi': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.wsi.*'
    ],
    'CtsDeqpTestCases.dEQP-VK.ycbcr': [
        '--include-filter', 'CtsDeqpTestCases', '--module', 'CtsDeqpTestCases',
        '--test', 'dEQP-VK.ycbcr.*'
    ]
}

_EXTRA_ATTRIBUTES = {
    'CtsDeqpTestCases': ['suite:arc-cts', 'suite:arc-cts-deqp'],
    'CtsDeqpTestCases.dEQP-EGL': [
        'suite:arc-cts-deqp', 'suite:graphics_per-day'
    ],
    'CtsDeqpTestCases.dEQP-GLES2': [
        'suite:arc-cts-deqp', 'suite:graphics_per-day'
    ],
    'CtsDeqpTestCases.dEQP-GLES3': [
        'suite:arc-cts-deqp', 'suite:graphics_per-day'
    ],
    'CtsDeqpTestCases.dEQP-GLES31': [
        'suite:arc-cts-deqp', 'suite:graphics_per-day'
    ],
    'CtsDeqpTestCases.dEQP-VK': [
        'suite:arc-cts-deqp', 'suite:graphics_per-day'
    ],
    _COLLECT: ['suite:arc-cts-qual', 'suite:arc-cts'],
}


def get_tradefed_build(line):
    """Gets the build of Android CTS from tradefed.

    @param line Tradefed identification output on startup. Example:
                Android Compatibility Test Suite 7.0 (3423912)
    @return Tradefed CTS build. Example: 2813453.
    """
    # Sample string: Android Compatibility Test Suite 7.0 (3423912)
    m = re.search(r' \((.*)\)', line)
    if m:
        return m.group(1)
    logging.warning('Could not identify build in line "%s".', line)
    return '<unknown>'


def get_tradefed_revision(line):
    """Gets the revision of Android CTS from tradefed.

    @param line Tradefed identification output on startup. Example:
                Android CTS 6.0_r6 build:2813453
    @return Tradefed CTS revision. Example: 6.0_r6.
    """
    m = re.search(r'Android Compatibility Test Suite (.*) \(', line)
    if m:
        return m.group(1)
    logging.warning('Could not identify revision in line "%s".', line)
    return None


def get_bundle_abi(filename):
    """Makes an educated guess about the ABI.

    In this case we chose to guess by filename, but we could also parse the
    xml files in the module. (Maybe this needs to be done in the future.)
    """
    if filename.endswith('_x86-arm.zip'):
        return 'arm'
    if filename.endswith('_x86-x86.zip'):
        return 'x86'
    raise Exception('Could not determine ABI from "%s".' % filename)


def get_bundle_revision(filename):
    """Makes an educated guess about the revision.

    In this case we chose to guess by filename, but we could also parse the
    xml files in the module.
    """
    m = re.search(r'(?<=android-cts-)(.*)-linux', filename)
    if m is not None:
        return m.group(1)
    return None


def get_extension(module, abi, revision, public=False, camera_facing=None):
    """Defines a unique string.

    Notice we chose module revision first, then abi, as the module revision
    changes at least on a monthly basis. This ordering makes it simpler to
    add/remove modules.
    @param module: CTS module which will be tested in the control file. If 'all'
                   is specified, the control file will runs all the tests.
    @param public: boolean variable to specify whether or not the bundle is from
                   public source or not.
    @param camera_facing: string or None indicate whether it's camerabox tests
                          for specific camera facing or not.
    @return string: unique string for specific tests. If public=True then the
                    string is "<abi>.<module>", otherwise, the unique string is
                    "<revision>.<abi>.<module>".
    """
    ext_parts = [abi, module]
    if not public:
        ext_parts = [revision] + ext_parts
    if camera_facing:
        ext_parts.extend(['camerabox', camera_facing])
    return '.'.join(ext_parts)


def get_doc(modules, abi, is_public):
    """Defines the control file DOC string."""
    if not modules.intersection(get_collect_modules(is_public)):
        # Generate per-module DOC
        doc = ('Run module %s of the '
               'Android Compatibility Test Suite (CTS) using %s ABI in '
               'the ARC++ container.' % (', '.join(sorted(list(modules))), abi))
    else:
        doc = ('Run all of the '
               'Android Compatibility Test Suite (CTS) using %s ABI in '
               'the ARC++ container.' % (abi))

    return doc


def get_controlfile_name(module,
                         abi,
                         revision,
                         public=False,
                         camera_facing=None):
    """Defines the control file name.

    @param module: CTS module which will be tested in the control file. If 'all'
                   is specified, the control file will runs all the tests.
    @param public: boolean variable to specify whether or not the bundle is from
                   public source or not.
    @param camera_facing: string or None indicate whether it's camerabox tests
                          for specific camera facing or not.
    @return string: control file for specific tests. If public=True or
                    module=all, then the name will be "control.<abi>.<module>",
                    otherwise, the name will be
                    "control.<revision>.<abi>.<module>".
    """
    return 'control.%s' % get_extension(module, abi, revision, public,
                                        camera_facing)


def get_sync_count(_modules, _abi, _is_public):
    return 1


def get_suites(modules, abi, is_public):
    """Defines the suites associated with a module.

    @param module: CTS module which will be tested in the control file. If 'all'
                   is specified, the control file will runs all the tests.
    # TODO(ihf): Make this work with the "all" and "collect" generation,
    # which currently bypass this function.
    """
    if is_public:
        # On moblab everything runs in the same suite.
        return ['suite:cts_P']

    # As this is not called for the "all" runs we can safely assume that each
    # module runs in suite:arc-cts.
    suites = ['suite:arc-cts']
    for module in modules:
        if module in get_collect_modules(is_public):
            # We collect all tests both in arc-cts and arc-cts-qual as both have
            # a chance to be complete (and used for submission).
            suites += ['suite:arc-cts-qual']
        if module in _EXTRA_ATTRIBUTES:
            # Special cases come with their own suite definitions.
            suites += _EXTRA_ATTRIBUTES[module]
        if module in _SMOKE:
            # Handle VMTest by adding a few jobs to suite:smoke.
            suites += ['suite:smoke']
        if module not in get_collect_modules(is_public) and abi == 'x86':
            # Handle a special builder for running all of CTS in a betty VM.
            # TODO(ihf): figure out if this builder is still alive/needed.
            vm_suite = None
            for suite in VMTEST_INFO_SUITES:
                if not vm_suite:
                    vm_suite = suite
                if module in VMTEST_INFO_SUITES[suite]:
                    vm_suite = suite
            suites += ['suite:%s' % vm_suite]
        # One or two modules hould be in suite:bvt-arc to cover CQ/PFQ. A few
        # spare/fast modules can run in suite:bvt-perbuild in case we need a
        # replacement for the module in suite:bvt-arc (integration test for
        # cheets_CTS only, not a correctness test for CTS content).
        if module in _BVT_ARC and abi == 'arm':
            suites += ['suite:bvt-arc']
        elif module in _BVT_PERBUILD and abi == 'arm':
            suites += ['suite:bvt-perbuild']
    return sorted(list(set(suites)))


def get_dependencies(modules, abi, is_public, is_camerabox_test):
    """Defines lab dependencies needed to schedule a module.

    Currently we only care about x86 ABI tests, which must run on Intel boards.
    @param module: CTS module which will be tested in the control file. If 'all'
                   is specified, the control file will runs all the tests.
    @param abi: string that specifies the application binary interface of the
                current test.
    @param is_public: boolean variable to specify whether or not the bundle is
                      from public source or not.
    @param is_camerabox_test: boolean variable to specify whether it's camerabox
                              related test.
    """
    dependencies = ['arc']
    if abi == 'x86':
        # We only want to run x86 ABI on DUTs that have an Intel/AMD CPU.
        dependencies.append('cts_abi_x86')

    if is_camerabox_test:
        dependencies.append('camerabox')

    for module in modules:
        if is_public and module in _PUBLIC_DEPENDENCIES:
            dependencies.extend(_PUBLIC_DEPENDENCIES[module])

    return ', '.join(dependencies)


def get_job_retries(modules, is_public):
    """Define the number of job retries associated with a module.

    @param module: CTS module which will be tested in the control file. If a
                   special module is specified, the control file will runs all
                   the tests without retry.
    """
    # TODO(haddowk): remove this when cts p has stabalized.
    if is_public:
        return 1
    retries = 1  # 0 is NO job retries, 1 is one retry etc.
    for module in modules:
        # We don't want job retries for module collection or special cases.
        if (module in get_collect_modules(is_public) or
            module in _EXTRA_MODULES['CtsDeqpTestCases']):
            retries = 0
    return retries


def get_max_retries(modules, abi, suites, is_public):
    """Partners experiance issues where some modules are flaky and require more

       retries.  Calculate the retry number per module on moblab.
    @param module: CTS module which will be tested in the control file.
    """
    retry = -1
    if is_public:
        # In moblab at partners we may need many more retries than in lab.
        for module in modules:
            if module in _PUBLIC_MODULE_RETRY_COUNT:
                retry = max(retry, _PUBLIC_MODULE_RETRY_COUNT[module])
    else:
        # See if we have any special values for the module, chose the largest.
        for module in modules:
            if module in _CTS_MAX_RETRIES:
                retry = max(retry, _CTS_MAX_RETRIES[module])

    # Ugly overrides.
    for module in modules:
        # In bvt we don't want to hold the CQ/PFQ too long.
        if ('suite:bvt-arc' in suites or
                'suite:bvt-perbuild' in suites and abi == 'arm'):
            retry = 3
        # During qualification we want at least 9 retries, possibly more.
        if 'suite:arc-cts-qual' in suites:
            retry = max(retry, _CTS_QUAL_RETRIES)
        # Collection should never have a retry. This needs to be last.
        if module in get_collect_modules(is_public):
            retry = 0
    if retry >= 0:
        return retry
    # Default case omits the retries in the control file, so tradefed_test.py
    # can chose its own value.
    return None


def get_max_result_size_kb(modules, is_public):
    """Returns the maximum expected result size in kB for autotest.

    @param modules: List of CTS modules to be tested by the control file.
    """
    for module in modules:
        if (module in get_collect_modules(is_public) or
            module == 'CtsDeqpTestCases'):
            # Both arm, x86 tests results normally is below 200MB.
            # 1000MB should be sufficient for CTS tests and dump logs for
            # android-cts.
            return 1000 * 1024
    # Individual module normal produces less results than all modules, which
    # is ranging from 4MB to 50MB.
    # 500MB should be sufficient to handle all the cases.
    return 500 * 1024


def get_extra_args(modules, is_public):
    """Generate a list of extra arguments to pass to the test.

    Some params are specific to a particular module, particular mode or
    combination of both, generate a list of arguments to pass into the template.

    @param modules: List of CTS modules to be tested by the control file.
    """
    extra_args = set()
    preconditions = set()
    login_preconditions = set()
    for module in modules:
        if is_public:
            extra_args.add('warn_on_test_retry=False')
            extra_args.add('retry_manual_tests=True')
            if module in _PUBLIC_PRECONDITION:
                preconditions = preconditions | set(
                    _PUBLIC_PRECONDITION[module])
        else:
            if module in _LOGIN_PRECONDITION:
                login_preconditions = login_preconditions | set(
                    _LOGIN_PRECONDITION[module])
            if module in _PRECONDITION:
                preconditions = preconditions | set(_PRECONDITION[module])
    # Notice: we are just squishing the preconditions for all modules together.
    # We do not honor any ordering, instead we ensure every precondition is
    # added only once. This may not always be correct. In such a case one should
    # split the bookmarks in a way that the modules with conflicting
    # preconditions end up in separate control files.
    if preconditions:
        # To properly escape the public preconditions we need to format the list
        # manually using join.
        extra_args.add('precondition_commands=[%s]' % ', '.join(
            sorted(list(preconditions))))
    if login_preconditions:
        extra_args.add('login_precondition_commands=[%s]' % ', '.join(
            sorted(list(login_preconditions))))
    return sorted(list(extra_args))


def get_test_length(modules):
    """ Calculate the test length based on the module name.

    To better optimize DUT's connected to moblab, it is better to run the
    longest tests and tests that require limited resources.  For these modules
    override from the default test length.

    @param module: CTS module which will be tested in the control file. If 'all'
                   is specified, the control file will runs all the tests.

    @return string: one of the specified test lengths:
                    ['FAST', 'SHORT', 'MEDIUM', 'LONG', 'LENGTHY']
    """
    length = 3  # 'MEDIUM'
    for module in modules:
        if module in _OVERRIDE_TEST_LENGTH:
            length = max(length, _OVERRIDE_TEST_LENGTH[module])
    return _TEST_LENGTH[length]


def get_test_priority(modules, is_public):
    """ Calculate the test priority based on the module name.

    On moblab run all long running tests and tests that have some unique
    characteristic at a higher priority (50).

    This optimizes the total run time of the suite assuring the shortest
    time between suite kick off and 100% complete.

    @param module: CTS module which will be tested in the control file.

    @return int: None if priorty not to be overridden or 50
    """
    priority = 0
    if is_public:
        for module in modules:
            if (module in _OVERRIDE_TEST_LENGTH or
                    module in _PUBLIC_DEPENDENCIES or
                    module in _PUBLIC_PRECONDITION or
                    module.split('.')[0] in _OVERRIDE_TEST_LENGTH):
                priority = max(priority, 50)
            if module == _PUBLIC_COLLECT:
                priority = max(priority, 70)
    return priority


def _format_collect_cmd(retry):
    """Returns a list specifying tokens for tradefed to list all tests."""
    if retry:
        return None
    cmd = ['run', 'commandAndExit', 'collect-tests-only', '--disable-reboot']
    for m in _MEDIA_MODULES:
        cmd.append('--module-arg')
        cmd.append('%s:skip-media-download:true' % m)
    return cmd


def _get_special_command_line(modules, _is_public):
    """This function allows us to split a module like Deqp into segments."""
    cmd = []
    for module in sorted(modules):
        cmd += _EXTRA_COMMANDLINE.get(module, [])
    return cmd


def _format_modules_cmd(is_public, modules=None, retry=False):
    """Returns list of command tokens for tradefed."""
    if retry:
        cmd = ['run', 'commandAndExit', 'retry', '--retry', '{session_id}']
    else:
        cmd = ['run', 'commandAndExit', 'cts']
        special_cmd = _get_special_command_line(modules, is_public)
        if special_cmd:
            cmd.extend(special_cmd)
        # We run each module with its own --include-filter command/option.
        # https://source.android.com/compatibility/cts/run
        elif modules:
            for module in sorted(modules):
                cmd += ['--include-filter', module]
        # For runs create a logcat file for each individual failure.
        # Not needed on moblab, nobody is going to look at them.
        if not (modules.intersection(_DISABLE_LOGCAT_ON_FAILURE) or
                is_public):
            cmd.append('--logcat-on-failure')
    return cmd


def get_run_template(modules, is_public, retry=False):
    """Command to run the modules specified by a control file."""
    cmd = None
    if modules.intersection(get_collect_modules(is_public)):
        if _COLLECT in modules or _PUBLIC_COLLECT in modules:
            cmd = _format_collect_cmd(retry=retry)
        elif _ALL in modules:
            cmd = _format_modules_cmd(is_public, modules, retry=retry)
    else:
        cmd = _format_modules_cmd(is_public, modules, retry=retry)
    return cmd


def get_retry_template(modules, is_public):
    """Command to retry the failed modules as specified by a control file."""
    return get_run_template(modules, is_public, retry=True)


def get_extra_modules_dict(is_public):
    if is_public:
        return _PUBLIC_EXTRA_MODULES
    return _EXTRA_MODULES


def get_extra_modules(is_public):
    extra_modules_dict = get_extra_modules_dict(is_public)
    modules = []
    for _, extra_modules in extra_modules_dict.items():
        modules += extra_modules
    return set(modules)


def get_modules_to_remove(is_public):
    if is_public:
        return get_extra_modules_dict(is_public).keys()
    return []


def calculate_timeout(modules, suites, is_public):
    """Calculation for timeout of tradefed run.

    Timeout is at least one hour, except if part of BVT_ARC.
    Notice these do get adjusted dynamically by number of ABIs on the DUT.
    """
    if 'suite:bvt-arc' in suites:
        return int(3600 * _BVT_TIMEOUT)
    if 'suite:arc-cts-qual' in suites and not (_COLLECT in modules or
                                               _PUBLIC_COLLECT in modules):
        return int(3600 * _QUAL_TIMEOUT)

    timeout = 0
    # First module gets 1h (standard), all other half hour extra (heuristic).
    delta = 3600
    for module in modules:
        if is_public and module.startswith('CtsDeqpTestCases'):
            timeout = max(timeout, int(3600 * 12))
        else:
            # Modules that run very long are encoded here.
            if module in _CTS_TIMEOUT:
                timeout += int(3600 * _CTS_TIMEOUT[module])
            # We have too many of these modules and they run fast.
            elif 'Jvmti' in module:
                timeout += 300
            else:
                timeout += delta
                delta = 1800
    return timeout


def needs_push_media(modules):
    """Oracle to determine if to push several GB of media files to DUT."""
    if modules.intersection(set(_NEEDS_PUSH_MEDIA)):
        return True
    return False


def get_controlfile_content(combined,
                            modules,
                            abi,
                            revision,
                            build,
                            uri,
                            suites=None,
                            is_public=False,
                            camera_facing=None):
    """Returns the text inside of a control file.

    @param combined: name to use for this combination of modules.
    @param modules: list of CTS modules which will be tested in the control
                   file. If 'all' is specified, the control file will runs
                   all the tests.
    """
    # We tag results with full revision now to get result directories containing
    # the revision. This fits stainless/ better.
    tag = '%s' % get_extension(combined, abi, revision, is_public,
                               camera_facing)
    # For test_that the NAME should be the same as for the control file name.
    # We could try some trickery here to get shorter extensions for a default
    # suite/ARM. But with the monthly uprevs this will quickly get confusing.
    name = 'cheets_CTS_P.%s' % tag
    if not suites:
        suites = get_suites(modules, abi, is_public)
    attributes = ', '.join(suites)
    uri = None if is_public else uri
    target_module = None
    if combined not in get_collect_modules(is_public):
        target_module = combined
    for target, m in get_extra_modules_dict(is_public).items():
        if combined in m:
            target_module = target
    return _CONTROLFILE_TEMPLATE.render(
        name=name,
        attributes=attributes,
        dependencies=get_dependencies(
            modules,
            abi,
            is_public,
            is_camerabox_test=(camera_facing is not None)),
        job_retries=get_job_retries(modules, is_public),
        max_result_size_kb=get_max_result_size_kb(modules, is_public),
        revision=revision,
        build=build,
        abi=abi,
        needs_push_media=needs_push_media(modules),
        tag=tag,
        uri=uri,
        DOC=get_doc(modules, abi, is_public),
        max_retries=get_max_retries(modules, abi, suites, is_public),
        timeout=calculate_timeout(modules, suites, is_public),
        run_template=get_run_template(modules, is_public),
        retry_template=get_retry_template(modules, is_public),
        target_module=target_module,
        target_plan=None,
        test_length=get_test_length(modules),
        priority=get_test_priority(modules, is_public),
        extra_args=get_extra_args(modules, is_public),
        sync_count=get_sync_count(modules, abi, is_public),
        camera_facing=camera_facing)


def get_tradefed_data(path, is_public):
    """Queries tradefed to provide us with a list of modules.

    Notice that the parsing gets broken at times with major new CTS drops.
    """
    tradefed = os.path.join(path, 'android-cts/tools/cts-tradefed')
    # Forgive me for I have sinned. Same as: chmod +x tradefed.
    os.chmod(tradefed, os.stat(tradefed).st_mode | stat.S_IEXEC)
    cmd_list = [tradefed, 'list', 'modules']
    logging.info('Calling tradefed for list of modules.')
    # TODO(ihf): Get a tradefed command which terminates then refactor.
    p = subprocess.Popen(cmd_list, stdout=subprocess.PIPE)
    modules = []
    build = '<unknown>'
    line = ''
    revision = None
    # The process does not terminate, but we know the last test is vm-tests-tf.
    while True:
        line = p.stdout.readline().strip()
        # Android Compatibility Test Suite 7.0 (3423912)
        if line.startswith('Android Compatibility Test Suite '):
            logging.info('Unpacking: %s.', line)
            build = get_tradefed_build(line)
            revision = get_tradefed_revision(line)
        elif line.startswith('Cts'):
            modules.append(line)
        elif line.startswith('cts-'):
            modules.append(line)
        elif line.startswith('signed-Cts'):
            modules.append(line)
        elif line.startswith('vm-tests-tf'):
            modules.append(line)
            break  # TODO(ihf): Fix using this as EOS.
        elif line.isspace or line.startswith('Use "help"'):
            pass
        else:
            logging.warning('Ignoring "%s"', line)
    p.kill()
    p.wait()
    for module in get_modules_to_remove(is_public):
        modules.remove(module)
    return modules, build, revision


def download(uri, destination):
    """Download |uri| to local |destination|."""
    if uri.startswith('http'):
        subprocess.check_call(['wget', uri, '-P', destination])
    elif uri.startswith('gs'):
        subprocess.check_call(['gsutil', 'cp', uri, destination])
    else:
        raise Exception


@contextlib.contextmanager
def pushd(d):
    """Defines pushd."""
    current = os.getcwd()
    os.chdir(d)
    try:
        yield
    finally:
        os.chdir(current)


def unzip(filename, destination):
    """Unzips a zip file to the destination directory."""
    with pushd(destination):
        # We are trusting Android to have a sane zip file for us.
        with zipfile.ZipFile(filename) as zf:
            zf.extractall()


def get_collect_modules(is_public):
    if is_public:
        return set([_PUBLIC_COLLECT])
    return set([_COLLECT])


@contextlib.contextmanager
def TemporaryDirectory(prefix):
    """Poor man's python 3.2 import."""
    tmp = tempfile.mkdtemp(prefix=prefix)
    try:
        yield tmp
    finally:
        shutil.rmtree(tmp)


def get_word_pattern(m, l=1):
    """Return the first few words of the CamelCase module name.

    Break after l+1 CamelCase word.
    Example: CtsDebugTestCases -> CtsDebug.
    """
    s = re.findall('^[a-z]+|[A-Z]*[^A-Z0-9]*', m)[0:l + 1]
    # Ignore Test or TestCases at the end as they don't add anything.
    if len(s) > l:
        if s[l].startswith('Test'):
            return ''.join(s[0:l])
        if s[l - 1] == 'Test' and s[l].startswith('Cases'):
            return ''.join(s[0:l - 1])
    return ''.join(s[0:l + 1])


def combine_modules_by_common_word(modules):
    """Returns a dictionary of (combined name, set of module) pairs.

    This gives a mild compaction of control files (from about 320 to 135).
    Example:
    'CtsVoice' -> ['CtsVoiceInteractionTestCases', 'CtsVoiceSettingsTestCases']
    """
    d = dict()
    # On first pass group modules with common first word together.
    for module in modules:
        pattern = get_word_pattern(module)
        v = d.get(pattern, [])
        v.append(module)
        v.sort()
        d[pattern] = v
    # Second pass extend names to maximum common prefix. This keeps control file
    # names identical if they contain only one module and less ambiguous if they
    # contain multiple modules.
    combined = dict()
    for key in sorted(d):
        # Instead if a one syllable prefix use longest common prefix of modules.
        prefix = os.path.commonprefix(d[key])
        # Beautification: strip Tests/TestCases from end of prefix, but only if
        # there is more than one module in the control file. This avoids
        # slightly strange combination of having CtsDpiTestCases1/2 inside of
        # CtsDpiTestCases (now just CtsDpi to make it clearer there are several
        # modules in this control file).
        if len(d[key]) > 1:
            prefix = re.sub('TestCases$', '', prefix)
            prefix = re.sub('Tests$', '', prefix)
        # Beautification: CtsMedia files run very long and are unstable. Give
        # each module its own control file, even though this heuristic would
        # lump them together.
        if prefix.startswith('CtsMedia'):
            for media in d[key]:
                combined[media] = set([media])
        else:
            combined[prefix] = set(d[key])
        # Sanity check.
        #print key, len(d[key]), prefix, d[key]
    print 'Reduced number of control files from %d to %d.' % (len(modules),
                                                              len(combined))
    return combined


def combine_modules_by_bookmark(modules):
    """Return a manually curated list of name, module pairs.

    Ideally we split "all" into a dictionary of maybe 10-20 equal runtime parts.
    (Say 2-5 hours each.) But it is ok to run problematic modules alone.
    """
    d = dict()
    # Figure out sets of modules between bookmarks. Not optimum time complexity.
    for bookmark in _QUAL_BOOKMARKS:
        if modules:
            for module in sorted(modules):
                if module < bookmark:
                    v = d.get(bookmark, set())
                    v.add(module)
                    d[bookmark] = v
            # Remove processed modules.
            if bookmark in d:
                modules = modules - d[bookmark]
    # Clean up names.
    combined = dict()
    for key in sorted(d):
        v = sorted(d[key])
        # New name is first element '_-_' last element.
        # Notice there is a bug in $ADB_VENDOR_KEYS path name preventing
        # arbitrary characters.
        prefix = v[0] + '_-_' + v[-1]
        combined[prefix] = set(v)
    return combined


def write_controlfile(name, modules, abi, revision, build, uri, suites,
                      is_public):
    """Write a single control file."""
    filename = get_controlfile_name(name, abi, revision, is_public)
    content = get_controlfile_content(name, modules, abi, revision, build, uri,
                                      suites, is_public)
    with open(filename, 'w') as f:
        f.write(content)


def write_moblab_controlfiles(modules, abi, revision, build, uri, is_public):
    """Write all control files for moblab.

    Nothing gets combined.

    Moblab uses one module per job. In some cases like Deqp which can run super
    long it even creates several jobs per module. Moblab can do this as it has
    less relative overhead spinning up jobs than the lab.
    """
    for module in modules:
        write_controlfile(module, set([module]), abi, revision, build, uri,
                          ['suite:cts_P'], is_public)


def write_regression_controlfiles(modules, abi, revision, build, uri,
                                  is_public):
    """Write all control files for stainless/ToT regression lab coverage.

    Regression coverage on tot currently relies heavily on watching stainless
    dashboard and sponge. So instead of running everything in a single run
    we split CTS into many jobs. It used to be one job per module, but that
    became too much in P (more than 300 per ABI). Instead we combine modules
    with similar names and run these in the same job (alphabetically).
    """
    combined = combine_modules_by_common_word(set(modules))
    for key in combined:
        write_controlfile(key, combined[key], abi, revision, build, uri, None,
                          is_public)
    # Seed this with modules that we want to split (like Deqp.VK etc).
    # for module in get_extra_modules(is_public):
    #     write_controlfile(module, set([module]), abi, revision, build, uri,
    #                       None, is_public)


def write_qualification_controlfiles(modules, abi, revision, build, uri,
                                     is_public):
    """Write all control files to run "all" tests for qualification.

    Qualification was performed on N by running all tests using tradefed
    sharding (specifying SYNC_COUNT=2) in the control files. In skylab
    this is currently not implemented, so we fall back to autotest sharding
    all CTS tests into 10-20 hand chosen shards.
    """
    combined = combine_modules_by_bookmark(set(modules))
    for key in combined:
        write_controlfile('all.' + key, combined[key], abi, revision, build,
                          uri, ['suite:arc-cts-qual'], is_public)


def write_collect_controlfiles(_modules, abi, revision, build, uri, is_public):
    """Write all control files for test collection used as reference to

    compute completeness (missing tests) on the CTS dashboard.
    """
    suites = ['suite:arc-cts', 'suite:arc-cts-qual']
    if is_public:
        suites = ['suite:cts_P']
    for module in get_collect_modules(is_public):
        write_controlfile(module, set([module]), abi, revision, build, uri,
                          suites, is_public)


def write_extra_deqp_controlfiles(_modules, abi, revision, build, uri,
                                  is_public):
    """Write all control files for splitting Deqp into pieces.

    This is used in particular by moblab to load balance. A similar approach
    was also used during bringup of grunt to split media tests.
    """
    submodules = get_extra_modules_dict(is_public)['CtsDeqpTestCases']
    suites = ['suite:arc-cts-deqp', 'suite:graphics_per-day']
    if is_public:
        suites = ['suite:cts_P']
    for module in submodules:
        write_controlfile(module, set([module]), abi, revision, build, uri,
                          suites, is_public)


def write_extra_camera_controlfiles(abi, revision, build, uri, is_public):
    """Control files for CtsCameraTestCases.camerabox.*"""
    module = 'CtsCameraTestCases'
    for facing in ['back', 'front']:
        name = get_controlfile_name(module, abi,
                                    revision, is_public, facing)
        content = get_controlfile_content(module, set([module]), abi,
                                          revision, build, uri,
                                          None, is_public, facing)
        with open(name, 'w') as f:
            f.write(content)


def main(uris, is_public):
    """Downloads each bundle in |uris| and generates control files for each

    module as reported to us by tradefed.
    """
    for uri in uris:
        abi = get_bundle_abi(uri)
        # Get tradefed data by downloading & unzipping the files

        with TemporaryDirectory(prefix='cts-android_') as tmp:
            logging.info('Downloading to %s.', tmp)
            download(uri, tmp)
            bundle = os.path.join(tmp, os.path.basename(uri))
            logging.info('Extracting %s.', bundle)
            unzip(bundle, tmp)
            modules, build, revision = get_tradefed_data(tmp, is_public)
            if not revision:
                raise Exception('Could not determine revision.')

            logging.info('Writing all control files.')
            if is_public:
                write_moblab_controlfiles(modules, abi, revision, build, uri,
                                          is_public)
            else:
                write_regression_controlfiles(modules, abi, revision, build,
                                              uri, is_public)
                write_qualification_controlfiles(modules, abi, revision, build,
                                                 uri, is_public)
                write_extra_camera_controlfiles(abi, revision, build,
                                                uri, is_public)
            write_collect_controlfiles(modules, abi, revision, build, uri,
                                       is_public)
            write_extra_deqp_controlfiles(None, abi, revision, build, uri,
                                          is_public)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(
        description='Create control files for a CTS bundle on GS.',
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        'uris',
        nargs='+',
        help='List of Google Storage URIs to CTS bundles. Example:\n'
        'gs://chromeos-arc-images/cts/bundle/2016-06-02/'
        'android-cts-6.0_r6-linux_x86-arm.zip')
    parser.add_argument(
        '--is_public',
        dest='is_public',
        default=False,
        action='store_true',
        help='Generate the public control files for CTS, default generate'
        ' the internal control files')
    args = parser.parse_args()
    main(args.uris, args.is_public)
