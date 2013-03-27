# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, shutil, re, logging

from autotest_lib.client.common_lib import log
from autotest_lib.client.common_lib import error, utils, global_config
from autotest_lib.client.bin import base_sysinfo
from autotest_lib.client.cros import constants

get_value = global_config.global_config.get_config_value
collect_corefiles = get_value('CLIENT', 'collect_corefiles',
                              type=bool, default=True)


logfile = base_sysinfo.logfile
command = base_sysinfo.command


class logdir(base_sysinfo.loggable):
    def __init__(self, directory, additional_exclude=None):
        super(logdir, self).__init__(directory, log_in_keyval=False)
        self.dir = directory
        self.additional_exclude = additional_exclude


    def __repr__(self):
        return "site_sysinfo.logdir(%r, %s)" % (self.dir,
                                                self.additional_exclude)


    def __eq__(self, other):
        if isinstance(other, logdir):
            return (self.dir == other.dir and
                    self.additional_exclude == other.additional_exclude)
        elif isinstance(other, base_sysinfo.loggable):
            return False
        return NotImplemented


    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result


    def __hash__(self):
        return hash(self.dir) + hash(self.additional_exclude)


    def run(self, log_dir):
        if os.path.exists(self.dir):
            parent_dir = os.path.dirname(self.dir)
            utils.system("mkdir -p %s%s" % (log_dir, parent_dir))
            # Take source permissions and add ugo+r so files are accessible via
            # archive server.
            additional_exclude_str = ""
            if self.additional_exclude:
                additional_exclude_str = "--exclude=" + self.additional_exclude

            utils.system("rsync --no-perms --chmod=ugo+r -a --exclude=autoserv*"
                         " %s %s %s%s" % (additional_exclude_str, self.dir,
                                          log_dir, parent_dir))


class file_stat(object):
    """Store the file size and inode, used for retrieving new data in file."""
    def __init__(self, file_path):
        """Collect the size and inode information of a file.

        @param file_path: full path to the file.

        """
        stat = os.stat(file_path)
        # Start size of the file, skip that amount of bytes when do diff.
        self.st_size = stat.st_size
        # inode of the file. If inode is changed, treat this as a new file and
        # copy the whole file.
        self.st_ino = stat.st_ino


class diffable_logdir(logdir):
    """Represents a log directory that only new content will be copied.

    An instance of this class should be added in both
    before_iteration_loggables and after_iteration_loggables. This is to
    guarantee the file status information is collected when run method is
    called in before_iteration_loggables, and diff is executed when run
    method is called in after_iteration_loggables.

    """
    def __init__(self, directory, additional_exclude=None,
                 keep_file_hierarchy=True, append_diff_in_name=True):
        """
        Constructor of a diffable_logdir instance.

        @param directory: directory to be diffed after an iteration finished.
        @param additional_exclude: additional dir to be excluded, not used.
        @param keep_file_hierarchy: True if need to preserve full path, e.g.,
            sysinfo/var/log/sysstat, v.s. sysinfo/sysstat if it's False.
        @param append_diff_in_name: True if you want to append '_diff' to the
            folder name to indicate it's a diff, e.g., var/log_diff. Option
            keep_file_hierarchy must be True for this to take effect.

        """
        super(diffable_logdir, self).__init__(directory, additional_exclude)
        self.additional_exclude = additional_exclude
        self.keep_file_hierarchy = keep_file_hierarchy
        self.append_diff_in_name = append_diff_in_name
        # Init dictionary to store all file status for files in the directory.
        self._log_stats = {}


    def _get_init_status_of_src_dir(self, src_dir):
        """Get initial status of files in src_dir folder.

        @param src_dir: directory to be diff-ed.

        """
        # Dictionary used to store the initial status of files in src_dir.
        for file_path in self._get_all_files(src_dir):
            self._log_stats[file_path] = file_stat(file_path)
        self.file_stats_collected = True


    def _get_all_files(self, path):
        """Iterate through files in given path including subdirectories.

        @param path: root directory.
        @return: an iterator that iterates through all files in given path
            including subdirectories.

        """
        if not os.path.exists(path):
            yield []
        for root, dirs, files in os.walk(path):
            for f in files:
                if f.startswith('autoserv'):
                    continue
                yield os.path.join(root, f)


    def _copy_new_data_in_file(self, file_path, src_dir, dest_dir):
        """Copy all new data in a file to target directory.

        @param file_path: full path to the file to be copied.
        @param src_dir: source directory to do the diff.
        @param dest_dir: target directory to store new data of src_dir.

        """
        bytes_to_skip = 0
        if self._log_stats.has_key(file_path):
            prev_stat = self._log_stats[file_path]
            new_stat = os.stat(file_path)
            if new_stat.st_ino == prev_stat.st_ino:
                bytes_to_skip = prev_stat.st_size
            if new_stat.st_size == bytes_to_skip:
                return
            elif new_stat.st_size < prev_stat.st_size:
                # File is modified to a smaller size, copy whole file.
                bytes_to_skip = 0
        try:
            with open(file_path, 'r') as in_log:
                if bytes_to_skip > 0:
                    in_log.seek(bytes_to_skip)
                # Skip src_dir in path, e.g., src_dir/[sub_dir]/file_name.
                target_path = os.path.join(dest_dir,
                                           os.path.relpath(file_path, src_dir))
                target_dir = os.path.dirname(target_path)
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir)
                with open(target_path, "w") as out_log:
                    out_log.write(in_log.read())
        except IOError as e:
            logging.error('Diff %s failed with error: %s', file_path, e)


    def _log_diff(self, src_dir, dest_dir):
        """Log all of the new data in src_dir to dest_dir.

        @param src_dir: source directory to do the diff.
        @param dest_dir: target directory to store new data of src_dir.

        """
        if self.keep_file_hierarchy:
            dir = src_dir.lstrip('/')
            if self.append_diff_in_name:
                dir = dir.rstrip('/') + '_diff'
            dest_dir = os.path.join(dest_dir, dir)

        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)

        for src_file in self._get_all_files(src_dir):
            self._copy_new_data_in_file(src_file, src_dir, dest_dir)


    def run(self, log_dir, collect_init_status=True):
        """Copies new content from self.dir to the destination log_dir.

        @param log_dir: The destination log directory.
        @param collect_init_status: Set to True if run method is called to
            collect the initial status of files.

        """
        if collect_init_status:
            self._get_init_status_of_src_dir(self.dir)
        elif os.path.exists(self.dir):
                self._log_diff(self.dir, log_dir)


