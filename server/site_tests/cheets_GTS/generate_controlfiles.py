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
    # Copyright 2016 The Chromium OS Authors. All rights reserved.
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
    def run_GTS(ntuples):
        host_list = [hosts.create_host(machine) for machine in ntuples]
    {% else %}
    def run_GTS(machine):
        host_list = [hosts.create_host(machine)]
    {%- endif %}
        job.run_test(
            'cheets_GTS',
            hosts=host_list,
            iterations=1,
    {%- if max_retries != None %}
            max_retry={{max_retries}},
    {%- endif %}
            tag='{{tag}}',
            test_name='{{name}}',
    {%- if authkey %}
            authkey='{{authkey}}',
    {%- endif %}
            run_template={{run_template}},
            retry_template={{retry_template}},
            target_module={% if target_module %}'{{target_module}}'{% else %}None{%endif%},
            target_plan={% if target_plan %}'{{target_plan}}'{% else %}None{% endif %},
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
    parallel_simple(run_GTS, ntuples, log=False)
    {% else -%}
    parallel_simple(run_GTS, machines)
    {% endif %}
"""))

_ALL = 'all'
# The dashboard suppresses upload to APFE for GS directories (based on autotest
# tag) that contain 'tradefed-run-collect-tests'. b/119640440
# Do not change the name/tag without adjusting the dashboard.
_COLLECT = 'tradefed-run-collect-tests-only-internal'
_PUBLIC_COLLECT = 'tradefed-run-collect-tests-only'

_GTS_MAX_RETRIES = {}

# TODO(ihf): Update timeouts once P is more stable.
# Timeout in hours.
_GTS_TIMEOUT = {
    'GtsExoPlayerTestCases': 1.5,
    'GtsMediaTestCases': 8,
    'GtsOsTestCases': 0.25,
    _ALL: 24,
    _COLLECT: 0.25,
    _PUBLIC_COLLECT: 0.25,
}

# Any test that runs as part as blocking BVT needs to be stable and fast. For
# this reason we enforce a tight timeout on these modules/jobs.
# Timeout in hours. (0.1h = 6 minutes)
_BVT_TIMEOUT = 0.1
# We allow a very long runtime for qualification (1 day).
_QUAL_TIMEOUT = 24

_QUAL_BOOKMARKS = sorted([
    'A',  # A bookend to simplify partition algorithm.
    'zzzzz'  # A bookend to simplify algorithm.
])

_SMOKE = [
    'GtsAdminTestCases',
    'GtsMemoryTestCases',
]

_BVT_ARC = [
    'GtsMemoryHostTestCases',
]

_BVT_PERBUILD = [
    'GtsAdminTestCases',
    'GtsMemoryHostTestCases',
    'GtsMemoryTestCases',
    'GtsNetTestCases',
    'GtsOsTestCases',
    'GtsPlacementTestCases',
    'GtsPrivacyTestCases',
]

# Modules that are known to download and/or push media file assets.
_MEDIA_MODULES = ['GtsYouTubeTestCases']
# TODO(b/128874657): Wire _NEEDS_PUSH_MEDIA to the control file and the test
# code, so that the download can be cached and shared among test runs.
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

# Preconditions applicable to public and internal tests.
_PRECONDITION = {}
_LOGIN_PRECONDITION = {}
_WIFI_CONNECT_COMMANDS = []

# Preconditions applicable to public tests.
_PUBLIC_PRECONDITION = {}
_PUBLIC_DEPENDENCIES = {}

# This information is changed based on regular analysis of the failure rate on
# partner moblabs.
_PUBLIC_MODULE_RETRY_COUNT = {}

# This information is changed based on regular analysis of the job run time on
# partner moblabs.

_TEST_LENGTH = {1: 'FAST', 2: 'SHORT', 3: 'MEDIUM', 4: 'LONG', 5: 'LENGTHY'}
_OVERRIDE_TEST_LENGTH = {
    'GtsMediaTestCases': 4,
    _ALL: 4,
    # Even though collect tests doesn't run very long, it must be the very first
    # job executed inside of the suite. Hence it is the only 'LENGTHY' test.
    _COLLECT: 5,  # LENGTHY
}

# Enabling --logcat-on-failure can extend total run time significantly if
# individual tests finish in the order of 10ms or less (b/118836700). Specify
# modules here to not enable the flag.
_DISABLE_LOGCAT_ON_FAILURE = set([])
_EXTRA_MODULES = {}
_PUBLIC_EXTRA_MODULES = {}
_EXTRA_COMMANDLINE = {}
_EXTRA_ATTRIBUTES = {
    'tradefed-run-collect-tests-only-internal': ['suite:arc-gts'],
}


def get_tradefed_build(line):
    """Gets the build of Android GTS from tradefed.

    @param line Tradefed identification output on startup.
    @return Tradefed GTS build. Example: 2813453.
    """
    # Sample string: Android Google Mobile Services (GMS) Test Suite 6.0_r1
    # (4756896)
    m = re.search(r' \((.*)\)', line)
    if m:
        return m.group(1)
    logging.warning('Could not identify build in line "%s".', line)
    return '<unknown>'


def get_tradefed_revision(line):
    """Gets the revision of Android GTS from tradefed.

    @param line Tradefed identification output on startup.
    @return Tradefed GTS revision. Example: 4.1_r2.
    """
    m = re.search(r'Android Google Mobile Services \(GMS\) Test Suite (.*) \(',
                  line)
    if m:
        return m.group(1)
    logging.warning('Could not identify revision in line "%s".', line)
    return None


def get_bundle_revision(filename):
    """Makes an educated guess about the revision.

    In this case we chose to guess by filename, but we could also parse the
    xml files in the module.
    """
    m = re.search(r'(?<=gts-)(.*)-linux', filename)
    if m is not None:
        return m.group(1)
    return None


def get_extension(module, revision, public=False):
    """Defines a unique string.

    We follow the CTS naming scheme, but there is currently no need to break out
    the ABI as GTS does it all at once by default.
    @param module: GTS module which will be tested in the control file. If 'all'
                   is specified, the control file will runs all the tests.
    @param public: boolean variable to specify whether or not the bundle is from
                   public source or not.
    @return string: unique string for specific tests. If public=True or
                    module=all, then the string is "<module>",
                    otherwise, the unique string is "<revision>.<module>".
    """
    if public:
        return '%s' % (module)
    else:
        return '%s.%s' % (revision, module)


def get_doc(modules, is_public):
    """Defines the control file DOC string."""
    if not modules.intersection(get_collect_modules(is_public)):
        # Generate per-module DOC
        doc = ('Run module %s of the '
               'Android Google Test Suite (GTS) in '
               'the ARC++ container.' % (', '.join(sorted(list(modules)))))
    else:
        doc = ('Run all of the '
               'Android Google Test Suite (GTS) in '
               'the ARC++ container.')

    return doc


def get_controlfile_name(module, revision, public=False):
    """Defines the control file name.

    @param module: GTS module which will be tested in the control file. If 'all'
                   is specified, the control file will runs all the tests.
    @param public: boolean variable to specify whether or not the bundle is from
                   public source or not.
    @return string: control file for specific tests. If public=True or
                    module=all, then the name will be "control.<module>",
                    otherwise, the name will be
                    "control.<revision>.<module>".
    """
    return 'control.%s' % get_extension(module, revision, public)


def get_sync_count(_modules, _is_public):
    return 1


def get_suites(modules, is_public):
    """Defines the suites associated with a module.

    @param module: GTS module which will be tested in the control file. If 'all'
                   is specified, the control file will runs all the tests.
    # TODO(ihf): Make this work with the "all" and "collect" generation,
    # which currently bypass this function.
    """
    if is_public:
        # On moblab everything runs in the same suite.
        return ['suite:gts']

    # As this is not called for the "all" runs we can safely assume that each
    # module runs in suite:arc-gts.
    suites = ['suite:arc-gts']
    for module in modules:
        if module in get_collect_modules(is_public):
            # We collect all tests both in arc-gts and arc-gts-qual as both have
            # a chance to be complete (and used for submission).
            suites += ['suite:arc-gts-qual']
        if module in _EXTRA_ATTRIBUTES:
            # Special cases come with their own suite definitions.
            suites += _EXTRA_ATTRIBUTES[module]
        if module in _SMOKE:
            # Handle VMTest by adding a few jobs to suite:smoke.
            suites += ['suite:smoke']
        # One or two modules hould be in suite:bvt-arc to cover CQ/PFQ. A few
        # spare/fast modules can run in suite:bvt-perbuild in case we need a
        # replacement for the module in suite:bvt-arc (integration test for
        # cheets_GTS only, not a correctness test for GTS content).
        if module in _BVT_ARC:
            suites += ['suite:bvt-arc']
        if module in _BVT_PERBUILD:
            suites += ['suite:bvt-perbuild']
    return sorted(list(set(suites)))


def get_dependencies(modules, is_public):
    """Defines lab dependencies needed to schedule a module.

    @param module: GTS module which will be tested in the control file. If 'all'
                   is specified, the control file will runs all the tests.
    @param is_public: boolean variable to specify whether or not the bundle is
                      from public source or not.
    """
    return 'arc'


def get_job_retries(modules, is_public):
    """Define the number of job retries associated with a module.

    @param module: GTS module which will be tested in the control file. If a
                   special module is specified, the control file will runs all
                   the tests without retry.
    """
    if is_public:
        retries = 2
    else:
        retries = 1  # 0 is NO job retries, 1 is one retry etc.
    for module in modules:
        # We don't want job retries for module collection or special cases.
        if module in get_collect_modules(is_public):
            retries = 0
    return retries


def get_max_retries(modules, suites, is_public):
    """Partners experiance issues where some modules are flaky and require more

       retries.  Calculate the retry number per module on moblab.
    @param module: GTS module which will be tested in the control file.
    """
    retry = -1
    if is_public:
        retry = 2
        # In moblab at partners we may need many more retries than in lab.
        for module in modules:
            if module in _PUBLIC_MODULE_RETRY_COUNT:
                retry = max(retry, _PUBLIC_MODULE_RETRY_COUNT[module])
    else:
        # See if we have any special values for the module, chose the largest.
        for module in modules:
            if module in _GTS_MAX_RETRIES:
                retry = max(retry, _GTS_MAX_RETRIES[module])

    # Ugly overrides.
    for module in modules:
        # In bvt we don't want to hold the CQ/PFQ too long.
        if ('suite:bvt-arc' in suites or 'suite:bvt-perbuild' in suites):
            retry = 2
        # During qualification we want at least 9 retries, possibly more.
        if 'suite:arc-gts-qual' in suites:
            retry = max(retry, 9)
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

    @param modules: List of GTS modules to be tested by the control file.
    """
    for module in modules:
        if module in get_collect_modules(is_public):
            # Both arm, x86 tests results normally is below 100MB.
            # 500MB should be sufficient for GTS tests and dump logs for
            # android-gts.
            return 500 * 1024
    # Individual module normal produces less results than all modules, which
    # is ranging from 4MB to 50MB.
    # 300MB should be sufficient to handle all the cases.
    return 300 * 1024


def get_extra_args(modules, is_public):
    """Generate a list of extra arguments to pass to the test.

    Some params are specific to a particular module, particular mode or
    combination of both, generate a list of arguments to pass into the template.

    @param modules: List of GTS modules to be tested by the control file.
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

    @param module: GTS module which will be tested in the control file. If 'all'
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

    @param module: GTS module which will be tested in the control file.

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


def get_authkey(is_public):
    if is_public:
        # TODO(haddowk, kinaba): fill the partner authkey file
        return None
    return 'gs://chromeos-arc-images/cts/bundle/gts-arc.json'


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
    cmd = ['run', 'commandAndExit', 'retry' if retry else 'gts']
    special_cmd = _get_special_command_line(modules, is_public)
    if special_cmd:
        cmd.extend(special_cmd)
    # We run each module with its own --include-filter command/option.
    # https://source.android.com/compatibility/cts/run
    elif modules and not retry:
        for module in sorted(modules):
            cmd += ['--include-filter', module]
    # We handle media download ourselves in the lab, as lazy as possible.
    cmd.append('--ignore-business-logic-failure')
    if retry:
        cmd.append('--retry')
        cmd.append('{session_id}')
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
    if 'suite:arc-gts-qual' in suites and not (_COLLECT in modules or
                                               _PUBLIC_COLLECT in modules):
        return int(3600 * _QUAL_TIMEOUT)

    timeout = 0
    # First module gets 1h (standard), all other half hour extra (heuristic).
    delta = 3600
    for module in modules:
        # Modules that run very long are encoded here.
        if module in _GTS_TIMEOUT:
            timeout += int(3600 * _GTS_TIMEOUT[module])
        else:
            timeout += delta
            delta = 1800
    return timeout


def get_controlfile_content(combined,
                            modules,
                            revision,
                            build,
                            uri,
                            suites=None,
                            is_public=False):
    """Returns the text inside of a control file.

    @param combined: name to use for this combination of modules.
    @param modules: list of GTS modules which will be tested in the control
                   file. If 'all' is specified, the control file will runs
                   all the tests.
    """
    # We tag results with full revision now to get result directories containing
    # the revision. This fits stainless/ better.
    tag = '%s' % get_extension(combined, revision, is_public)
    # For test_that the NAME should be the same as for the control file name.
    # We could try some trickery here to get shorter extensions for a default
    # suite/ARM. But with the monthly uprevs this will quickly get confusing.
    name = 'cheets_GTS.%s' % tag
    if not suites:
        suites = get_suites(modules, is_public)
    attributes = ', '.join(suites)
    uri = None if is_public else uri
    # cheets_GTS internal retries limited due to time constraints on cq.
    target_module = None
    if combined not in get_collect_modules(is_public):
        target_module = combined
    for target, m in get_extra_modules_dict(is_public).items():
        if combined in m:
            target_module = target
    return _CONTROLFILE_TEMPLATE.render(
        name=name,
        attributes=attributes,
        dependencies=get_dependencies(modules, is_public),
        job_retries=get_job_retries(modules, is_public),
        max_result_size_kb=get_max_result_size_kb(modules, is_public),
        revision=revision,
        build=build,
        tag=tag,
        uri=uri,
        DOC=get_doc(modules, is_public),
        max_retries=get_max_retries(modules, suites, is_public),
        timeout=calculate_timeout(modules, suites, is_public),
        run_template=get_run_template(modules, is_public),
        retry_template=get_retry_template(modules, is_public),
        target_module=target_module,
        target_plan=None,
        test_length=get_test_length(modules),
        priority=get_test_priority(modules, is_public),
        extra_args=get_extra_args(modules, is_public),
        authkey=get_authkey(is_public),
        sync_count=get_sync_count(modules, is_public))


def get_tradefed_data(path, is_public):
    """Queries tradefed to provide us with a list of modules.

    Notice that the parsing gets broken at times with major new GTS drops.
    """
    tradefed = os.path.join(path, 'android-gts/tools/gts-tradefed')
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
    while not (line.startswith('vm-tests-tf') or line.startswith('Saved log')):
        line = p.stdout.readline().strip()
        # Android Compatibility Test Suite 7.0 (3423912)
        if line.startswith('Android Google '):
            logging.info('Unpacking: %s.', line)
            build = get_tradefed_build(line)
            revision = get_tradefed_revision(line)
        elif line.startswith('Gts'):
            modules.append(line)
        elif line.startswith('Saved log'):
            break
        elif line.isspace or line.startswith('Use "help"'):
            pass
        else:
            logging.warning('Ignoring "%s"', line)
    p.kill()
    p.wait()
    for module in get_modules_to_remove(is_public):
        modules.remove(module)
    return modules, build, revision


# GTS is never truly public, but we consider the version for partners as such.
def download(uri, destination, _is_public):
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
    Example: GtsDebugTestCases -> GtsDebug.
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
    'GtsVoice' -> ['GtsVoiceInteractionTestCases', 'GtsVoiceSettingsTestCases']
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
        # slightly strange combination of having GtsDpiTestCases1/2 inside of
        # GtsDpiTestCases (now just GtsDpi to make it clearer there are several
        # modules in this control file).
        if len(d[key]) > 1:
            prefix = re.sub('TestCases$', '', prefix)
            prefix = re.sub('Tests$', '', prefix)
        combined[prefix] = set(d[key])
        # Sanity check.
        print key, len(d[key]), prefix, d[key]
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


def write_controlfile(name, modules, revision, build, uri, suites, is_public):
    """Write a single control file."""
    filename = get_controlfile_name(name, revision, is_public)
    content = get_controlfile_content(name, modules, revision, build, uri,
                                      suites, is_public)
    with open(filename, 'w') as f:
        f.write(content)


def write_moblab_controlfiles(modules, revision, build, uri, is_public):
    """Write all control files for moblab.

    Nothing gets combined.

    Moblab uses one module per job. In some cases like Deqp which can run super
    long it even creates several jobs per module. Moblab can do this as it has
    less relative overhead spinning up jobs than the lab.
    """
    for module in modules:
        write_controlfile(module, set([module]), revision, build, uri,
                          ['suite:gts'], is_public)


def write_regression_controlfiles(modules, revision, build, uri, is_public):
    """Write all control files for stainless/ToT regression lab coverage.

    Regression coverage on tot currently relies heavily on watching stainless
    dashboard and sponge. So instead of running everything in a single run
    we split GTS into many jobs. It used to be one job per module, but that
    became too much in P (more than 300 per ABI). Instead we combine modules
    with similar names and run these in the same job (alphabetically).
    """
    combined = combine_modules_by_common_word(set(modules))
    for key in combined:
        write_controlfile(key, combined[key], revision, build, uri, None,
                          is_public)


def write_qualification_controlfiles(modules, revision, build, uri, is_public):
    """Write all control files to run "all" tests for qualification.

    Qualification was performed on N by running all tests using tradefed
    sharding (specifying SYNC_COUNT=2) in the control files. In skylab
    this is currently not implemented, so we fall back to autotest sharding
    all GTS tests into 1-2 hand chosen shards.
    """
    combined = combine_modules_by_bookmark(set(modules))
    for key in combined:
        write_controlfile('all.' + key, combined[key], revision, build,
                          uri, ['suite:arc-gts-qual'], is_public)


def write_collect_controlfiles(_modules, revision, build, uri, is_public):
    """Write all control files for test collection used as reference to

    compute completeness (missing tests) on the CTS dashboard.
    """
    suites = ['suite:arc-gts', 'suite:arc-gts-qual']
    if is_public:
        suites = ['suite:gts']
    for module in get_collect_modules(is_public):
        write_controlfile(module, set([module]), revision, build, uri, suites,
                          is_public)


def main(uris, is_public):
    """Downloads each module in |uris| and generates control files."""
    for uri in uris:
        # Get tradefed data by downloading & unzipping the files
        with TemporaryDirectory(prefix='gts-android_') as tmp:
            logging.info('Downloading to %s.', tmp)
            download(uri, tmp, is_public)
            bundle = os.path.join(tmp, os.path.basename(uri))
            logging.info('Extracting %s.', bundle)
            unzip(bundle, tmp)
            modules, build, revision = get_tradefed_data(tmp, is_public)
            if not revision:
                raise Exception('Could not determine revision.')

            logging.info('Writing all control files.')
            if is_public:
                write_moblab_controlfiles(modules, revision, build, uri,
                                          is_public)
            else:
                write_regression_controlfiles(modules, revision, build, uri,
                                              is_public)
                write_qualification_controlfiles(modules, revision, build, uri,
                                                 is_public)
            write_collect_controlfiles(modules, revision, build, uri, is_public)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(
        description='Create control files for a GTS bundle on GS.',
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        'uris',
        nargs='+',
        help='List of Google Storage URIs to GTS bundles. Example:\n'
        'gs://chromeos-arc-images/cts/bundle/P/android-gts-4756896.zip')
    parser.add_argument(
        '--is_public',
        dest='is_public',
        default=False,
        action='store_true',
        help='Generate the public control files for GTS, default generate'
        ' the internal control files')
    args = parser.parse_args()
    main(args.uris, args.is_public)
