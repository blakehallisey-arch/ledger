"""The reads: open, scorecard, brief.

This is code and not a spreadsheet because the numbers have to stay honest
under a small sample. A take rate of 100% off two rulings is not a track
record, and a report that prints it without saying so is worse than no report
— someone will quote it. Every read here carries its own sample size and
flags itself when there is not enough to mean anything.

`brief` is the half that closes the loop: it emits a markdown block you paste
into the agent's system prompt so the next stateless run starts knowing what
happened to the last ten.
"""

import re
import statistics

from . import store

SMALL_SAMPLE = 5

_STOPWORDS = set(
    """
    the a an and or but for nor so yet of to in on at by with from into over
    under this that these those it its it's is are was were be been being do
    does did have has had will would should could can may might must not no
    if then than as about after before again all any both each few more most
    other some such only own same too very just now here there when where why
    how what which who whom you your we our they them their he she his her i
    me my mine us out up down off out again further once because while during
    against between through above below use used using make makes made get
    gets got give gives given put puts take takes taken thing things one two
    three next last first also still even much many way ways new old
    """.split()
)


def _tokens(text):
    words = re.findall(r"[a-z][a-z0-9'-]{2,}", (text or "").lower())
    return set(w for w in words if w not in _STOPWORDS and len(w) >= 4)


# --------------------------------------------------------------------------
# open


def open_entries(directory, agent=None, as_of=None):
    """Every entry still PENDING, oldest first, with how long it has sat."""
    as_of = as_of or store.today()
    names = [agent] if agent else store.agents(directory)
    rows = []
    for name in names:
        ledger = store.load(directory, name)
        for entry in ledger.entries:
            if entry.action != "PENDING":
                continue
            rows.append(
                {
                    "agent": name,
                    "run": entry.run_id,
                    "date": entry.date.isoformat(),
                    "days_open": (as_of - entry.date).days,
                    "output": entry.get("Output", ""),
                    "context": entry.get("Context in", ""),
                }
            )
    rows.sort(key=lambda r: (r["date"], r["agent"], r["run"]))
    return rows


def format_open(rows, as_of=None):
    as_of = as_of or store.today()
    if not rows:
        return "ledger — nothing open. Every entry has been ruled on."
    out = ["ledger — open entries  (as of %s)" % as_of.isoformat(), ""]
    width = max(len(r["agent"]) for r in rows)
    for row in rows:
        out.append(
            "%s  run %-4s %s  %3d days open"
            % (
                row["agent"].ljust(width),
                row["run"],
                row["date"],
                row["days_open"],
            )
        )
        out.append("    %s" % _one_line(row["output"], 88))
    out.append("")
    out.append(
        "%d entry(s) you have not ruled on. `ledger acted <agent> <id> --taken|"
        "--rejected|--partial`" % len(rows)
    )
    return "\n".join(out)


def _one_line(text, limit):
    flat = " ".join((text or "").split())
    if len(flat) <= limit:
        return flat
    cut = flat[: limit - 1]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut + "…"


# --------------------------------------------------------------------------
# scorecard


def score_agent(directory, agent, as_of=None):
    as_of = as_of or store.today()
    ledger = store.load(directory, agent)
    counts = {"TAKEN": 0, "REJECTED": 0, "PARTIAL": 0, "PENDING": 0}
    outcomes = {"RIGHT": 0, "WRONG": 0, "MIXED": 0, "OPEN": 0}
    lags = []
    for entry in ledger.entries:
        action = entry.action
        counts[action] = counts.get(action, 0) + 1
        if action == "PENDING":
            continue
        if entry.action_date:
            lags.append((entry.action_date - entry.date).days)
        if action == "TAKEN":
            outcomes[entry.outcome] = outcomes.get(entry.outcome, 0) + 1
    ruled = counts["TAKEN"] + counts["REJECTED"] + counts["PARTIAL"]
    judged = outcomes["RIGHT"] + outcomes["WRONG"] + outcomes["MIXED"]
    return {
        "agent": agent,
        "runs": len(ledger.entries),
        "taken": counts["TAKEN"],
        "rejected": counts["REJECTED"],
        "partial": counts["PARTIAL"],
        "pending": counts["PENDING"],
        "ruled": ruled,
        "take_rate": (counts["TAKEN"] / ruled) if ruled else None,
        "outcome_right": outcomes["RIGHT"],
        "outcome_wrong": outcomes["WRONG"],
        "outcome_mixed": outcomes["MIXED"],
        "outcome_open": outcomes["OPEN"],
        "outcome_judged": judged,
        "right_rate": (outcomes["RIGHT"] / judged) if judged else None,
        "median_days_to_ruling": statistics.median(lags) if lags else None,
        "small_sample": ruled < SMALL_SAMPLE,
    }


