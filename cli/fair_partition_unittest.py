# pylint: disable-msg=C0111
#!/usr/bin/python
#
# Copyright 2008 Google Inc. All Rights Reserved.
"""Test for skylab json utils."""

from __future__ import unicode_literals
from __future__ import print_function

import unittest

import common
from autotest_lib.cli import fair_partition as f


class fair_partition_unittest(unittest.TestCase):

    def test_enumerate_with_random_empty(self):
        self.assertEqual(list(f._enumerate_with_random([])), [])

    def test_enumerate_with_random(self):
        input = [1, 2, 3]
        output = list(f._enumerate_with_random(input))
        self.assertEqual(output[0][:2], (0, 1))
        self.assertEqual(output[1][:2], (1, 2))
        self.assertEqual(output[2][:2], (2, 3))

    def test_normalize_entitlement_trivial(self):
        self.assertEqual(f._normalize_entitlement([]), ())

    def test_normalize_entitlement_singleton(self):
        self.assertAlmostEqual(sum(f._normalize_entitlement([74])), 1)

    def test_normalize_entitlement(self):
        input = [1 * 47, 3 * 47]
        output = list(f._normalize_entitlement(input))
        self.assertAlmostEqual(sum(output), 1)
        self.assertAlmostEqual(output[0], 0.25)
        self.assertAlmostEqual(output[1], 0.75)

    def test_descending_fair_sort_enumerator_trivial(self):
        self.assertEqual(list(f._descending_fair_sort_enumerator([])), [])

    def test_descending_fair_sort_enumerator_singleton(self):
        output = list(f._descending_fair_sort_enumerator(["a"]))
        # 0th element of output must be (0, "a", <some random number>)
        self.assertEqual(output[0][0], 0)
        self.assertEqual(output[0][1], "a")

    def test_full_partial_remaining_trivial(self):
        self.assertEqual(f._full_partial_remaining([], 0), ([], [], 0))

    def test_full_partial_remaining_singleton(self):
        full, partial, remaining = f._full_partial_remaining([1], 7)
        self.assertAlmostEqual(full[0], 7.0)
        self.assertAlmostEqual(partial[0], 0.0)
        self.assertEqual(remaining, 0)

    def test_full_partial_remaining(self):
        full, partial, remaining = f._full_partial_remaining(
            [1.0 / 3, 1.0 / 3, 1.0 / 3], 8)
        self.assertAlmostEqual(full[0], 2.0)
        self.assertAlmostEqual(full[1], 2.0)
        self.assertAlmostEqual(full[2], 2.0)
        self.assertAlmostEqual(partial[0], 2.0 / 3)
        self.assertAlmostEqual(partial[1], 2.0 / 3)
        self.assertAlmostEqual(partial[2], 2.0 / 3)
        self.assertAlmostEqual(remaining, 2.0)

    def test_largest_remainder__trivial(self):
        self.assertEqual(f._largest_remainder([], 0), [])

    def test_largest_remainder_singleton(self):
        self.assertEqual(f._largest_remainder([45], 52), [52])

    def test_largest_remainder(self):
        output = sorted(f._largest_remainder([1, 1, 1, 1, 1], 18))
        self.assertEqual(output, [3, 3, 4, 4, 4])

    def test_partition_trivial(self):
        self.assertEqual(f.partition([], 0), ([], []))

    def test_partition_singleton(self):
        self.assertEqual(f.partition(["a"], 0), ([], ["a"]))

    def test_partition(self):
        input = ["a", "b", "c", "d", "e", "f", "g"]
        to_transfer, to_retain = f.partition(input, 0.5)
        to_transfer, to_retain = set(to_transfer), set(to_retain)
        # transfer and retain subsets must be disjoint
        self.assertTrue(to_transfer.isdisjoint(to_retain))
        # every element of input must be in one set or the other
        self.assertEqual(to_transfer.union(to_retain), set(input))
        # one set must have length 4 and the other length 3
        self.assertEqual(min(len(to_transfer), len(to_retain)), 3)
        self.assertEqual(max(len(to_transfer), len(to_retain)), 4)


if __name__ == "__main__":
    unittest.main()
