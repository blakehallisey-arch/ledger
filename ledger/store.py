"""Read and write the ledger markdown files.

One file per agent, `<dir>/<agent>.md`, plain markdown so it reads fine in a
pull request. This module is code and not a note because two things have to be
true and neither survives on trust alone:

1. Round-trip has to be exact. The file is edited by hand as often as by the
   CLI, so parse-then-write must return the same bytes or hand edits get eaten.
   That is why entries keep their raw lines and a field write rewrites only the
   lines it owns.
2. The Action and Outcome slots are human-only. `record` writes what the agent
   said; only `acted` and `outcome` write what the human did about it. If the
   recording path could touch those two fields the record becomes the agent
   grading itself, and the one signal the tool exists to collect is gone. So
   the block lives here, in the store, not in the CLI argument parser where a
   second caller could walk around it.
"""

import datetime
import os
import re
import tempfile
from contextlib import contextmanager

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX
    fcntl = None

# The two slots no agent may ever write about itself.
HUMAN_ONLY = ("Action", "Outcome")

ACTIONS = ("PENDING", "TAKEN", "REJECTED", "PARTIAL")
OUTCOMES = ("OPEN", "RIGHT", "WRONG", "MIXED")

FIELD_ORDER = ("Context in", "Output", "Signal", "Action", "Outcome")

_HEADING_RE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s+[—-]\s+run\s+(\d+)\s*$")
_FIELD_RE = re.compile(r"^-\s+\*\*([^*]+?):\*\*[ ]?(.*)$")
_STATE_RE = re.compile(
    r"^([A-Z]+)"
    r"(?:\s+\((\d{4}-\d{2}-\d{2})\))?"
    r"(?:\s+—\s+(.*))?$",
    re.S,
)

HEADER = """# {agent} — ledger

What this agent recommended, and what the human did about it.

`Action` and `Outcome` are human-only slots. `ledger record` cannot write them;
only `ledger acted` and `ledger outcome` can. That split is the whole point of
the file — an agent grading its own advice is not a track record.
"""


class LedgerError(Exception):
    """Anything the caller did wrong. The CLI turns this into exit 1."""


class HumanOnlyField(LedgerError):
    """Raised when the recording path tries to write Action or Outcome."""


def today():
    """Today, overridable with LEDGER_TODAY so tests and examples are stable."""
    stamp = os.environ.get("LEDGER_TODAY")
    if stamp:
        return datetime.date.fromisoformat(stamp)
    return datetime.date.today()


def parse_date(value):
    try:
        return datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        raise LedgerError("not a YYYY-MM-DD date: %r" % (value,))


# --------------------------------------------------------------------------
# entries


