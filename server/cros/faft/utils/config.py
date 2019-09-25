# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os

import common

CONFIG_DIR = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), os.pardir, 'configs')


def _get_config_filepath(platform):
    """Find the JSON file containing the platform's config"""
    return os.path.join(CONFIG_DIR, '%s.json' % platform)


def _has_config_file(platform):
    """Determine whether the platform has a config file"""
    return os.path.isfile(_get_config_filepath(platform))


def _load_config(platform):
    """Load the platform's JSON config into a dict"""
    fp = _get_config_filepath(platform)
    with open(fp) as config_file:
        return json.load(config_file)


class Config(object):
    """Configuration for FAFT tests.

    This object is meant to be the interface to all configuration required
    by FAFT tests, including device specific overrides.

    It gets the values from the JSON files in CONFIG_DIR.
    Default values are declared in the DEFAULTS.json.
    Platform-specific overrides come from <platform>.json.
    Boards can also inherit overrides from a parent platform, with the child
    platform's overrides taking precedence over the parent's.

    TODO(gredelston): Move the JSON out of this directory, as per
    go/cros-fw-testing-configs

    @ivar platform: string containing the board/model name being tested.
    """

    def __init__(self, platform):
        """Initialize an object with FAFT settings.

        @param platform: The name of the platform being tested.
        """
        # Load JSON files order of importance (platform, parent/s, DEFAULTS)
        self.platform = platform.rsplit('_', 1)[-1].lower().replace("-", "_")
        _precedence_list = []
        if _has_config_file(self.platform):
            _precedence_list.append(_load_config(self.platform))
            parent_platform = _precedence_list[-1].get('parent', None)
            while parent_platform is not None:
                _precedence_list.append(_load_config(parent_platform))
                parent_platform = _precedence_list[-1].get('parent', None)
        else:
            logging.debug(
                    'No platform config file found at %s. Using default.',
                    _get_config_filepath(self.platform))
        _precedence_list.append(_load_config('DEFAULTS'))

        # Set attributes
        all_attributes = _precedence_list[-1].keys()
        self.attributes = {}
        self.attributes['platform'] = self.platform
        for attribute in all_attributes:
            if attribute.endswith('.DOC'):
                continue
            for config_dict in _precedence_list:
                if attribute in config_dict:
                    self.attributes[attribute] = config_dict[attribute]
                    break

    def __getattr__(self, attr):
        if attr in self.attributes:
            return self.attributes[attr]
        raise AttributeError('FAFT config has no attribute named %s' % attr)

    def __str__(self):
        str_list = []
        str_list.append('----------[ FW Testing Config Variables ]----------')
        for attr in sorted(self.attributes):
            str_list.append('  %s: %s' % (attr, self.attributes[attr]))
        str_list.append('---------------------------------------------------')
        return '\n'.join(str_list)
