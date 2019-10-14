# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import tempfile
import unittest

import config


class CanLoadDefaultTestCase(unittest.TestCase):
    """Ensure that configs can load the default JSON"""

    def runTest(self):
        """Main test logic"""
        platform = "foo"
        cfg = config.Config(platform)
        self.assertIsInstance(cfg.has_keyboard, bool)


class _MockConfigTestCaseBaseClass(unittest.TestCase):
    """
    Base class which handles the setup/teardown of mock config files.

    Sub-classes should declare a class attribute, mock_configs,
    as a dict representing all platforms to be written as JSON files.
    This class writes those JSON files during setUp() and deletes them
    during tearDown().
    During runTest(), sub-classes can create config.Config instances by name
    and run assertions as normal.

    """

    mock_configs = None

    def setUp(self):
        """Set up a tempfile containing the test data"""
        if self.mock_configs is None:
            return
        self.original_config_dir = config.CONFIG_DIR
        config.CONFIG_DIR = tempfile.mkdtemp()
        self.mock_config_files = []
        for platform in self.mock_configs:
            mock_config_file = os.path.join(config.CONFIG_DIR,
                                            '%s.json' % platform)
            with open(mock_config_file, 'w') as f:
                json.dump(self.mock_configs[platform], f)
            self.mock_config_files.append(mock_config_file)

    def tearDown(self):
        """After tests are complete, delete the tempfile"""
        if self.mock_configs is None:
            return
        for tf in self.mock_config_files:
            os.remove(tf)
        os.rmdir(config.CONFIG_DIR)
        config.CONFIG_DIR = self.original_config_dir


class InheritanceTestCase(_MockConfigTestCaseBaseClass):
    """Ensure that platforms inherit attributes correctly"""

    mock_configs = {
            'DEFAULTS': {
                    'no_override': 'default',
                    'parent_override': 'default',
                    'child_override': 'default',
                    'both_override': 'default',
                    'parent': None
            },
            'childboard': {
                    'child_override': 'child',
                    'both_override': 'child',
                    'parent': 'parentboard'
            },
            'parentboard': {
                    'parent_override': 'parent',
                    'both_override': 'parent'
            }
    }

    def runTest(self):
        """
        Verify that the following situations resolve correctly:
            A platform that inherit some overridess from another platform
            A platform that does not inherit from another platform
            A platform not found in the config file
        """
        child_config = config.Config('childboard')
        #print(child_config)
        self.assertEqual(child_config.no_override, 'default')
        self.assertEqual(child_config.parent_override, 'parent')
        self.assertEqual(child_config.child_override, 'child')
        self.assertEqual(child_config.both_override, 'child')
        with self.assertRaises(AttributeError):
            child_config.foo  # pylint: disable=pointless-statement

        parent_config = config.Config('parentboard')
        self.assertEqual(parent_config.no_override, 'default')
        self.assertEqual(parent_config.parent_override, 'parent')
        self.assertEqual(parent_config.child_override, 'default')
        self.assertEqual(parent_config.both_override, 'parent')

        foo_config = config.Config('foo')
        self.assertEqual(foo_config.no_override, 'default')
        self.assertEqual(foo_config.parent_override, 'default')
        self.assertEqual(foo_config.child_override, 'default')
        self.assertEqual(foo_config.both_override, 'default')

        # While we're here, verify that str(config) doesn't break
        str(child_config)  # pylint: disable=pointless-statement


class PlatformNamesTestCase(unittest.TestCase):
    """Ensure that each config has a correct 'platform' attribute"""

    def runTest(self):
        """
        For each JSON config file (except DEFAULTS), verify that there is an
        attribute 'platform' whose value exactly matches the file's basename.
        For example, rambi.json should contain {'platform': 'rambi'}
        """
        for filename in os.listdir(config.CONFIG_DIR):
            filepath = os.path.join(config.CONFIG_DIR, filename)
            platform_name, ext = os.path.splitext(filename)
            if ext != '.json' or platform_name == 'DEFAULTS':
                continue
            with open(filepath) as f:
                d = json.load(f)
                self.assertIn('platform', d,
                        msg='JSON file %s did not contain platform attribute' \
                        % filepath)
                self.assertEqual(platform_name, d['platform'],
                        msg='JSON file %s contained mismatched platform %s' \
                        % (filepath, d['platform']))


if __name__ == '__main__':
    unittest.main()
