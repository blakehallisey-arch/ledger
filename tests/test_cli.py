"""The CLI, including the flags that must not exist on `record`."""

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest

from ledger import cli, store


def run(argv, directory):
    """Run the CLI against a directory. Returns (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    old = os.environ.get("LEDGER_DIR")
    os.environ["LEDGER_DIR"] = directory
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = cli.main(argv)
            except SystemExit as exc:  # argparse usage errors
                code = exc.code if isinstance(exc.code, int) else 2
    finally:
        if old is None:
            os.environ.pop("LEDGER_DIR", None)
        else:
            os.environ["LEDGER_DIR"] = old
    return code, out.getvalue(), err.getvalue()


class CliCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ledger-cli-")
        self.addCleanup(shutil.rmtree, self.dir, True)

    def run_cli(self, *argv):
        return run(list(argv), self.dir)


class RecordCannotRuleTests(CliCase):
    def test_record_has_no_taken_flag(self):
        self.run_cli("record", "gus", "--context", "c", "--output", "o")
        code, _, err = self.run_cli(
            "record", "gus", "--context", "c", "--output", "o", "--taken"
        )
        self.assertNotEqual(code, 0)
        self.assertIn("unrecognized arguments", err)

    def test_record_has_no_action_or_outcome_flag(self):
        for flag in ("--action", "--outcome", "--right", "--rejected"):
            code, _, err = self.run_cli(
                "record", "gus", "--context", "c", "--output", "o", flag, "TAKEN"
            )
            self.assertNotEqual(code, 0, flag)
            self.assertIn("unrecognized arguments", err)

    def test_recorded_entry_is_pending(self):
        code, out, _ = self.run_cli("record", "gus", "--context", "c", "--output", "o")
        self.assertEqual(code, 0)
        self.assertIn("PENDING", out)
        self.assertEqual(store.load(self.dir, "gus").entries[0].action, "PENDING")


class RecordTests(CliCase):
    def test_prints_the_new_id(self):
        code, out, _ = self.run_cli(
            "record", "gus", "--context", "c", "--output", "o", "--json"
        )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["id"], 1)
        _, out2, _ = self.run_cli(
            "record", "gus", "--context", "c", "--output", "o", "--json"
        )
        self.assertEqual(json.loads(out2)["id"], 2)

    def test_body_from_a_file(self):
        path = os.path.join(self.dir, "body.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("a long\nmulti-line body\n")
        code, _, err = self.run_cli(
            "record", "gus", "--context", "c", "--output-file", path
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(
            store.load(self.dir, "gus").entries[0].get("Output"),
            "a long\nmulti-line body",
        )

    def test_at_path_shorthand(self):
        path = os.path.join(self.dir, "body2.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("from @path\n")
        code, _, err = self.run_cli(
            "record", "gus", "--context", "c", "--output", "@" + path
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(store.load(self.dir, "gus").entries[0].get("Output"), "from @path")

    def test_missing_output_errors_cleanly(self):
        code, _, err = self.run_cli("record", "gus", "--context", "c")
        self.assertEqual(code, 1)
        self.assertIn("--output is required", err)


class RulingTests(CliCase):
    def test_acted_then_outcome(self):
        self.run_cli("record", "gus", "--context", "c", "--output", "o")
        code, out, err = self.run_cli("acted", "gus", "1", "--taken", "--note", "did it")
        self.assertEqual(code, 0, err)
        self.assertIn("TAKEN", out)
        code, out, err = self.run_cli("outcome", "gus", "1", "--right")
        self.assertEqual(code, 0, err)
        entry = store.load(self.dir, "gus").entries[0]
        self.assertEqual(entry.action, "TAKEN")
        self.assertEqual(entry.outcome, "RIGHT")

    def test_acted_on_a_missing_id_exits_one(self):
        self.run_cli("record", "gus", "--context", "c", "--output", "o")
        code, _, err = self.run_cli("acted", "gus", "42", "--taken")
        self.assertEqual(code, 1)
        self.assertIn("no run 42", err)
        self.assertNotIn("Traceback", err)

    def test_acted_on_a_missing_agent_exits_one(self):
        code, _, err = self.run_cli("acted", "nobody", "1", "--taken")
        self.assertEqual(code, 1)
        self.assertIn("no ledger", err)

    def test_acted_needs_exactly_one_verdict(self):
        self.run_cli("record", "gus", "--context", "c", "--output", "o")
        code, _, _ = self.run_cli("acted", "gus", "1")
        self.assertNotEqual(code, 0)
        code, _, _ = self.run_cli("acted", "gus", "1", "--taken", "--rejected")
        self.assertNotEqual(code, 0)


class ReadTests(CliCase):
    def seed(self):
        self.run_cli("record", "gus", "--date", "2026-01-01",
                     "--context", "c", "--output", "first")
        self.run_cli("record", "gus", "--date", "2026-01-05",
                     "--context", "c", "--output", "second")
        self.run_cli("acted", "gus", "2", "--taken", "--date", "2026-01-06")

    def test_open_json(self):
        self.seed()
        code, out, err = self.run_cli("open", "--json")
        self.assertEqual(code, 0, err)
        rows = json.loads(out)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["run"], 1)

    def test_scorecard_json(self):
        self.seed()
        code, out, err = self.run_cli("scorecard", "--json")
        self.assertEqual(code, 0, err)
        rows = json.loads(out)
        self.assertEqual(rows[0]["agent"], "gus")
        self.assertEqual(rows[0]["runs"], 2)

    def test_brief_is_markdown(self):
        self.seed()
        code, out, err = self.run_cli("brief", "gus")
        self.assertEqual(code, 0, err)
        self.assertIn("## Your ledger — gus", out)
        self.assertIn("What your record says about you", out)

    def test_scorecard_on_an_empty_dir(self):
        code, out, _ = self.run_cli("scorecard")
        self.assertEqual(code, 0)
        self.assertIn("no agents recorded yet", out)


class InitTests(unittest.TestCase):
    def test_init_creates_the_dir_and_config(self):
        root = os.path.realpath(tempfile.mkdtemp(prefix="ledger-init-"))
        self.addCleanup(shutil.rmtree, root, True)
        cwd = os.getcwd()
        os.chdir(root)
        try:
            code, out, err = run(["init"], os.path.join(root, "ledger"))
        finally:
            os.chdir(cwd)
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.isdir(os.path.join(root, "ledger")))
        with open(os.path.join(root, "ledger.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["dir"], "ledger")
        self.assertIn("ledger acted", out)


if __name__ == "__main__":
    unittest.main()
