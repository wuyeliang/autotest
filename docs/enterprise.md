# Autotest Documentation For Enterprise
To provide all the information needed about the current state of Enterprise
autotest automation. Current coverage, location of tests, how to execute
the tests, what machine to run the tests on, test breakdown, etc.

## Current coverage

Calculating coverage could be tricky as there are many different ways
it could be done. We were using two ways to do it:

*   By policy:
    *   Look at this recently updated [spreadsheet](http://go/ent-pol-auto):
        There are 265 policies available for ChromeOS via C/D Panel. We have
        96 policies automated, 75 of those are in C/D Panel. So that’s
        75/264 = %28 coverage + 21 more tests covering various other policies.
*   By section:
    *   Refer to this recently updated [spreadsheet](http://go/ent-sec-auto)
        in which we list out current coverage.

## Test Location

Tests that automate user policies are located [here](http://go/usr-pol-loc).

Tests that automate device policies are located [here](http://go/dev-pol-loc).

Most of Enterprise tests start with *policy_* but there are some
that begin with *enterprise_*.

## Test Results

*   The best way to view test results is by using stainless:
*   Go to https://stainless.corp.google.com/
*   Click on Test History Matrix
*   In the Test dropdown, select “policy_*”
*   Hit Search and you should see the results like so:
![Results](https://screenshot.googleplex.com/UxMiYrVMDdF.png)

## Running a test

A test can be executed using this command from chroot:
*test_that --board=BOARD_NAME IP_ADDRESS FULL_TEST_NAME*
Example:
*/trunk/src/scripts $ test_that --board=hana 100.107.106.138
policy_DeviceServer.AllowBluetooth_true*

**--board** - should be the board that you have setup locally. You only need to
setup the board ones and you shouldn’t have to touch it again for a long time.
The board that you setup on your workstation doesn’t have to match the
DUT(device under test) board that you’re executing the test on. To set up the
board please follow instructions [here](http://go/run-autotest). You will also
need to run the build_packages command.

**IP_ADDRESS** - IP of the DUT. If you have a device locally, it needs to be
plugged into the test network and not corp network. You can also use a device
in the lab. To reserve a device from the lab please follow these steps:

*   Go here: http://cautotest.corp.google.com/afe/#tab_id=hosts
*   Pick a host from the list and click on it
*   Lock the host you want to run the test on(don’t forget to unlock
    when you’re done)
*   Grab the host name, for example: chromeos15-row3-rack13-host2.
    Use this as the IP: chromeos15-row3-rack13-host2**.cros**.

Full test name - test name can be grabbed from the control file.
[Example](http://go/control-file-name).

You can check other options for test_that by running: *test_that --help*.

## Setting up a local DUT

To run a test on a local DUT you need to make sure the DUT has been
properly setup with a test build. You can use this helpful
[tool](http://go/crosdl-usage). Execute from this dir:
*/chromiumos/src/platform/crostestutils/provingground$*
Run this command to put the build on a USB stick:
*./crosdl.py -c dev -t -b 12503.0.0 -p sarien --to_stick /dev/sda*
Or this command to update the DUT directly(flaky):
*./crosdl.py -c dev -t -b 12105.54.0 -p sarien --to_ip 100.107.106.132*

To find out the right build number, please use [goldeneye](http://go/goldeneye)
and search for the right build for your board.

## Test Breakdown

A typical dir for a user policy(client) test will consist of control files
and a .py test file. A control file will contain basic description of the
test as well as options such as these:
'''python
AUTHOR = 'name’
NAME = 'full_test_name'
ATTRIBUTES = 'suite:ent-nightly, suite:policy'
TIME = 'SHORT'
TEST_CATEGORY = 'General'
TEST_CLASS = 'enterprise'
TEST_TYPE = 'client'
'''

Example of a basic [test](http://go/basic-ent-test).
Class name of the test, *policy_ShowHomeButton* has to match the name of
the .py file.

**run_once** - function that gets called first.
**setup_case** - sets up DMS, logs in, verifies policies values and various
other login arguments. Defined:[enterprise_policy_base](http://go/ent-pol-base)
**start_ui_root** - needed if you’re planning on interacting with UI objects
during your test. Defined:[ui_utils](http://go/ent-ui-utils).
This [CL](http://crrev.com/c/1531141) describes what ui_utils is based off
and the usefulness of it.

**check_home_button** - Function that verifies the presence of the Home button
in this test. Depending on the policy setting, the test is using
*ui.item_present* to verify the status of the Home button.

Every enterprise test will require a run_once function and will most likely
require setup_case. You will need to pass in a dictionary with the policy
name and value into setup_case.

### Useful utility

This [utils.py](http://go/ent_util) file which contains many useful functions
that you’ll come across in tests.

**Some examples:**
**poll_for_condition** - keeps checking for condition to be true until a time
limit is reached at which point it fails.
**run** - allows to run a VT2 command on the DUT.

### Difference between device policy test and user policy test

On top of having a control file and a .py test file like you do for a user
policy test you will also need another control file and another .py server
file to kick off the client test.
[Example](http://go/ent-cont-example) of the control file.
[Example](http://go/ent-test-example) of the .py server file.

### Debugging an autotest

Unfortunately there's no good debugging tool in autotest and you can't use pdb
so you're left with using time.sleep and logging. With time.sleep you can pause
the test and see what's going on in the actual device. When using logging you
can run 'logging.info("what you want to log")' and then when the test is done
running you can check the results here:
/tmp/test_that_latest/results-1-TESTNAME/TESTNAME/debug/TESTNAME.INFO

If a test is failing remotely, on stainless, you can view the logs there by
clicking on the Logs link. You can also see the screenshot of the last screen
before the test finished although they are rarely useful.

### Using Servo board with Autotests

Some tests require the use of the [Servo Board](http://go/servo-ent).
If you want to get ahold of a servo board you need to reach out to crosdistros@
and request one. You can either get a Servo type A or Servo type C, in case
your test involves controlling the power to the DUT.

Setting up the servo, hopefully you'll find this
[screenshot](https://screenshot.googleplex.com/PcZGhW5eqk3) useful. You can see
that two cables on the left go to the DUT and the cable on the right goes into
the host machine. If you're going to be feeding the power to the DUT you will
also need to connect a Type-C charger to the Servo by plugging it into the
slot marked "Dut Power". Note: if you grabbed the micro usb -> USB A cables
in the tech stop make sure that the light on the switch glows orange and not
green. If it's green the tests will not work.

Starting the servo, from chroot run: "sudo servo_updater" make sure everything
is up to date. Then run "sudo servod -b BOARD_NAME" BOARD_NAME being the board
you have built on your server. While this is running, in another terminal tab
you can now execute dut-control commands such as
"dut-control servo_v4_role:scr".

With the servod running you can now execute local tests using the servo board.
[Example test using servo](http://go/servo-ent-example-test).
