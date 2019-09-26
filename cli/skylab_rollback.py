import os
import subprocess


BATCH_SIZE = 200


# delete all the duts and un-migrate the corresponding entries in
# autotest. We achieve un-migrated by renaming a hostname with the suffix
# -migrated-do-not-use so it does not have the suffix.
# Then, for good measure, we unlock everything.
ROLLBACK_CMD = r"""
bug="${ROLLBACK_BUG:-b/7}"

skylab remove-duts -delete -bug b/7 "$@"

declare -a mangled

for item in "$@"; do
    mangled+=("$item"-migrated-do-not-use)
done

echo y > /tmp/yfile

cat /tmp/yfile | atest host rename --for-rollback "${mangled[@]}"

atest host mod --unlock "${mangled[@]}"
"""


def _batches(xs, batch_size=BATCH_SIZE):
    """yield batches of a given size"""
    out = []
    for x in xs:
        out.append(x)
        if len(out) >= batch_size:
            yield out
            out = []
    if out:
        yield out


def rollback(hosts, bug=None, dry_run=False):
    """rollback a collection of hosts"""
    assert isinstance(bug, (int, str, float, long, type(None)))
    old_environ = os.environ.copy()
    out = []
    if bug:
        os.environ["ROLLBACK_BUG"] = str(bug)
    try:
        for slice_ in _batches(hosts):
            cmd = ["bash", "-c", ROLLBACK_CMD, "bash"] + slice_
            if dry_run:
                out.append(cmd)
            else:
                subprocess.call(cmd)
    finally:
        os.environ.clear()
        os.environ.update(old_environ)
    if not dry_run:
        out = None
    return out
