# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import logging
import shutil

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import autotemp, error
from autotest_lib.client.cros.cros_disks import CrosDisksTester
from autotest_lib.client.cros.cros_disks import DefaultFilesystemTestContent
from autotest_lib.client.cros.cros_disks import FilesystemTestDirectory
from autotest_lib.client.cros.cros_disks import FilesystemTestFile
from autotest_lib.client.cros.cros_disks import VirtualFilesystemImage
from collections import deque


def utf8(s):
    return s.encode('utf8')


class CrosDisksArchiveTester(CrosDisksTester):
    """A tester to verify archive support in CrosDisks.
    """

    def __init__(self, test, archive_types):
        super(CrosDisksArchiveTester, self).__init__(test)
        self._data_dir = os.path.join(test.bindir, 'data')
        self._archive_types = archive_types

    def _find_all_files(self, root_dir):
        """Returns all files under a directory and its sub-directories.

           This is a generator that performs a breadth-first-search of
           all files under a specified directory and its sub-directories.

        Args:
            root_dir: The root directory where the search starts from.
        Yields:
            Path of any found file relative to the root directory.
        """
        dirs_to_explore = deque([''])
        while len(dirs_to_explore) > 0:
            current_dir = dirs_to_explore.popleft()
            for path in os.listdir(os.path.join(root_dir, current_dir)):
                expanded_path = os.path.join(root_dir, current_dir, path)
                relative_path = os.path.join(current_dir, path)
                if os.path.isdir(expanded_path):
                    dirs_to_explore.append(relative_path)
                else:
                    yield relative_path

    def _test_archive(self, archive_path, want_content):
        logging.info('Mounting archive %r', archive_path)
        archive_name = os.path.basename(archive_path)

        # Mount archive file via CrosDisks.
        #
        # TODO(crbug.com/996549) Remove '.rar2fs' once old avfsd-based system
        # is removed.
        self.cros_disks.mount(archive_path, '.rar2fs')
        mount_result = self.cros_disks.expect_mount_completion({
                'status':
                0,
                'source_path':
                archive_path,
                'mount_path':
                os.path.join('/media/archive', archive_name),
        })

        mount_path = utf8(mount_result['mount_path'])
        logging.info('Archive mounted at %r', mount_path)

        # Verify the content of the mounted archive file.
        logging.info('Verifying mounted archive contents')
        if not want_content.verify(mount_path):
            raise error.TestFail(
                    'Mounted archive %r does not have expected contents' %
                    archive_name)

        logging.info('Unmounting archive')
        self.cros_disks.unmount(mount_path, [])

    def _test_unicode(self, mount_path):
        # Test RAR V4 with Unicode BMP characters in file and directory
        # names.
        want = [
                FilesystemTestFile(
                        utf8(u'File D79F \uD79F.txt'),
                        utf8(u'Char U+D79F is \uD79F HANGUL SYLLABLE HIC\n')),
                FilesystemTestFile(' Space Oddity ', 'Mind the gap\n'),
                FilesystemTestDirectory('Level 1', [
                        FilesystemTestFile('Empty', ''),
                        FilesystemTestFile('Digits', '0123456789'),
                        FilesystemTestFile('Small', 'Small file\n'),
                        FilesystemTestDirectory('Level 2', [
                                FilesystemTestFile('Big', 'a' * 65536),
                        ]),
                ]),
        ]

        self._test_archive(
                os.path.join(mount_path, 'Format V4.rar'),
                FilesystemTestDirectory('', want))

        # Test RAR V5 with Unicode BMP and non-BMP characters in file
        # and directory names.
        want += [
                FilesystemTestDirectory(
                        utf8(u'Dir 1F601 \U0001F601'), [
                                FilesystemTestFile(
                                        utf8(u'File 1F602 \U0001F602.txt'),
                                        utf8(u'Char U+1F602 is \U0001F602 ' +
                                             u'FACE WITH TEARS OF JOY\n')),
                        ]),
        ]

        self._test_archive(
                os.path.join(mount_path, 'Format V5.rar'),
                FilesystemTestDirectory('', want))

    def _test_multipart(self, mount_path):
        # Test multipart RARs.
        want = FilesystemTestDirectory('', [
                FilesystemTestFile(
                        'Lines', ''.join(
                                ['Line %03i\n' % (i + 1) for i in range(200)]))
        ])

        for archive_name in [
                'Multipart Old Style.rar',
                'Multipart New Style.part01.rar',
                'Multipart New Style.part02.rar',
                'Multipart New Style.part03.rar',
        ]:
            self._test_archive(os.path.join(mount_path, archive_name), want)

    def _test_invalid(self, mount_path):
        for archive_name in [
                'Invalid.rar',
                'Encrypted.rar',
                'Not There.rar',
        ]:
            archive_path = os.path.join(mount_path, archive_name)
            logging.info('Mounting archive %r', archive_path)

            # Mount archive file via CrosDisks.
            #
            # TODO(crbug.com/996549) Remove '.rar2fs' once old avfsd-based
            # system is removed.
            self.cros_disks.mount(archive_path, '.rar2fs')
            mount_result = self.cros_disks.expect_mount_completion({
                    'status':
                    12,
                    'source_path':
                    archive_path,
                    'mount_path':
                    '',
            })

    def _test_nested(self, mount_path):
        archive_name = 'Nested.rar'
        archive_path = os.path.join(mount_path, archive_name)
        logging.info('Mounting archive %r', archive_path)

        # Mount archive file via CrosDisks.
        #
        # TODO(crbug.com/996549) Remove '.rar2fs' once old avfsd-based system
        # is removed.
        self.cros_disks.mount(archive_path, '.rar2fs')
        mount_result = self.cros_disks.expect_mount_completion({
                'status':
                0,
                'source_path':
                archive_path,
                'mount_path':
                os.path.join('/media/archive', archive_name),
        })

        mount_path = utf8(mount_result['mount_path'])
        logging.info('Archive mounted at %r', mount_path)

        self._test_unicode(mount_path)
        self._test_multipart(mount_path)
        self._test_invalid(mount_path)

        logging.info('Unmounting archive')
        self.cros_disks.unmount(mount_path, [])

    def test_archives(self):
        # Create a FAT filesystem containing all our test archive files.
        logging.info('Creating FAT filesystem holding test archive files')
        with VirtualFilesystemImage(
                block_size=1024,
                block_count=65536,
                filesystem_type='vfat',
                mkfs_options=['-F', '32', '-n', 'ARCHIVE']) as image:
            image.format()
            image.mount(options=['sync'])

            logging.debug('Copying archive files to %r', image.mount_dir)
            for archive_name in [
                    'test.rar',
                    'Encrypted.rar',
                    'Invalid.rar',
                    'Format V4.rar',
                    'Format V5.rar',
                    'Multipart Old Style.rar',
                    'Multipart Old Style.r00',
                    'Multipart New Style.part01.rar',
                    'Multipart New Style.part02.rar',
                    'Multipart New Style.part03.rar',
                    'Nested.rar',
            ]:
                logging.debug('Copying %r', archive_name)
                shutil.copy(
                        os.path.join(self._data_dir, archive_name),
                        image.mount_dir)

            image.unmount()

            # Mount the FAT filesystem via CrosDisks. This simulates mounting
            # archive files on a removable drive, and ensures they are in a
            # location CrosDisks expects them to be in.
            loop_device = image.loop_device
            logging.info('Mounting FAT filesystem from %r via CrosDisks',
                         loop_device)
            self.cros_disks.mount(loop_device, '',
                                  ["ro", "nodev", "noexec", "nosuid"])
            mount_result = self.cros_disks.expect_mount_completion({
                    'status':
                    0,
                    'source_path':
                    loop_device,
            })

            mount_path = utf8(mount_result['mount_path'])
            logging.info('FAT filesystem mounted at %r', mount_path)

            # Perform tests with the archive files in the mounted FAT filesystem.
            self._test_archive(
                    os.path.join(mount_path, 'test.rar'),
                    DefaultFilesystemTestContent())
            self._test_unicode(mount_path)
            self._test_multipart(mount_path)
            self._test_invalid(mount_path)
            self._test_nested(mount_path)

            logging.info('Unmounting FAT filesystem')
            self.cros_disks.unmount(mount_path, [])

    def get_tests(self):
        return [self.test_archives]


class platform_CrosDisksArchive(test.test):
    version = 1

    def run_once(self, *args, **kwargs):
        tester = CrosDisksArchiveTester(self, kwargs['archive_types'])
        tester.run(*args, **kwargs)
