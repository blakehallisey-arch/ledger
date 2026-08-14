"""Scorecard math, small-sample honesty, open ordering, brief derivation."""

import datetime
import shutil
import tempfile
import unittest

from ledger import report, store

D = datetime.date


class ReportCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ledger-report-")
        self.addCleanup(shutil.rmtree, self.dir, True)

    def add(self, agent, day, output="some advice", action=None, ruled_day=None,
            outcome=None, outcome_day=None, context="a question", signal=None):
        run_id = store.append(self.dir, agent, context, output, signal, date=day)
        if action:
            store.rule(self.dir, agent, run_id, "Action", action,
                       date=ruled_day or day)
        if outcome:
            store.rule(self.dir, agent, run_id, "Outcome", outcome,
                       date=outcome_day or ruled_day or day)
        return run_id


class ScorecardMathTests(ReportCase):
    def build(self):
        # 6 taken, 2 rejected, 1 partial, 1 pending. Of the taken, 4 right,
        # 1 wrong, 1 with no verdict.
        self.add("a", D(2026, 1, 1), action="TAKEN", ruled_day=D(2026, 1, 2),
                 outcome="RIGHT", outcome_day=D(2026, 1, 9))
        self.add("a", D(2026, 1, 2), action="TAKEN", ruled_day=D(2026, 1, 4),
                 outcome="RIGHT", outcome_day=D(2026, 1, 9))
        self.add("a", D(2026, 1, 3), action="TAKEN", ruled_day=D(2026, 1, 4),
                 outcome="RIGHT")
        self.add("a", D(2026, 1, 4), action="TAKEN", ruled_day=D(2026, 1, 5),
                 outcome="RIGHT")
        self.add("a", D(2026, 1, 5), action="TAKEN", ruled_day=D(2026, 1, 15),
                 outcome="WRONG")
        self.add("a", D(2026, 1, 6), action="TAKEN", ruled_day=D(2026, 1, 7))
        self.add("a", D(2026, 1, 7), action="REJECTED", ruled_day=D(2026, 1, 8))
        self.add("a", D(2026, 1, 8), action="REJECTED", ruled_day=D(2026, 1, 9))
        self.add("a", D(2026, 1, 9), action="PARTIAL", ruled_day=D(2026, 1, 10))
        self.add("a", D(2026, 1, 10))

    def test_counts_and_rates(self):
        self.build()
        row = report.score_agent(self.dir, "a", as_of=D(2026, 2, 1))
        self.assertEqual(row["runs"], 10)
        self.assertEqual(row["taken"], 6)
        self.assertEqual(row["rejected"], 2)
        self.assertEqual(row["partial"], 1)
        self.assertEqual(row["pending"], 1)
        self.assertEqual(row["ruled"], 9)
        self.assertAlmostEqual(row["take_rate"], 6 / 9)
        self.assertEqual(row["outcome_right"], 4)
        self.assertEqual(row["outcome_wrong"], 1)
        self.assertEqual(row["outcome_open"], 1)
        self.assertEqual(row["outcome_judged"], 5)
        self.assertAlmostEqual(row["right_rate"], 4 / 5)
        self.assertFalse(row["small_sample"])

    def test_median_days_to_ruling(self):
        self.build()
        row = report.score_agent(self.dir, "a", as_of=D(2026, 2, 1))
        # lags: 1,2,1,1,10,1,1,1,1 -> median 1
        self.assertEqual(row["median_days_to_ruling"], 1)

    def test_pending_entries_are_not_counted_as_rulings(self):
        self.add("b", D(2026, 1, 1))
        self.add("b", D(2026, 1, 2))
        row = report.score_agent(self.dir, "b", as_of=D(2026, 2, 1))
        self.assertIsNone(row["take_rate"])
        self.assertIsNone(row["median_days_to_ruling"])
        self.assertEqual(row["ruled"], 0)

    def test_ranked_by_take_rate_with_unruled_agents_last(self):
        self.add("high", D(2026, 1, 1), action="TAKEN", ruled_day=D(2026, 1, 1))
        self.add("low", D(2026, 1, 1), action="REJECTED", ruled_day=D(2026, 1, 1))
        self.add("none", D(2026, 1, 1))
        rows = report.scorecard(self.dir, as_of=D(2026, 2, 1))
        self.assertEqual([r["agent"] for r in rows], ["high", "low", "none"])


class SmallSampleTests(ReportCase):
    def test_under_five_rulings_is_flagged(self):
        for i in range(4):
            self.add("a", D(2026, 1, 1 + i), action="TAKEN",
                     ruled_day=D(2026, 1, 1 + i))
        row = report.score_agent(self.dir, "a", as_of=D(2026, 2, 1))
        self.assertTrue(row["small_sample"])
        self.assertAlmostEqual(row["take_rate"], 1.0)
        text = report.format_scorecard(report.scorecard(self.dir), as_of=D(2026, 2, 1))
        self.assertIn("a*", text)
        self.assertIn("too few to mean anything", text)
        # The numbers are still printed, not hidden.
        self.assertIn("100%", text)

    def test_five_rulings_is_not_flagged(self):
        for i in range(5):
            self.add("a", D(2026, 1, 1 + i), action="TAKEN",
                     ruled_day=D(2026, 1, 1 + i))
        row = report.score_agent(self.dir, "a", as_of=D(2026, 2, 1))
        self.assertFalse(row["small_sample"])
        text = report.format_scorecard(report.scorecard(self.dir), as_of=D(2026, 2, 1))
        self.assertNotIn("too few to mean anything", text)