def scorecard(directory, agent=None, as_of=None):
    names = [agent] if agent else store.agents(directory)
    rows = [score_agent(directory, name, as_of) for name in names]
    # Rank by take rate, agents with no rulings at the bottom.
    rows.sort(key=lambda r: (r["take_rate"] is None, -(r["take_rate"] or 0), r["agent"]))
    return rows


def _pct(value):
    return "—" if value is None else "%d%%" % round(value * 100)


def format_scorecard(rows, as_of=None):
    as_of = as_of or store.today()
    if not rows:
        return "ledger — no agents recorded yet. `ledger record <agent> ...`"
    head = ["agent", "runs", "taken", "rej", "part", "pend", "take rate", "of taken", "med days"]
    table = [head]
    for row in rows:
        if row["outcome_judged"]:
            taken_read = "%d/%d right" % (row["outcome_right"], row["outcome_judged"])
        else:
            taken_read = "—"
        table.append(
            [
                row["agent"] + ("*" if row["small_sample"] else ""),
                str(row["runs"]),
                str(row["taken"]),
                str(row["rejected"]),
                str(row["partial"]),
                str(row["pending"]),
                _pct(row["take_rate"]),
                taken_read,
                "—"
                if row["median_days_to_ruling"] is None
                else ("%g" % row["median_days_to_ruling"]),
            ]
        )
    widths = [max(len(r[i]) for r in table) for i in range(len(head))]
    lines = ["ledger — scorecard  (as of %s)" % as_of.isoformat(), ""]
    for i, row in enumerate(table):
        cells = [row[0].ljust(widths[0])]
        cells += [row[j].rjust(widths[j]) for j in range(1, len(head))]
        lines.append("  ".join(cells).rstrip())
        if i == 0:
            lines.append("  ".join("-" * w for w in widths))
    if any(r["small_sample"] for r in rows):
        lines.append("")
        lines.append(
            "* fewer than %d rulings. The numbers are printed as recorded; they are"
            % SMALL_SAMPLE
        )
        lines.append("  too few to mean anything yet. Do not quote them.")
    total_pending = sum(r["pending"] for r in rows)
    if total_pending:
        lines.append("")
        lines.append(
            "%d entry(s) still PENDING across %d agent(s). `ledger open`"
            % (total_pending, len(rows))
        )
    return "\n".join(lines)


# --------------------------------------------------------------------------
# brief — the feedback half


def _rejection_pattern(taken_texts, rejected_texts):
    """Words that show up across the rejected advice and not the taken advice.

    Deliberately dumb. It reports overlap in wording, nothing more, and it
    keeps quiet unless there are at least three rejections to overlap. A made-up
    pattern in an agent's own system prompt is worse than silence — the agent
    will believe it.
    """
    if len(rejected_texts) < 3:
        return []
    rej_sets = [_tokens(t) for t in rejected_texts]
    take_sets = [_tokens(t) for t in taken_texts]
    hits = []
    vocab = set()
    for s in rej_sets:
        vocab |= s
    for word in vocab:
        rej_frac = sum(1 for s in rej_sets if word in s) / len(rej_sets)
        take_frac = (
            sum(1 for s in take_sets if word in s) / len(take_sets) if take_sets else 0.0
        )
        if rej_frac >= 0.6 and take_frac <= 0.2:
            hits.append((rej_frac - take_frac, rej_frac, word))
    hits.sort(reverse=True)
    return [(w, rf) for _, rf, w in hits[:4]]


def brief(directory, agent, last=8, as_of=None):
    as_of = as_of or store.today()
    ledger = store.load(directory, agent)
    entries = ledger.entries[-last:] if last else list(ledger.entries)
    total = len(ledger.entries)

    lines = []
    lines.append("## Your ledger — %s" % agent)
    lines.append("")
    lines.append(
        "Someone records what you recommended and, later, what they actually did "
        "about it. You cannot write those last two fields. This is the record as "
        "of %s — your last %d run(s) of %d."
        % (as_of.isoformat(), len(entries), total)
    )
    lines.append("")
    lines.append("### The runs")
    lines.append("")
    if not entries:
        lines.append("- Nothing recorded yet.")
    for entry in entries:
        state, when, note = entry.state("Action")
        state = state or "PENDING"
        tail = state
        if state == "PENDING":
            tail += " (%d days)" % (as_of - entry.date).days
        out_state = entry.outcome
        if state == "TAKEN" and out_state != "OPEN":
            tail += " → turned out %s" % out_state
        lines.append("- **run %d** (%s) — %s" % (entry.run_id, entry.date.isoformat(), tail))
        lines.append("  - asked: %s" % _one_line(entry.get("Context in", ""), 160))
        lines.append("  - you said: %s" % _one_line(entry.get("Output", ""), 200))
        sig = _one_line(entry.get("Signal", ""), 160)
        if sig and sig != "—":
            lines.append("  - noted: %s" % sig)
        if note:
            lines.append("  - they said: %s" % _one_line(note, 160))

    lines.append("")
    lines.append("### What your record says about you")
    lines.append("")
    lines.extend("- " + line for line in _record_says(entries, as_of))
    lines.append("")
    lines.append(
        "Read that before you answer. Do not re-serve advice this record shows was "
        "already turned down, unless something in the new context actually changed."
    )
    return "\n".join(lines)


