#!/usr/bin/python

"""
Fetch credentials used by lab tools from Google storage.

Usage?  Just run it.
    utils/download_creds.py
"""

import os
import sys

import common
from chromite.lib import gs
from chromite.lib import osutils

from autotest_lib.utils import external_packages


CRED_DIR = 'creds'
RUN_SUITE_SERVICE_ACCOUNT = (
        'gs://chromeos-proxy.appspot.com/skylab-trampoline.json')

def _fetch_run_suite_creds(ctx, creds_dir):
    """Download creds for labtools run_suites.

    Args:
      ctx: A gs.GSContext object.
      creds_dir: A string path.
    """
    cred_file = os.path.join(creds_dir,
                             'skylab_trampoline_service_account.json')
    ctx.Copy(RUN_SUITE_SERVICE_ACCOUNT, cred_file)


def main():
    """Download credentials."""
    autotest_dir = external_packages.find_top_of_autotest_tree()
    creds_dir = os.path.join(autotest_dir, CRED_DIR)
    osutils.SafeMakedirs(creds_dir)
    ctx = gs.GSContext()
    _fetch_run_suite_creds(ctx, creds_dir)


if __name__ == '__main__':
    sys.exit(main())
