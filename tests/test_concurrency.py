"""Two writers at once must not lose an entry or half-write the file.

This is the failure that has no error message. An orchestrator fans out, two
returns land in the same second, both read "the last run is 7", both write
run 8, and one of them is simply gone — no traceback, no bad exit code, just a
ledger that is quietly missing a run. The lock in store.locked() exists for
that, and a lock with no test on it is decoration.
"""

import multiprocessing
import shutil
import tempfile
import unittest

from ledger import store

WRITERS = 8
PER_WRITER = 6


def _write(args):
    directory, worker = args
    ids = []
    for i in range(PER_WRITER):
        ids.append(
            store.append(
                directory,
                "busy",
                "worker %d call %d" % (worker, i),
                "recommendation from worker %d, call %d" % (worker, i),
            )
        )
    return ids


class ConcurrentAppendTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ledger-conc-")
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_parallel_appends_keep_every_entry(self):
        ctx = multiprocessing.get_context("spawn")
        with ctx.Pool(WRITERS) as pool:
            results = pool.map(_write, [(self.dir, w) for w in range(WRITERS)])

        handed_out = [i for chunk in results for i in chunk]
        expected = WRITERS * PER_WRITER
        self.assertEqual(len(handed_out), expected)
        # Every id handed out was unique — nobody reused a run number.
        self.assertEqual(len(set(handed_out)), expected)
        self.assertEqual(sorted(handed_out), list(range(1, expected + 1)))

        ledger = store.load(self.dir, "busy")
        self.assertEqual(len(ledger.entries), expected)
        self.assertEqual(
            sorted(e.run_id for e in ledger.entries), list(range(1, expected + 1))
        )

    def test_file_is_still_well_formed_and_round_trips(self):
        ctx = multiprocessing.get_context("spawn")
        with ctx.Pool(4) as pool:
            pool.map(_write, [(self.dir, w) for w in range(4)])
        path = store.path_for(self.dir, "busy")
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(store.render(store.parse(text, "busy")), text)
        # No half-written entry: every entry has all five fields.
        for entry in store.parse(text, "busy").entries:
            self.assertEqual(
                entry.fields(),
                ["Context in", "Output", "Signal", "Action", "Outcome"],
            )

    def test_parallel_rulings_do_not_drop_each_other(self):
        for _ in range(10):
            store.append(self.dir, "busy", "c", "o")
        ctx = multiprocessing.get_context("spawn")
        with ctx.Pool(5) as pool:
            pool.map(_rule, [(self.dir, i) for i in range(1, 11)])
        ledger = store.load(self.dir, "busy")
        self.assertEqual([e.action for e in ledger.entries], ["TAKEN"] * 10)


def _rule(args):
    directory, run_id = args
    store.rule(directory, "busy", run_id, "Action", "TAKEN")
    return run_id


if __name__ == "__main__":
    unittest.main()
