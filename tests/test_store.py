"""Round-trip fidelity and the human-only block.

These two are the tests that matter. If round-trip is not byte-exact, hand
edits to the file get silently rewritten and the file stops being trustworthy
in a pull request. If `record` can reach the Action or Outcome slot, the agent
grades its own advice and the tool measures nothing.
"""

import datetime
import os
import shutil
import tempfile
import unittest

from ledger import store


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ledger-test-")
        self.addCleanup(shutil.rmtree, self.dir, True)


class RoundTripTests(TempDirCase):
    def assert_round_trips(self, text):
        parsed = store.parse(text, "agent")
        self.assertEqual(store.render(parsed), text)

    def test_empty_and_header_only(self):
        self.assert_round_trips("")
        self.assert_round_trips(store.HEADER.format(agent="gus"))

    def test_generated_file_round_trips_byte_for_byte(self):
        store.append(self.dir, "gus", "a sweep", "move the job")
        store.append(self.dir, "gus", "another sweep", "pin the model id")
        store.rule(self.dir, "gus", 1, "Action", "TAKEN", "did it")
        path = store.path_for(self.dir, "gus")
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        self.assert_round_trips(text)

    def test_unicode_survives(self):
        body = "em—dash, curly “quotes”, naïve, 日本語, →, ½"
        store.append(self.dir, "gus", body, "output " + body, "signal " + body)
        ledger = store.load(self.dir, "gus")
        self.assertEqual(ledger.entries[0].get("Context in"), body)
        with open(store.path_for(self.dir, "gus"), "r", encoding="utf-8") as fh:
            self.assert_round_trips(fh.read())

    def test_multiline_body_survives(self):
        body = "first line\nsecond line\n\nfourth line after a blank\n  indented"
        store.append(self.dir, "gus", "ctx", body)
        ledger = store.load(self.dir, "gus")
        self.assertEqual(ledger.entries[0].get("Output"), body)
        with open(store.path_for(self.dir, "gus"), "r", encoding="utf-8") as fh:
            self.assert_round_trips(fh.read())

    def test_hand_written_extras_are_preserved(self):
        # A human adds a stray note line the tool knows nothing about.
        store.append(self.dir, "gus", "ctx", "out")
        path = store.path_for(self.dir, "gus")
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        text = text.replace(
            "- **Signal:** —",
            "- **Signal:** —\n- **Reviewer:** someone else\n\n  a loose paragraph",
        )
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        self.assert_round_trips(text)
        store.rule(self.dir, "gus", 1, "Action", "TAKEN")
        with open(path, "r", encoding="utf-8") as fh:
            after = fh.read()
        self.assertIn("- **Reviewer:** someone else", after)
        self.assertIn("a loose paragraph", after)


class HumanOnlyTests(TempDirCase):
    def test_record_cannot_set_action(self):
        store.append(self.dir, "gus", "ctx", "out")
        entry = store.load(self.dir, "gus").entries[0]
        with self.assertRaises(store.HumanOnlyField):
            entry.set("Action", "TAKEN")

    def test_record_cannot_set_outcome(self):
        store.append(self.dir, "gus", "ctx", "out")
        entry = store.load(self.dir, "gus").entries[0]
        with self.assertRaises(store.HumanOnlyField):
            entry.set("Outcome", "RIGHT")

    def test_case_does_not_get_you_past_the_block(self):
        store.append(self.dir, "gus", "ctx", "out")
        entry = store.load(self.dir, "gus").entries[0]
        for name in ("action", "ACTION", " Outcome "):
            with self.assertRaises(store.HumanOnlyField):
                entry.set(name, "TAKEN")

    def test_append_signature_has_no_action_argument(self):
        import inspect

        params = set(inspect.signature(store.append).parameters)
        self.assertNotIn("action", params)
        self.assertNotIn("outcome", params)

    def test_new_entry_starts_pending_and_open(self):
        store.append(self.dir, "gus", "ctx", "out")
        entry = store.load(self.dir, "gus").entries[0]
        self.assertEqual(entry.action, "PENDING")
        self.assertEqual(entry.outcome, "OPEN")

    def test_rule_refuses_a_non_human_field(self):
        store.append(self.dir, "gus", "ctx", "out")
        with self.assertRaises(store.LedgerError):
            store.rule(self.dir, "gus", 1, "Output", "TAKEN")

    def test_rule_refuses_an_unknown_state(self):
        store.append(self.dir, "gus", "ctx", "out")
        with self.assertRaises(store.LedgerError):
            store.rule(self.dir, "gus", 1, "Action", "MAYBE")


