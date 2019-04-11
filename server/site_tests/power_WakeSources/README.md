# Wake sources testing

[TOC]

## Introduction

On Chrome device, several wake sources are expected to wake the system from
sleep. Not all wake sources will turn the display back on after resume (if
[Dark Resume] is enabled). Only wakes that are triggered by input devices will
cause a Full Resume (turn the display on).

This test thus makes sure that following wake sources causes a Full Resume:

*   Power button
*   Lid open
*   Lid close
*   Base attach
*   Base detach
*   Internal keyboard
*   USB keyboard

This test also makes sure that RTC triggers a Dark Resume.

Currently this test cannot verify the following wake sources and have to be
tested manually.
*   Fingerprint sensor
*   WiFi

## Steps to run the test.
The steps below describe how to run the test with a Servo V4. The steps should
be similar for other Servos too.

1.  Make sure that servo has the latest firmware.
    *   `$ sudo servo_updater`
2.  This test depends on the Servo's USB HID emulator capability. Please run
    [firmware_FlashServoKeyboardMap] Autotest to install the latest
    [keyboard.hex] onto Servo.
3.  Make sure that the USBC charger is plugged into Servo before running the
    test.
3.  Run the test.
    *   `$ test_that ${DUT_ipaddr} power_WakeSources`

[Dark Resume]: https://chromium.googlesource.com/chromiumos/platform2/+/master/power_manager/docs/dark_resume.md
[keyboard.hex]: https://chromium.googlesource.com/chromiumos/third_party/hdctools/+/refs/heads/master/servo/firmware/usbkm/KeyboardSerial/Keyboard.hex
[firmware_FlashServoKeyboardMap]: https://chromium.googlesource.com/chromiumos/third_party/autotest/+/refs/heads/master/server/site_tests/firmware_FlashServoKeyboardMap/