class Entry(object):
    """One recorded run. `lines` is the raw body, kept so writes are surgical."""

    def __init__(self, date, run_id, heading, lines):
        self.date = date
        self.run_id = run_id
        self.heading = heading
        self.lines = list(lines)

    # -- reading ----------------------------------------------------------

    def _field_span(self, name):
        """Return (start, end) line indexes for a field, or None."""
        target = name.lower()
        for i, line in enumerate(self.lines):
            m = _FIELD_RE.match(line)
            if not m or m.group(1).strip().lower() != target:
                continue
            end = i + 1
            while end < len(self.lines):
                nxt = self.lines[end]
                if nxt.startswith("  ") and not _FIELD_RE.match(nxt):
                    end += 1
                    continue
                break
            return (i, end)
        return None

    def get(self, name, default=None):
        span = self._field_span(name)
        if span is None:
            return default
        start, end = span
        head = _FIELD_RE.match(self.lines[start]).group(2)
        rest = [ln[2:] for ln in self.lines[start + 1:end]]
        return "\n".join([head] + rest)

    def fields(self):
        out = []
        for line in self.lines:
            m = _FIELD_RE.match(line)
            if m:
                out.append(m.group(1).strip())
        return out

    # -- writing ----------------------------------------------------------

    def set(self, name, value, human=False):
        """Write a field. Action/Outcome need human=True; see module docstring."""
        canonical = _canonical_field(name)
        if canonical in HUMAN_ONLY and not human:
            raise HumanOnlyField(
                "%s is a human-only slot — `ledger record` cannot write it. "
                "Use `ledger acted` / `ledger outcome`." % canonical
            )
        new = render_field(canonical, value)
        span = self._field_span(canonical)
        if span is not None:
            start, end = span
            self.lines[start:end] = new
            return
        # Append after the last field line, before any trailing blanks.
        insert = 0
        for i, line in enumerate(self.lines):
            if _FIELD_RE.match(line) or line.startswith("  "):
                insert = i + 1
        self.lines[insert:insert] = new

    # -- interpretation ---------------------------------------------------

    def state(self, name):
        """(STATE, date-or-None, note-or-None) for Action / Outcome."""
        raw = self.get(name)
        if raw is None:
            return (None, None, None)
        m = _STATE_RE.match(raw.strip())
        if not m:
            return (raw.strip().split()[0].upper() if raw.strip() else None, None, None)
        state, stamp, note = m.group(1), m.group(2), m.group(3)
        return (
            state.upper(),
            datetime.date.fromisoformat(stamp) if stamp else None,
            note.strip() if note else None,
        )

    @property
    def action(self):
        return self.state("Action")[0] or "PENDING"

    @property
    def action_date(self):
        return self.state("Action")[1]

    @property
    def outcome(self):
        return self.state("Outcome")[0] or "OPEN"

    def render(self):
        return [self.heading] + list(self.lines)


def _canonical_field(name):
    for known in FIELD_ORDER:
        if known.lower() == name.strip().lower():
            return known
    return name.strip()


def render_field(name, value):
    parts = str(value).split("\n")
    out = ["- **%s:** %s" % (name, parts[0])]
    for part in parts[1:]:
        out.append("  " + part)
    return out


def render_state(state, when=None, note=None):
    text = state.upper()
    if when is not None:
        text += " (%s)" % when.isoformat()
    if note:
        text += " — " + note
    return text


# --------------------------------------------------------------------------
# whole files


class Ledger(object):
    """A parsed agent file: a preamble, then entries."""

    def __init__(self, agent, preamble, entries):
        self.agent = agent
        self.preamble = list(preamble)
        self.entries = list(entries)

    def render(self):
        lines = list(self.preamble)
        for entry in self.entries:
            lines.extend(entry.render())
        return "\n".join(lines)

    def get(self, run_id):
        for entry in self.entries:
            if entry.run_id == run_id:
                return entry
        return None

    def next_run_id(self):
        if not self.entries:
            return 1
        return max(e.run_id for e in self.entries) + 1


def parse(text, agent="agent"):
    lines = text.split("\n")
    preamble = []
    entries = []
    current = None
    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            if current is not None:
                entries.append(current)
            current = Entry(
                datetime.date.fromisoformat(m.group(1)),
                int(m.group(2)),
                line,
                [],
            )
            continue
        if current is None:
            preamble.append(line)
        else:
            current.lines.append(line)
    if current is not None:
        entries.append(current)
    return Ledger(agent, preamble, entries)


def render(ledger):
    return ledger.render()


# --------------------------------------------------------------------------
# disk


def path_for(directory, agent):
    safe = str(agent).strip()
    if not safe or "/" in safe or "\\" in safe or safe.startswith("."):
        raise LedgerError("bad agent name: %r" % (agent,))
    return os.path.join(directory, safe + ".md")


def load(directory, agent):
    path = path_for(directory, agent)
    if not os.path.exists(path):
        raise LedgerError("no ledger for %r (looked in %s)" % (agent, directory))
    with open(path, "r", encoding="utf-8") as fh:
        return parse(fh.read(), agent)


def load_or_new(directory, agent):
    try:
        return load(directory, agent)
    except LedgerError:
        return parse(HEADER.format(agent=agent), agent)