class ErrorTests(TempDirCase):
    def test_acted_on_a_missing_id_errors_cleanly(self):
        store.append(self.dir, "gus", "ctx", "out")
        with self.assertRaises(store.LedgerError) as caught:
            store.rule(self.dir, "gus", 99, "Action", "TAKEN")
        message = str(caught.exception)
        self.assertIn("no run 99", message)
        self.assertIn("runs on file: 1", message)

    def test_acted_on_a_missing_agent_errors_cleanly(self):
        with self.assertRaises(store.LedgerError) as caught:
            store.rule(self.dir, "nobody", 1, "Action", "TAKEN")
        self.assertIn("no ledger", str(caught.exception))

    def test_blank_context_is_refused(self):
        with self.assertRaises(store.LedgerError):
            store.append(self.dir, "gus", "   ", "out")

    def test_bad_agent_name_is_refused(self):
        for bad in ("../escape", "a/b", "", ".hidden"):
            with self.assertRaises(store.LedgerError):
                store.path_for(self.dir, bad)


class IdTests(TempDirCase):
    def test_ids_increment(self):
        self.assertEqual(store.append(self.dir, "gus", "a", "b"), 1)
        self.assertEqual(store.append(self.dir, "gus", "a", "b"), 2)
        self.assertEqual(store.append(self.dir, "gus", "a", "b"), 3)

    def test_ids_are_per_agent(self):
        store.append(self.dir, "gus", "a", "b")
        self.assertEqual(store.append(self.dir, "bob", "a", "b"), 1)

    def test_explicit_dates_are_kept(self):
        store.append(self.dir, "gus", "a", "b", date=datetime.date(2026, 1, 2))
        entry = store.load(self.dir, "gus").entries[0]
        self.assertEqual(entry.date, datetime.date(2026, 1, 2))
        self.assertIn("## 2026-01-02 — run 1", entry.heading)

    def test_note_and_date_land_in_the_action_line(self):
        store.append(self.dir, "gus", "a", "b", date=datetime.date(2026, 1, 2))
        store.rule(
            self.dir, "gus", 1, "Action", "PARTIAL", "half of it",
            date=datetime.date(2026, 1, 5),
        )
        entry = store.load(self.dir, "gus").entries[0]
        state, when, note = entry.state("Action")
        self.assertEqual(state, "PARTIAL")
        self.assertEqual(when, datetime.date(2026, 1, 5))
        self.assertEqual(note, "half of it")


class DiscoveryTests(TempDirCase):
    def test_only_marker_bearing_files_count_as_agents(self):
        store.append(self.dir, "gus", "ctx", "out")
        with open(os.path.join(self.dir, "brief.md"), "w", encoding="utf-8") as fh:
            fh.write("## Your ledger — gus\n\nsome pasted output\n")
        with open(os.path.join(self.dir, "README.md"), "w", encoding="utf-8") as fh:
            fh.write("# notes\n")
        self.assertEqual(store.agents(self.dir), ["gus"])

    def test_missing_directory_is_empty_not_an_error(self):
        self.assertEqual(store.agents(os.path.join(self.dir, "nope")), [])


class TodayTests(unittest.TestCase):
    def test_ledger_today_env_override(self):
        os.environ["LEDGER_TODAY"] = "2026-03-04"
        self.addCleanup(os.environ.pop, "LEDGER_TODAY", None)
        self.assertEqual(store.today(), datetime.date(2026, 3, 4))


if __name__ == "__main__":
    unittest.main()
