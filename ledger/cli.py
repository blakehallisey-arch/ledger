"""The command line.

Five verbs, and the split between them is the design:

  record   — what the agent said. An agent or an orchestrator may run this.
  acted    — what the human did about it. Human only.
  outcome  — whether it worked. Human only.
  open     — the nag: advice nobody ruled on.
  scorecard / brief — the reads.

`record` has no --taken and no --right flag. Not hidden, not ignored: absent.
The store refuses those fields as well, so a second caller importing the
library cannot walk around the argument parser.

Exit codes: 0 fine, 1 the caller got something wrong, 2 argparse usage error.
"""

import argparse
import json
import os
import sys

from . import config, report, store

VERSION = "0.1.0"


def _read_body(value, stdin_name):
    """Accept a literal string, `-` for stdin, or `@path` for a file."""
    if value is None:
        return None
    if value == "-":
        return sys.stdin.read().rstrip("\n")
    if value.startswith("@"):
        path = value[1:]
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().rstrip("\n")
    return value


def _body(args, name):
    literal = getattr(args, name)
    from_file = getattr(args, name + "_file", None)
    if literal and from_file:
        raise store.LedgerError("give --%s or --%s-file, not both" % (name, name))
    if from_file:
        with open(from_file, "r", encoding="utf-8") as fh:
            return fh.read().rstrip("\n")
    return _read_body(literal, name)


def _date(args):
    value = getattr(args, "date", None)
    return store.parse_date(value) if value else None


# --------------------------------------------------------------------------
# commands


def cmd_init(args, directory):
    os.makedirs(directory, exist_ok=True)
    conf_path = os.path.join(os.getcwd(), config.CONFIG_NAME)
    made = []
    if not os.path.exists(conf_path):
        rel = os.path.relpath(directory, os.getcwd())
        with open(conf_path, "w", encoding="utf-8") as fh:
            json.dump({"dir": rel}, fh, indent=2)
            fh.write("\n")
        made.append(conf_path)
    print("ledger dir: %s" % directory)
    for path in made:
        print("wrote:      %s" % path)
    print("")
    print("Record a run:  ledger record <agent> --context \"...\" --output \"...\"")
    print("Rule on it:    ledger acted <agent> <id> --taken|--rejected|--partial")
    print("Feed it back:  ledger brief <agent>")
    return 0


def cmd_record(args, directory):
    run_id = store.append(
        directory,
        args.agent,
        _body(args, "context"),
        _body(args, "output"),
        _body(args, "signal"),
        date=_date(args),
    )
    if args.json:
        print(json.dumps({"agent": args.agent, "id": run_id}))
    else:
        print("%s run %d recorded — PENDING." % (args.agent, run_id))
        print("Rule on it with: ledger acted %s %d --taken|--rejected|--partial"
              % (args.agent, run_id))
    return 0


def cmd_acted(args, directory):
    state = (
        "TAKEN" if args.taken else "REJECTED" if args.rejected else "PARTIAL"
    )
    store.rule(directory, args.agent, args.id, "Action", state, args.note, _date(args))
    print("%s run %d — %s." % (args.agent, args.id, state))
    return 0


def cmd_outcome(args, directory):
    state = "RIGHT" if args.right else "WRONG" if args.wrong else "MIXED"
    store.rule(directory, args.agent, args.id, "Outcome", state, args.note, _date(args))
    print("%s run %d — outcome %s." % (args.agent, args.id, state))
    return 0


def cmd_open(args, directory):
    rows = report.open_entries(directory, args.agent)
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(report.format_open(rows))
    return 0


def cmd_scorecard(args, directory):
    rows = report.scorecard(directory, args.agent)
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(report.format_scorecard(rows))
    return 0


def cmd_brief(args, directory):
    print(report.brief(directory, args.agent, args.last))
    return 0


# --------------------------------------------------------------------------
# parser


def build_parser():
    parser = argparse.ArgumentParser(
        prog="ledger",
        description="A memory of what you did with each agent's advice.",
    )
    parser.add_argument("--version", action="version", version="ledger " + VERSION)
    parser.add_argument("--dir", help="where the agent .md files live (default: ledger/)")
    subs = parser.add_subparsers(dest="cmd")

    p = subs.add_parser("init", help="create the ledger directory and ledger.json")
    p.set_defaults(func=cmd_init)

    p = subs.add_parser(
        "record",
        help="append a run: what the agent was given and what it recommended",
        description="Records what the agent said. It cannot record what you did "
                    "about it — that is `ledger acted`, on purpose.",
    )
    p.add_argument("agent")
    p.add_argument("--context", help="what it was given and asked ('-' for stdin)")
    p.add_argument("--context-file", help="read the context body from a file")
    p.add_argument("--output", help="what it recommended, compressed to the claim")
    p.add_argument("--output-file", help="read the output body from a file")
    p.add_argument("--signal", help="what was notable: missed, nailed, assumed")
    p.add_argument("--signal-file", help="read the signal body from a file")
    p.add_argument("--date", help="record it under this date (YYYY-MM-DD)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_record)

    p = subs.add_parser("acted", help="human only: what you did with the advice")
    p.add_argument("agent")
    p.add_argument("id", type=int)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--taken", action="store_true")
    g.add_argument("--rejected", action="store_true")
    g.add_argument("--partial", action="store_true")
    p.add_argument("--note")
    p.add_argument("--date", help="rule it under this date (YYYY-MM-DD)")
    p.set_defaults(func=cmd_acted)

    p = subs.add_parser("outcome", help="human only: did it turn out right")
    p.add_argument("agent")
    p.add_argument("id", type=int)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--right", action="store_true")
    g.add_argument("--wrong", action="store_true")
    g.add_argument("--mixed", action="store_true")
    p.add_argument("--note")
    p.add_argument("--date", help="rule it under this date (YYYY-MM-DD)")
    p.set_defaults(func=cmd_outcome)

    p = subs.add_parser("open", help="every entry still PENDING, oldest first")
    p.add_argument("agent", nargs="?")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_open)

    p = subs.add_parser("scorecard", help="runs, take rate, and how the taken ones went")
    p.add_argument("agent", nargs="?")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_scorecard)

    p = subs.add_parser(
        "brief",
        help="markdown to paste into that agent's system prompt",
    )
    p.add_argument("agent")
    p.add_argument("--last", type=int, default=8, help="how many entries (default 8)")
    p.set_defaults(func=cmd_brief)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    try:
        directory = config.resolve_dir(args.dir)
        return args.func(args, directory)
    except store.LedgerError as exc:
        sys.stderr.write("ledger: %s\n" % exc)
        return 1
    except (OSError, ValueError) as exc:
        sys.stderr.write("ledger: %s\n" % exc)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