_LEDGER_TITLE_RE = re.compile(r"^#\s+.+\s+[—-]\s+ledger\s*$")


def is_ledger_file(path):
    """A ledger is a .md whose first non-blank line is `# <agent> — ledger`.

    The marker line is what keeps a stray README or a pasted brief in the same
    directory from being counted as an agent with zero runs. Cheap, and it only
    reads the top of the file.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for _ in range(20):
                line = fh.readline()
                if not line:
                    return False
                if line.strip():
                    return bool(_LEDGER_TITLE_RE.match(line.rstrip("\n")))
    except OSError:
        return False
    return False


def agents(directory):
    if not os.path.isdir(directory):
        return []
    names = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".md") or name.startswith("."):
            continue
        if is_ledger_file(os.path.join(directory, name)):
            names.append(name[:-3])
    return names


def save(directory, ledger):
    """Atomic replace. Callers hold the lock; this only makes the swap clean."""
    path = path_for(directory, ledger.agent)
    text = ledger.render()
    fd, tmp = tempfile.mkstemp(dir=directory or ".", prefix=".ledger-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


@contextmanager
def locked(directory, agent):
    """Exclusive lock on one agent's file.

    Two sessions recording against the same agent at the same moment is normal
    — an orchestrator fans out and both returns land together. Without this
    both read run 7, both write run 8, and one entry is gone with no error
    anywhere. flock where we have it; a mkdir spinlock where we do not.
    """
    if directory and not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)
    lock_path = path_for(directory, agent) + ".lock"
    if fcntl is not None:
        fh = open(lock_path, "a+")
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            finally:
                fh.close()
    else:  # pragma: no cover - non-POSIX
        import time

        spin = lock_path + ".d"
        for _ in range(2000):
            try:
                os.mkdir(spin)
                break
            except FileExistsError:
                time.sleep(0.005)
        else:
            raise LedgerError("could not take the lock on %s" % lock_path)
        try:
            yield
        finally:
            try:
                os.rmdir(spin)
            except OSError:
                pass


def append(directory, agent, context, output, signal=None, date=None):
    """Record one run. Returns the new run id.

    Deliberately takes no action/outcome argument. There is no keyword to pass
    and no field to override — the only way into those slots is the human
    verbs.
    """
    if not context or not str(context).strip():
        raise LedgerError("--context is required and cannot be blank")
    if not output or not str(output).strip():
        raise LedgerError("--output is required and cannot be blank")
    when = date or today()
    with locked(directory, agent):
        ledger = load_or_new(directory, agent)
        run_id = ledger.next_run_id()
        entry = Entry(when, run_id, "## %s — run %d" % (when.isoformat(), run_id), [])
        entry.set("Context in", context)
        entry.set("Output", output)
        entry.set("Signal", signal if signal else "—")
        entry.set("Action", "PENDING", human=True)
        entry.set("Outcome", "OPEN", human=True)
        entry.lines.append("")
        if ledger.entries:
            pass
        elif ledger.preamble and ledger.preamble[-1] != "":
            ledger.preamble.append("")
        ledger.entries.append(entry)
        save(directory, ledger)
    return run_id


def rule(directory, agent, run_id, field, state, note=None, date=None):
    """Write a human-only slot. The only door into Action and Outcome."""
    field = _canonical_field(field)
    if field not in HUMAN_ONLY:
        raise LedgerError("%s is not a human-only slot" % field)
    allowed = ACTIONS if field == "Action" else OUTCOMES
    if state.upper() not in allowed:
        raise LedgerError("%s must be one of %s" % (field, ", ".join(allowed)))
    when = date or today()
    with locked(directory, agent):
        ledger = load(directory, agent)
        entry = ledger.get(run_id)
        if entry is None:
            have = ", ".join(str(e.run_id) for e in ledger.entries) or "none"
            raise LedgerError(
                "%s has no run %s (runs on file: %s)" % (agent, run_id, have)
            )
        entry.set(field, render_state(state, when, note), human=True)
        save(directory, ledger)
    return entry