class OpenTests(ReportCase):
    def test_oldest_first_with_day_counts(self):
        self.add("b", D(2026, 1, 10), output="newer")
        self.add("a", D(2026, 1, 1), output="oldest")
        self.add("a", D(2026, 1, 5), output="middle",
                 action="TAKEN", ruled_day=D(2026, 1, 6))
        rows = report.open_entries(self.dir, as_of=D(2026, 1, 20))
        self.assertEqual([r["output"] for r in rows], ["oldest", "newer"])
        self.assertEqual(rows[0]["days_open"], 19)
        self.assertEqual(rows[1]["days_open"], 10)

    def test_ruled_entries_never_appear(self):
        self.add("a", D(2026, 1, 1), action="REJECTED", ruled_day=D(2026, 1, 2))
        self.assertEqual(report.open_entries(self.dir, as_of=D(2026, 1, 20)), [])
        self.assertIn(
            "nothing open",
            report.format_open([], as_of=D(2026, 1, 20)),
        )

    def test_scoped_to_one_agent(self):
        self.add("a", D(2026, 1, 1))
        self.add("b", D(2026, 1, 1))
        rows = report.open_entries(self.dir, "a", as_of=D(2026, 1, 20))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["agent"], "a")

    def test_format_names_the_command_that_clears_it(self):
        self.add("a", D(2026, 1, 1))
        text = report.format_open(
            report.open_entries(self.dir, as_of=D(2026, 1, 20)), as_of=D(2026, 1, 20)
        )
        self.assertIn("19 days open", text)
        self.assertIn("ledger acted", text)


class BriefTests(ReportCase):
    def test_reports_the_counts_and_the_pattern(self):
        for i in range(5):
            self.add("a", D(2026, 1, 1 + i),
                     output="Rewrite the pipeline and migrate every caller",
                     action="REJECTED", ruled_day=D(2026, 1, 2 + i))
        for i in range(3):
            self.add("a", D(2026, 1, 10 + i), output="Add a lock around the append",
                     action="TAKEN", ruled_day=D(2026, 1, 11 + i),
                     outcome="RIGHT", outcome_day=D(2026, 1, 20))
        text = report.brief(self.dir, "a", last=10, as_of=D(2026, 2, 1))
        self.assertIn("3 taken, 5 rejected", text)
        self.assertIn("Take rate 38%", text)
        self.assertIn("rewrite", text)
        self.assertIn("migrate", text)

    def test_says_so_instead_of_inventing_a_pattern(self):
        outputs = [
            "Cache the roster lookup",
            "Delete the unused branch cleanup job",
            "Split the giant fixture into three",
        ]
        for i, out in enumerate(outputs):
            self.add("a", D(2026, 1, 1 + i), output=out, action="REJECTED",
                     ruled_day=D(2026, 1, 2 + i))
        self.add("a", D(2026, 1, 8), output="Cache the roster lookup harder",
                 action="TAKEN", ruled_day=D(2026, 1, 9))
        text = report.brief(self.dir, "a", last=10, as_of=D(2026, 2, 1))
        self.assertIn("no pattern in the text", text)

    def test_stays_quiet_on_a_pattern_under_three_rejections(self):
        for i in range(2):
            self.add("a", D(2026, 1, 1 + i),
                     output="Rewrite the pipeline and migrate every caller",
                     action="REJECTED", ruled_day=D(2026, 1, 2 + i))
        text = report.brief(self.dir, "a", last=10, as_of=D(2026, 2, 1))
        self.assertNotIn("share wording", text)
        self.assertIn("too few to be a pattern", text)

    def test_flags_pending_entries_as_not_agreement(self):
        self.add("a", D(2026, 1, 1))
        text = report.brief(self.dir, "a", last=10, as_of=D(2026, 1, 20))
        self.assertIn("Silence is not agreement", text)
        self.assertIn("PENDING (19 days)", text)

    def test_last_n_window(self):
        for i in range(12):
            self.add("a", D(2026, 1, 1 + i), output="advice %d" % (i + 1))
        text = report.brief(self.dir, "a", last=3, as_of=D(2026, 2, 1))
        self.assertIn("your last 3 run(s) of 12", text)
        self.assertIn("advice 12", text)
        self.assertNotIn("advice 9", text)

    def test_empty_window_does_not_crash(self):
        store.append(self.dir, "a", "ctx", "out")
        ledger = store.load(self.dir, "a")
        ledger.entries = []
        store.save(self.dir, ledger)
        text = report.brief(self.dir, "a", last=5, as_of=D(2026, 2, 1))
        self.assertIn("Nothing recorded yet", text)


if __name__ == "__main__":
    unittest.main()