class purgeable_logdir(logdir):
    def __init__(self, directory, additional_exclude=None):
        super(purgeable_logdir, self).__init__(directory, additional_exclude)
        self.additional_exclude = additional_exclude

    def run(self, log_dir):
        super(purgeable_logdir, self).run(log_dir)

        if os.path.exists(self.dir):
            utils.system("rm -rf %s/*" % (self.dir))


class site_sysinfo(base_sysinfo.base_sysinfo):
    def __init__(self, job_resultsdir):
        super(site_sysinfo, self).__init__(job_resultsdir)
        crash_exclude_string = None
        if not collect_corefiles:
            crash_exclude_string = "*.core"

        # This is added in before and after_iteration_loggables. When run is
        # called in before_iteration_loggables, it collects file status in
        # the directory. When run is called in after_iteration_loggables, diff
        # is executed.
        diffable_log = diffable_logdir(constants.LOG_DIR)
        self.diffable_loggables = set()
        self.diffable_loggables.add(diffable_log)

        # add in some extra command logging
        self.boot_loggables.add(command("ls -l /boot",
                                        "boot_file_list"))
        self.before_iteration_loggables.add(
            command(constants.BROWSER_EXE + " --version", "chrome_version"))
        self.test_loggables.add(
            purgeable_logdir(
                os.path.join(constants.CRYPTOHOME_MOUNT_PT, "log")))
        # We only want to gather and purge crash reports after the client test
        # runs in case a client test is checking that a crash found at boot
        # (such as a kernel crash) is handled.
        self.after_iteration_loggables.add(
            purgeable_logdir(
                os.path.join(constants.CRYPTOHOME_MOUNT_PT, "crash"),
                additional_exclude=crash_exclude_string))
        self.after_iteration_loggables.add(
            purgeable_logdir(constants.CRASH_DIR,
                             additional_exclude=crash_exclude_string))
        self.test_loggables.add(
            logfile(os.path.join(constants.USER_DATA_DIR,
                                 ".Google/Google Talk Plugin/gtbplugin.log")))
        self.test_loggables.add(purgeable_logdir(
                constants.CRASH_DIR,
                additional_exclude=crash_exclude_string))
        # Collect files under /tmp/crash_reporter, which contain the procfs
        # copy of those crashed processes whose core file didn't get converted
        # into minidump. We need these additional files for post-mortem analysis
        # of the conversion failure.
        self.test_loggables.add(
            purgeable_logdir(constants.CRASH_REPORTER_RESIDUE_DIR))


    @log.log_and_ignore_errors("pre-test sysinfo error:")
    def log_before_each_test(self, test):
        """Logging hook called before a test starts.

        @param test: A test object.
        """
        super(site_sysinfo, self).log_before_each_test(test)

        for log in self.diffable_loggables:
            log.run(log_dir=None, collect_init_status=True)


    @log.log_and_ignore_errors("post-test sysinfo error:")
    def log_after_each_test(self, test):
        """Logging hook called after a test finishs.

        @param test: A test object.
        """
        super(site_sysinfo, self).log_after_each_test(test)

        test_sysinfodir = self._get_sysinfodir(test.outputdir)
        for log in self.diffable_loggables:
            log.run(log_dir=test_sysinfodir, collect_init_status=False)


    def _get_chrome_version(self):
        """Gets the Chrome version number as a string.

        @return The current Chrome version number as a string.  It is specified
            in format "X.X.X.X" if it can be parsed in that format, otherwise
            it is specified as the full output of "chrome --version".

        """
        version_string = utils.system_output(self._CHROME_VERSION_COMMAND)
        match = re.search('\d+\.\d+\.\d+\.\d+', version_string)
        return match.group(0) if match else version_string


    def log_test_keyvals(self, test_sysinfodir):
        keyval = super(site_sysinfo, self).log_test_keyvals(test_sysinfodir)

        lsb_lines = utils.system_output(
            "cat /etc/lsb-release",
            ignore_status=True).splitlines()
        lsb_dict = dict(item.split("=") for item in lsb_lines)

        for lsb_key in lsb_dict.keys():
            # Special handling for build number
            if lsb_key == "CHROMEOS_RELEASE_DESCRIPTION":
                keyval["CHROMEOS_BUILD"] = (
                    lsb_dict[lsb_key].rstrip(")").split(" ")[3])
            keyval[lsb_key] = lsb_dict[lsb_key]

        # return the updated keyvals
        return keyval
