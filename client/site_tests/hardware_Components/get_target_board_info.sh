#!/bin/sh
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

ROOT_SSD=/dev/sda5

MOUNTPOINT=$(mktemp -d)
mount -t ext2 -o ro  "$ROOT_SSD" "$MOUNTPOINT"
grep CHROMEOS_RELEASE_DESCRIPTION $MOUNTPOINT/etc/lsb-release | \
    awk '{print $NF}'
umount "$MOUNTPOINT"
rmdir "$MOUNTPOINT"

exit 0
