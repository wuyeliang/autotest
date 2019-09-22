# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function

import logging
import os
import re
import shutil
import StringIO

from contextlib import contextmanager

from autotest_lib.client.common_lib import error
from autotest_lib.server import test
from autotest_lib.server import utils
from autotest_lib.site_utils import test_runner_utils


TELEMETRY_TIMEOUT_MINS = 60
WAIT_FOR_CMD_TIMEOUT_SECS = 60
DUT_COMMON_SSH_OPTIONS = ['-o StrictHostKeyChecking=no',
                          '-o UserKnownHostsFile=/dev/null',
                          '-o BatchMode=yes',
                          '-o ConnectTimeout=30',
                          '-o ServerAliveInterval=900',
                          '-o ServerAliveCountMax=3',
                          '-o ConnectionAttempts=4',
                          '-o Protocol=2']
DUT_SCP_OPTIONS = ' '.join(DUT_COMMON_SSH_OPTIONS)

CHROME_SRC_ROOT = '/var/cache/chromeos-cache/distfiles/target/'
CLIENT_CHROME_ROOT = '/usr/local/telemetry/src'
RUN_BENCHMARK = 'tools/perf/run_benchmark'

RSA_KEY = '-i %s' % test_runner_utils.TEST_KEY_PATH
DUT_CHROME_RESULTS_DIR = '/usr/local/telemetry/src/tools/perf'

TURBOSTAT_LOG = 'turbostat.log'
CPUSTATS_LOG = 'cpustats.log'
CPUINFO_LOG = 'cpuinfo.log'
TOP_LOG = 'top.log'

# Result Statuses
SUCCESS_STATUS = 'SUCCESS'
WARNING_STATUS = 'WARNING'
FAILED_STATUS = 'FAILED'

# Regex for the RESULT output lines understood by chrome buildbot.
# Keep in sync with
# chromium/tools/build/scripts/slave/performance_log_processor.py.
RESULTS_REGEX = re.compile(r'(?P<IMPORTANT>\*)?RESULT '
                           r'(?P<GRAPH>[^:]*): (?P<TRACE>[^=]*)= '
                           r'(?P<VALUE>[\{\[]?[-\d\., ]+[\}\]]?)('
                           r' ?(?P<UNITS>.+))?')
HISTOGRAM_REGEX = re.compile(r'(?P<IMPORTANT>\*)?HISTOGRAM '
                             r'(?P<GRAPH>[^:]*): (?P<TRACE>[^=]*)= '
                             r'(?P<VALUE_JSON>{.*})(?P<UNITS>.+)?')


CHARTJSON_ALLOWLIST = ('loading.desktop')

def _find_chrome_root_dir():
  # Look for chrome source root, either externally mounted, or inside
  # the chroot.  Prefer chrome-src-internal source tree to chrome-src.
  sources_list = ('chrome-src-internal', 'chrome-src')

  dir_list = [os.path.join(CHROME_SRC_ROOT, x) for x in sources_list]
  if 'CHROME_ROOT' in os.environ:
    dir_list.insert(0, os.environ['CHROME_ROOT'])

  for dir in dir_list:
    if os.path.exists(dir):
      chrome_root_dir = dir
      break
  else:
    raise error.TestError('Chrome source directory not found.')

  logging.info('Using Chrome source tree at %s', chrome_root_dir)
  return os.path.join(chrome_root_dir, 'src')


def _ensure_deps(dut, test_name):
  """Ensure the dependencies are locally available on DUT.

  @param dut: The autotest host object representing DUT.
  @param test_name: Name of the telemetry test.
  """
  # Get DEPs using host's telemetry.
  chrome_root_dir = _find_chrome_root_dir()
  format_string = ('python %s/tools/perf/fetch_benchmark_deps.py %s')
  command = format_string % (chrome_root_dir, test_name)
  logging.info('Getting DEPs: %s', command)
  stdout = StringIO.StringIO()
  stderr = StringIO.StringIO()
  try:
    utils.run(command, stdout_tee=stdout, stderr_tee=stderr)

  except error.CmdError:
    logging.debug('Error occurred getting DEPs: %s\n %s\n',
                  stdout.getvalue(), stderr.getvalue())
    raise error.TestFail('Error occurred while getting DEPs.')

  # Download DEPs to DUT.
  # send_file() relies on rsync over ssh. Couldn't be better.
  stdout_str = stdout.getvalue()
  stdout.close()
  stderr.close()
  for dep in stdout_str.split():
    src = os.path.join(chrome_root_dir, dep)
    dst = os.path.join(CLIENT_CHROME_ROOT, dep)
    if not os.path.isfile(src):
      raise error.TestFail('Error occurred while saving DEPs.')
    logging.info('Copying: %s -> %s', src, dst)
    try:
      dut.send_file(src, dst)
    except:
      raise error.TestFail('Error occurred while sending DEPs to dut.\n')


