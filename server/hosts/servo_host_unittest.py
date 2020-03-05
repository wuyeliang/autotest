import mock
import unittest

import common

from autotest_lib.server.hosts import servo_host


class MockCmd(object):
    """Simple mock command with base command and results"""

    def __init__(self, cmd, exit_status, stdout):
        self.cmd = cmd
        self.stdout = stdout
        self.exit_status = exit_status


class MockHost(servo_host.ServoHost):
    """Simple host for running mock'd host commands"""

    def __init__(self, *args):
        self._mock_cmds = {c.cmd: c for c in args}
        self._init_attributes()
        self.hostname = "chromeos1-row1-rack1-host1"
        self.servo_port = '9991'

    def run(self, command, **kwargs):
        """Finds the matching result by command value"""
        mock_cmd = self._mock_cmds[command]
        file_out = kwargs.get('stdout_tee', None)
        if file_out:
            file_out.write(mock_cmd.stdout)
        return mock_cmd


class ServoHostServoStateTestCase(unittest.TestCase):
    """Tests to verify changing the servo_state"""
    def test_return_broken_if_state_not_defined(self):
        host = MockHost()
        self.assertIsNotNone(host)
        self.assertIsNone(host._servo_state)
        self.assertIsNotNone(host.get_servo_state())
        self.assertEqual(host.get_servo_state(), servo_host.SERVO_STATE_UNKNOWN)
        self.assertEqual(host._servo_state, None)

    def test_verify_set_state_broken_if_raised_error(self):
        host = MockHost()
        host._is_localhost = True
        host._repair_strategy = mock.Mock()
        host._repair_strategy.verify.side_effect = Exception('something_ex')
        try:
            host.verify(silent=True)
            self.assertEqual("Should not be reached", 'expecting error')
        except:
            pass
        self.assertEqual(host.get_servo_state(), servo_host.SERVO_STATE_BROKEN)

    def test_verify_set_state_working_if_no_raised_error(self):
        host = MockHost()
        host._repair_strategy = mock.Mock()
        host.verify(silent=True)
        self.assertEqual(host.get_servo_state(), servo_host.SERVO_STATE_WORKING)

    def test_repair_set_state_broken_if_raised_error(self):
        host = MockHost()
        host._is_localhost = True
        host._repair_strategy = mock.Mock()
        host._repair_strategy.repair.side_effect = Exception('something_ex')
        try:
            host.repair(silent=True)
            self.assertEqual("Should not be reached", 'expecting error')
        except:
            pass
        self.assertEqual(host.get_servo_state(), servo_host.SERVO_STATE_BROKEN)

    def test_repair_set_state_working_if_no_raised_error(self):
        host = MockHost()
        host._is_labstation = False
        host._repair_strategy = mock.Mock()
        host.repair(silent=True)
        self.assertEqual(host.get_servo_state(), servo_host.SERVO_STATE_WORKING)


class ServoHostInformationValidator(unittest.TestCase):
    """Tests to verify logic in servo host data"""
    def test_true_when_host_and_port_is_correct(self):
        hostname = 'chromeos1-rack1-row1-host1-servo'
        port = 9999
        self.assertTrue(servo_host.is_servo_host_information_valid(hostname, port))

        hostname = 'CHROMEOS1-RACK1-ROW1-host1-SERVO'
        port = 7001
        self.assertTrue(servo_host.is_servo_host_information_valid(hostname, port))

    def test_false_when_host_is_incorrect_and_port_is_correct(self):
        port = '9991'
        self.assertFalse(
            servo_host.is_servo_host_information_valid('ch1%ra1$r1.h1.servo', port))
        self.assertFalse(
            servo_host.is_servo_host_information_valid('[undefined]', port))
        self.assertFalse(
            servo_host.is_servo_host_information_valid('None', port))
        self.assertFalse(
            servo_host.is_servo_host_information_valid('', port))
        self.assertFalse(
            servo_host.is_servo_host_information_valid(None, port))

    def test_false_when_port_is_incorrect_and_host_is_correct(self):
        hostname = 'Some_host-my'
        self.assertFalse(servo_host.is_servo_host_information_valid(hostname, None))
        self.assertFalse(servo_host.is_servo_host_information_valid(hostname, -1))
        self.assertFalse(servo_host.is_servo_host_information_valid(hostname, 0))
        self.assertFalse(servo_host.is_servo_host_information_valid(hostname, None))


class ServoHostInformationExistor(unittest.TestCase):
    """Tests to verify logic in servo host present"""
    def test_true_when_host_and_port_is_correct(self):
        hostname = 'chromeos1-rack1-row1-host1-servo'
        port = 9999
        self.assertTrue(servo_host._is_servo_host_information_exist(hostname, port))

        hostname = 'CHROMEOS1'
        port = 1
        self.assertTrue(servo_host._is_servo_host_information_exist(hostname, port))

    def test_false_when_port_was_not_set_up(self):
        hostname = 'chromeos1%rack1$row1.host1.servo'
        self.assertFalse(servo_host._is_servo_host_information_exist(hostname, '9999'))
        self.assertFalse(servo_host._is_servo_host_information_exist(hostname, None))
        self.assertFalse(servo_host._is_servo_host_information_exist(hostname, "9999"))

    def test_false_when_host_was_not_set_up(self):
        port = 1234
        self.assertFalse(servo_host._is_servo_host_information_exist('', port))
        self.assertFalse(servo_host._is_servo_host_information_exist(None, port))
        self.assertFalse(servo_host._is_servo_host_information_exist('  ', port))


if __name__ == '__main__':
    unittest.main()
