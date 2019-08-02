# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

from autotest_lib.client.common_lib import error

from autotest_lib.client.cros.enterprise import policy

"""
This is the unittest file for policy.py.
If you modify that file, you should be at minimum re-running this file.

Add and correct tests as changes are made to the utils file.

To run the tests, use the following command from your DEV box (outside_chroot):

src/third_party/autotest/files/utils$ python unittest_suite.py \
autotest_lib.client.cros.enterprise.test_policy --debug

"""


class TestPolicyManager(unittest.TestCase):

    dictValue = {'scope': 'testScope', 'source': 'testSource',
                 'level': 'testLevel', 'value': 'testValue'}
    dictValue2 = {'scope': 'testScope', 'source': 'testSource',
                  'level': 'testLevel', 'value': 'testValue2'}

    def test_setting_params(self):
        testPolicy = policy.Policy()
        testPolicy.name = 'Test'
        testPolicy.level = 1
        testPolicy.value = 'TheValue'
        testPolicy.scope = 'TestValue'
        testPolicy.source = 'Cloud'
        self.assertEqual(testPolicy.name, 'Test')
        self.assertEqual(testPolicy.level, 1)
        self.assertEqual(testPolicy.scope, 'TestValue')
        self.assertEqual(testPolicy.source, 'Cloud')
        self.assertEqual(testPolicy.value, 'TheValue')

    def test_setting_group_user(self):
        testPolicy = policy.Policy()
        testPolicy.name = 'Test'
        testPolicy.group = 'user'
        self.assertEqual(testPolicy.name, 'Test')
        self.assertEqual(testPolicy.source, 'cloud')
        self.assertEqual(testPolicy.level, 'mandatory')
        self.assertEqual(testPolicy.scope, 'user')

    def test_setting_group_device(self):
        testPolicy = policy.Policy()
        testPolicy.name = 'Test'
        testPolicy.group = 'device'
        self.assertEqual(testPolicy.name, 'Test')
        self.assertEqual(testPolicy.source, 'cloud')
        self.assertEqual(testPolicy.level, 'mandatory')
        self.assertEqual(testPolicy.scope, 'machine')

    def test_setting_group_suggested_user(self):
        testPolicy = policy.Policy()
        testPolicy.name = 'Test'
        testPolicy.group = 'suggested_user'
        self.assertEqual(testPolicy.name, 'Test')
        self.assertEqual(testPolicy.source, 'cloud')
        self.assertEqual(testPolicy.level, 'recommended')
        self.assertEqual(testPolicy.scope, 'user')

    def test_setting_value(self):
        testPolicy = policy.Policy()
        testPolicy.name = 'Test'
        testPolicy.set_policy_from_dict(self.dictValue)

        self.assertEqual(testPolicy.name, 'Test')
        self.assertEqual(testPolicy.level, 'testLevel')
        self.assertEqual(testPolicy.scope, 'testScope')
        self.assertEqual(testPolicy.source, 'testSource')
        self.assertEqual(testPolicy.value, 'testValue')

    def test_get_policy_as_dict(self):
        testPolicy = policy.Policy()
        testPolicy.name = 'Test'
        testPolicy.level = 1
        testPolicy.value = 'TheValue'
        testPolicy.scope = 'TestValue'
        testPolicy.source = 'Cloud'

        expectedDict = {'Test':
                            {'scope': 'TestValue',
                             'level': 1,
                             'value': 'TheValue',
                             'source': 'Cloud'}}
        self.assertEqual(expectedDict, testPolicy.get_policy_as_dict())

    def test_policy_eq_ne(self):
        testPolicy = policy.Policy()
        testPolicy.name = 'Test'
        testPolicy.set_policy_from_dict(self.dictValue)

        testPolicy2 = policy.Policy()
        testPolicy2.name = 'Test2'
        testPolicy2.set_policy_from_dict(self.dictValue)
        self.assertTrue(testPolicy == testPolicy2)
        self.assertFalse(testPolicy != testPolicy2)

        testPolicy3 = policy.Policy()
        testPolicy3.name = 'Test3'
        testPolicy3.set_policy_from_dict(self.dictValue2)
        self.assertFalse(testPolicy == testPolicy3)

    def test_policy_eq_obfuscated(self):
        testPolicy = policy.Policy()
        testPolicy.name = 'Test'
        testValue = {'scope': 'testScope', 'source': 'testSource',
                          'level': 'testLevel',
                           'value': {'NetworkConfigurations':
                                        [{'WiFi': {'Passphrase': 'Secret'}}]}}
        testPolicy.set_policy_from_dict(testValue)

        testPolicy2 = policy.Policy()
        testPolicy2.name = 'TestOpenNetworkConfiguration'
        obfuscatedValue = {'scope': 'testScope', 'source': 'testSource',
                           'level': 'testLevel',
                            'value': {'NetworkConfigurations':
                                        [{'WiFi': {'Passphrase': '********'}}]}}
        testPolicy2.set_policy_from_dict(obfuscatedValue)
        self.assertTrue(testPolicy == testPolicy2)
        self.assertFalse(testPolicy != testPolicy2)

    def test_is_network_policy(self):
        self.assertTrue(
            policy.is_network_policy('TestOpenNetworkConfiguration'))

        self.assertFalse(policy.is_network_policy('Test'))

    def test_check_obfuscation(self):
        testValue = {'NetworkConfigurations':
                        [{'WiFi': {'Passphrase': '********'}}]}
        self.assertTrue(policy.check_obfuscation(testValue))

        testValue2 = {'NetworkConfigurations':
                        [{'WiFi': {'Passphrase': 'Bad'}}]}
        self.assertFalse(policy.check_obfuscation(testValue2))

        testValue3 = {'NetworkConfigurations':
                        [{'WiFi': {'EAP': {'Password': '********'}}}]}
        self.assertTrue(policy.check_obfuscation(testValue3))

        testValue4 = {'NetworkConfigurations':
                        [{'WiFi': {'EAP': {'Password': 'Bad'}}}]}
        self.assertFalse(policy.check_obfuscation(testValue4))

        testValue5 = {'Certificates':
                        [{'PKCS12': '********'}]}
        self.assertTrue(policy.check_obfuscation(testValue5))

        testValue6 = {'Certificates':
                        [{'PKCS12': 'BAD'}]}
        self.assertFalse(policy.check_obfuscation(testValue6))

    def test_invalid_policy_dict(self):
        with self.assertRaises(error.TestError) as context:
            testPolicy = policy.Policy()
            testPolicy.name = 'Bad Policy'
            testPolicy.set_policy_from_dict({'Invalid Keys': 'Invalid Value'})
        self.assertIn('Incorrect input data provided', str(context.exception))


if __name__ == '__main__':
    unittest.main()