class telemetry_Crosperf(test.test):
  """Run one or more telemetry benchmarks under the crosperf script."""
  version = 1

  def scp_telemetry_results(self,
                            client_ip,
                            dut,
                            file,
                            host_dir,
                            ignore_status=False):
    """Copy telemetry results from dut.

    @param client_ip: The ip address of the DUT
    @param dut: The autotest host object representing DUT.
    @param file: The file to copy from DUT.
    @param host_dir: The directory on host to put the file .

    @returns status code for scp command.
    """
    cmd = []
    src = ('root@%s:%s' %
           (dut.hostname if dut else client_ip,
            file))
    cmd.extend(['scp', DUT_SCP_OPTIONS, RSA_KEY, '-v',
                src, host_dir])
    command = ' '.join(cmd)

    logging.debug('Retrieving Results: %s', command)
    try:
      result = utils.run(
          command,
          timeout=WAIT_FOR_CMD_TIMEOUT_SECS,
          ignore_status=ignore_status)
      exit_code = result.exit_status
    except Exception as e:
      logging.error('Failed to retrieve results: %s', e)
      raise

    logging.debug('command return value: %d', exit_code)
    return exit_code

  @contextmanager
  def no_background(self, *_args):
    """Background stub."""
    yield

  @contextmanager
  def run_in_background_with_log(self, cmd, dut, log_path):
    """Get cpustats periodically in background.

    NOTE:
      No error handling, exception or error report
      if command fails to run in background.
      Command failure is silenced.
    """
    logging.info('Running in background:\n%s', cmd)
    pid = dut.run_background(cmd)
    try:
      # TODO(denik): replace with more reliable way
      # to check run success/failure in background.
      # Wait some time before checking the process.
      check = dut.run('sleep 5; kill -0 %s' % pid, ignore_status=True)
      if check.exit_status != 0:
        # command wasn't started correctly
        logging.error(
            "Background command wasn't started correctly.\n"
            'Command:\n%s', cmd)
        pid = ''
        yield
        return

      logging.info('Background process started successfully, pid %s', pid)
      yield

    finally:
      if pid:
        # Stop background processes.
        logging.info('Killing background process, pid %s', pid)
        # Kill the process blindly. OK if it's already gone.
        # There is an issue when underlying child processes stay alive while
        # the parent master process is killed.
        # The solution is to kill the chain of processes via process group
        # id.
        dut.run('pgid=$(cat /proc/%s/stat | cut -d")" -f2 | cut -d" " -f4)'
                ' && kill -- -$pgid 2>/dev/null' % pid, ignore_status=True)

        # Copy the results to results directory with silenced failure.
        scp_res = self.scp_telemetry_results(
            '', dut, log_path, self.resultsdir, ignore_status=True)
        if scp_res:
          logging.error(
              'scp of cpuinfo logs failed '
              'with error %d.', scp_res)

  def run_cpustats_in_background(self, dut, log_name):
    """Run command to collect CPU stats in background."""

    log_path = '/tmp/%s' % log_name
    cpu_stats_cmd = (
        'cpulog=%s; '
        'rm -f ${cpulog}; '
        # Stop after 720*0.5min=6hours if not killed at clean-up phase.
        'for i in {1..720} ; do '
        # Collect current CPU frequency on all cores and thermal data.
        ' paste -d" " '
        '   <(ls /sys/devices/system/cpu/cpu*/cpufreq/cpuinfo_cur_freq) '
        '   <(cat /sys/devices/system/cpu/cpu*/cpufreq/cpuinfo_cur_freq) '
        '  >> ${cpulog} || break; ' # exit loop if fails.
        ' paste -d" "'
        '   <(cat /sys/class/thermal/thermal_zone*/type)'
        '   <(cat /sys/class/thermal/thermal_zone*/temp)'
        # Filter in thermal data from only CPU-related sources.
        '  | grep -iE "soc|cpu|pkg|big|little" >> ${cpulog} || break; '
        # Repeat every 30 sec.
        ' sleep 30; '
        'done;'
    ) % log_path

    return self.run_in_background_with_log(cpu_stats_cmd, dut, log_path)

  def run_top_in_background(self, dut, log_name, interval_in_sec):
    """Run top in background."""

    log_path = '/tmp/%s' % log_name
    top_cmd = (
        # Run top in batch mode with specified interval and filter out top
        # system summary and processes not consuming %CPU.
        # Output of each iteration is separated by a blank line.
        'HOME=/usr/local COLUMNS=128 top -bi -d%.1f'
        ' | grep -E "^[ 0-9]|^$" > %s;'
    ) % (interval_in_sec, log_path)

    return self.run_in_background_with_log(top_cmd, dut, log_path)

  def run_turbostat_in_background(self, dut, log_name):
    """Run turbostat in background."""

    log_path = '/tmp/%s' % log_name
    turbostat_cmd = (
        'nohup turbostat --quiet --interval 10 '
        '--show=CPU,Bzy_MHz,Avg_MHz,TSC_MHz,Busy%%,IRQ,CoreTmp '
        '1> %s'
    ) % log_path

    return self.run_in_background_with_log(turbostat_cmd, dut, log_path)

  def run_cpuinfo(self, dut, log_name):
    """Collect CPU info of "dut" into "log_name" file."""

    cpuinfo_cmd = (
        'for cpunum in '
        "   $(awk '/^processor/ { print $NF ; }' /proc/cpuinfo ) ; do "
        ' for i in `ls -d /sys/devices/system/cpu/cpu"${cpunum}"/cpufreq/'
        '{cpuinfo_cur_freq,scaling_*_freq,scaling_governor} '
        '     2>/dev/null` ; do '
        '  paste -d" " <(echo "${i}") <(cat "${i}"); '
        ' done;'
        'done;'
        'for cpudata in'
        '  /sys/devices/system/cpu/intel_pstate/no_turbo'
        '  /sys/devices/system/cpu/online; do '
        ' if [[ -e "${cpudata}" ]] ; then '
        '  paste <(echo "${cpudata}") <(cat "${cpudata}"); '
        ' fi; '
        'done; '
        # Adding thermal data to the log.
        'paste -d" "'
        '  <(cat /sys/class/thermal/thermal_zone*/type)'
        '  <(cat /sys/class/thermal/thermal_zone*/temp)')

    # Get CPUInfo at the end of the test.
    logging.info('Get cpuinfo: %s', cpuinfo_cmd)
    with open(os.path.join(self.resultsdir, log_name), 'w') as cpu_log_file:
      # Handle command failure gracefully.
      res = dut.run(
          cpuinfo_cmd, stdout_tee=cpu_log_file, ignore_status=True)
      if res.exit_status:
        logging.error('Get cpuinfo command failed with %d.',
                      res.exit_status)

  def run_once(self, args, client_ip='', dut=None):
    """Run a single telemetry test.

    @param args: A dictionary of the arguments that were passed
            to this test.
    @param client_ip: The ip address of the DUT
    @param dut: The autotest host object representing DUT.

    @returns A TelemetryResult instance with the results of this execution.
    """
    test_name = args.get('test', '')
    test_args = args.get('test_args', '')
    profiler_args = args.get('profiler_args', '')

    output_format = '--output-format=histograms'
    if test_name in CHARTJSON_ALLOWLIST:
      output_format += ' --output-format=chartjson'
    # Decide whether the test will run locally or by a remote server.
    if args.get('run_local', 'false').lower() == 'true':
      # The telemetry scripts will run on DUT.
      _ensure_deps(dut, test_name)
      format_string = ('python %s --browser=system '
                       '%s %s %s')
      command = format_string % (
          os.path.join(
              CLIENT_CHROME_ROOT, RUN_BENCHMARK),
          output_format, test_args, test_name)
      runner = dut
    else:
      # The telemetry scripts will run on server.
      format_string = ('python %s --browser=cros-chrome --remote=%s '
                       '--output-dir="%s" '
                       '%s %s %s')
      command = format_string % (os.path.join(_find_chrome_root_dir(),
                                              RUN_BENCHMARK), client_ip,
                                 self.resultsdir,
                                 output_format, test_args, test_name)
      runner = utils

    # Run the test. And collect profile if needed.
    stdout = StringIO.StringIO()
    stderr = StringIO.StringIO()
    try:
      # If profiler_args specified, we want to add several more options
      # to the command so that run_benchmark will collect system wide
      # profiles.
      if profiler_args:
        command += ' --interval-profiling-period=story_run' \
            ' --interval-profiling-target=system_wide' \
            ' --interval-profiler-options="%s"' \
            % (profiler_args)

      run_cpuinfo = self.run_cpustats_in_background if dut \
          else self.no_background
      run_turbostat = self.run_turbostat_in_background if (
          dut and args.get('turbostat', 'False') == 'True') \
              else self.no_background
      top_interval = float(args.get('top_interval', '0'))
      run_top = self.run_top_in_background if (
          dut and top_interval > 0) \
              else self.no_background

      # FIXME(denik): replace with ExitStack.
      with run_cpuinfo(dut, CPUSTATS_LOG) as _cpu_cm, \
          run_turbostat(dut, TURBOSTAT_LOG) as _turbo_cm, \
          run_top(dut, TOP_LOG, top_interval) as _top_cm:

        logging.info('CMD: %s', command)
        result = runner.run(
            command,
            stdout_tee=stdout,
            stderr_tee=stderr,
            timeout=TELEMETRY_TIMEOUT_MINS * 60)
        exit_code = result.exit_status
        if exit_code != 0:
          raise RuntimeError

    except RuntimeError:
      logging.debug('Telemetry test failed.')
      raise error.TestFail('Test failed while executing telemetry test.')
    except error.CmdError as e:
      logging.debug('Error occurred executing telemetry.')
      exit_code = e.result_obj.exit_status
      raise error.TestFail('An error occurred while executing '
                           'telemetry test.')
    except:
      logging.debug('Telemetry aborted with unknown error.')
      exit_code = -1
      raise
    finally:
      stdout_str = stdout.getvalue()
      stderr_str = stderr.getvalue()
      stdout.close()
      stderr.close()
      logging.info(
          'Telemetry completed with exit code: %d.'
          '\nstdout:%s\nstderr:%s', exit_code, stdout_str, stderr_str)

      if dut:
        self.run_cpuinfo(dut, CPUINFO_LOG)

    # Copy the results-chart.json and histograms.json file into
    # the test_that results directory, if necessary.
    if args.get('run_local', 'false').lower() == 'true':
      if test_name in CHARTJSON_ALLOWLIST:
        result = self.scp_telemetry_results(
            client_ip, dut,
            os.path.join(DUT_CHROME_RESULTS_DIR, 'results-chart.json'),
            self.resultsdir)
      result = self.scp_telemetry_results(
          client_ip, dut,
          os.path.join(DUT_CHROME_RESULTS_DIR, 'histograms.json'),
          self.resultsdir)
    else:
      if test_name in CHARTJSON_ALLOWLIST:
        filepath = os.path.join(self.resultsdir, 'results-chart.json')
        if not os.path.exists(filepath):
          exit_code = -1
          raise RuntimeError('Missing results file: %s' % filepath)
      filepath = os.path.join(self.resultsdir, 'histograms.json')
      if not os.path.exists(filepath):
        exit_code = -1
        raise RuntimeError('Missing results file: %s' % filepath)

    # Copy the perf data file into the test_that profiling directory,
    # if necessary. It always comes from DUT.
    if profiler_args:
      filepath = os.path.join(self.resultsdir, 'artifacts')
      if not os.path.isabs(filepath):
        raise RuntimeError('Expected absolute path of '
                           'arfifacts: %s' % filepath)
      perf_exist = False
      for root, _dirs, files in os.walk(filepath):
        for f in files:
          if f.endswith('.perf.data'):
            perf_exist = True
            src_file = os.path.join(root, f)
            # results-cache.py in crosperf supports multiple
            # perf.data files, but only if they are named exactly
            # so. Therefore, create a subdir for each perf.data
            # file.
            dst_dir = os.path.join(self.profdir,
                                   ''.join(f.split('.')[:-2]))
            os.makedirs(dst_dir)
            dst_file = os.path.join(dst_dir, 'perf.data')
            shutil.copyfile(src_file, dst_file)
      if not perf_exist:
        exit_code = -1
        raise error.TestFail('Error: No profiles collected, test may '
                             'not run correctly.')

    return result