def _record_says(entries, as_of):
    said = []
    counts = {"TAKEN": 0, "REJECTED": 0, "PARTIAL": 0, "PENDING": 0}
    for entry in entries:
        counts[entry.action] = counts.get(entry.action, 0) + 1
    ruled = counts["TAKEN"] + counts["REJECTED"] + counts["PARTIAL"]
    n = len(entries)
    if not n:
        return ["No entries yet. Nothing to say about your record."]

    said.append(
        "Of these %d run(s): %d taken, %d rejected, %d partial, %d never ruled on."
        % (n, counts["TAKEN"], counts["REJECTED"], counts["PARTIAL"], counts["PENDING"])
    )

    if ruled < SMALL_SAMPLE:
        said.append(
            "Only %d ruling(s) here. That is too few to be a pattern — treat the "
            "counts above as anecdotes, not as a track record." % ruled
        )
    else:
        rate = counts["TAKEN"] / ruled
        if rate >= 0.7:
            said.append(
                "Take rate %d%% of %d rulings. Your recommendations mostly get used. "
                "Keep the shape you have been using." % (round(rate * 100), ruled)
            )
        elif rate <= 0.35:
            said.append(
                "Take rate %d%% of %d rulings. Most of what you recommend is being "
                "turned down. Something about the shape of your advice is wrong, not "
                "just the details." % (round(rate * 100), ruled)
            )
        else:
            said.append(
                "Take rate %d%% of %d rulings. Mixed — about half your advice lands."
                % (round(rate * 100), ruled)
            )

    judged = [e for e in entries if e.action == "TAKEN" and e.outcome != "OPEN"]
    if judged:
        right = sum(1 for e in judged if e.outcome == "RIGHT")
        wrong = sum(1 for e in judged if e.outcome == "WRONG")
        mixed = sum(1 for e in judged if e.outcome == "MIXED")
        if len(judged) < SMALL_SAMPLE:
            said.append(
                "Of the taken ones, %d %s a verdict: %d right, %d wrong, %d mixed. "
                "Too few to trust."
                % (len(judged), "has" if len(judged) == 1 else "have", right, wrong, mixed)
            )
        else:
            said.append(
                "Of the taken ones with a verdict (%d): %d right, %d wrong, %d mixed."
                % (len(judged), right, wrong, mixed)
            )
    else:
        said.append(
            "None of the taken advice has a verdict yet, so nothing here says whether "
            "you were right — only whether you were used."
        )

    lags = [
        (e.action_date - e.date).days
        for e in entries
        if e.action != "PENDING" and e.action_date
    ]
    if lags:
        said.append(
            "Median %g day(s) from your run to a ruling." % statistics.median(lags)
        )

    pattern = _rejection_pattern(
        [e.get("Output", "") for e in entries if e.action == "TAKEN"],
        [e.get("Output", "") for e in entries if e.action == "REJECTED"],
    )
    rejected_n = counts["REJECTED"]
    if rejected_n >= 3:
        if pattern:
            words = ", ".join(
                '"%s" (%d of %d)' % (w, round(f * rejected_n), rejected_n)
                for w, f in pattern
            )
            said.append(
                "The rejected ones share wording the taken ones do not: %s. That is "
                "word overlap, not a diagnosis — but it is where to look first."
                % words
            )
        else:
            said.append(
                "The %d rejected runs share no wording the taken ones lack. There is "
                "no pattern in the text; if there is a pattern it is in the judgment, "
                "and this tool cannot see it." % rejected_n
            )

    if counts["PENDING"]:
        oldest = min(
            (as_of - e.date).days for e in entries if e.action == "PENDING"
        )
        said.append(
            "%d of these %s never ruled on (oldest %d days). Silence is not "
            "agreement — it usually means the advice was quietly skipped."
            % (counts["PENDING"], "was" if counts["PENDING"] == 1 else "were", oldest)
        )
    return said
