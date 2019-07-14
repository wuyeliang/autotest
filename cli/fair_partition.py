from __future__ import unicode_literals
from __future__ import print_function

from math import modf
import random as r


def _enumerate_with_random(xs):
    """ List[(key * value)] -> List[(key * value * rand)]

    like 'enumerate' but with a third argument that can be used as a random
    tiebreaker for fair sorting

    @param xs : an iterator of things

    @return : an iterator of triples consisting of
        1) the index into the original iterator
        2) the element drawn from the iterator
        3) a number in the range [0,1) chosen uniformly at random
    """
    for (k, v) in enumerate(xs):
        yield (k, v, r.random())


def _normalize_entitlement(entitlement):
    """normalize a list of entitlements so it has unit sum

    @param entitlement : a list of constants proportional to the share of
                         the total that the nth item is entitled to.

    @result : same as entitlement, but normalized to sum to 1.
    """
    s = sum(entitlement)
    return tuple(x / float(s) for x in entitlement)


def descending_fair_sort_indices(xs):
    """fairly sort an iterator of values in descending order.

    each item in the iterator is a pair consisting of an index into xs
    and the original value

    (4, 5, 6) --> iter([(2, 6), (1, 5), (0, 4)])

    @param xs : an iterator of things

    @return : the indices of xs, but with ties resolved fairly
    """
    for idx, _, _ in sorted(
            _enumerate_with_random(xs),
            key=(lambda (_, v, tiebreaker): (v, tiebreaker)),
            reverse=True):
        yield idx


def _full_partial_remaining(quota, seats):
    """number of full seats, partial seats, and remaining seats to be filled.

    given a list of numbers with unit sum (e.g. [0.5, 0.2, 0.3])
    perform the first step of fairly allocating a non-negative integer
    number of seats between them.

    @param quota : a list of numbers with unit sum

    @param seats : the number of items to be distributed.

    @return : a triple containing three things
            1) the number of full seats each index is entitled to
            2) the number of partial seats each index is entitled to
            3) the number of remaining seats that need to be filled from (2)
    """
    full = []
    partial = []
    must_fill = seats
    for x in quota:
        partial_seat, full_seats = modf(x * seats)
        full.append(full_seats)
        partial.append(partial_seat)
        must_fill -= full_seats
    return full, partial, must_fill


def _largest_remainder(entitlement, seats):
    """distribute stuff according to the largest remainder method.

    @param entitlement : a not-necessarily-normalized list of numbers
    representing
                         how many seats/things each index is entitled to.

    @param seats : the number of seats to distribute

    @return :  a list of integers of the same length as entitlement summing to
               seats. The allocation of seats is intended to be as close as
               possible
               To the original entitlement.
    """
    quota = _normalize_entitlement(entitlement)
    out, rems, remaining = _full_partial_remaining(quota, seats)
    indices = descending_fair_sort_indices(rems)
    for idx in indices:
        if remaining <= 0:
            break
        out[idx] += 1
        remaining -= 1
    assert sum(out) == seats
    return out


def _indices(xs):
    """get an iterator of indices over an iterator.

    Do not materialize the entire iterator first.

    @param xs : an iterator of things

    @return : an iterator of indices of the same length as (xs)
    """
    for k, _ in enumerate(xs):
        yield k


def partition(xs, ratio):
    """take a list of items and a ratio and return two lists.

    The ratio determines which fraction of the items are transferred.

    @param xs : a list of things to split between the transfer and retain group.

    @param ratio : the ratio of things to transfer.

    @return : a list of two things
              1) the elements of xs that are going to be transferred
              2) the elements of xs that are going to be retained
    """
    ratios = [ratio, 1.0 - ratio]
    transfer_count, _ = _largest_remainder(ratios, len(xs))
    transfer_count = int(round(transfer_count))
    to_transfer_indices = r.sample(
        population=list(_indices(xs)), k=transfer_count)
    to_transfer = []
    to_retain = []
    for k, v in enumerate(xs):
        if k in to_transfer_indices:
            to_transfer.append(v)
        else:
            to_retain.append(v)
    return to_transfer, to_retain
