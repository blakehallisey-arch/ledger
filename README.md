# ledger

Gives stateless agents a memory of what you actually did with their advice.

## The problem

A shop of a dozen specialist subagents. Each one gets spun up, reads the same
files, hands back a recommendation, and dies. The next run starts from zero
with the same blind spots, because there is nowhere for it to have learned
anything.

The signal that would fix that exists every single time and evaporates every
single time: what the human did next. One of the agents kept recommending the
same category of thing — big rewrites, migrate this onto that — and the human
kept quietly not doing it. Not arguing with it, not correcting the prompt.
Just closing the terminal and doing something smaller. That went on for months.
Nobody ever wrote it down, so the agent kept making the recommendation, and
every month somebody read a two-week rewrite proposal and moved on.

The interesting part is that an agent's track record is not its output. It is
the gap between its output and what happened next. `ledger` writes that gap
down, one markdown file per agent, and hands it back to the agent on the next
run.

## Install

```sh
git clone https://github.com/blakehallisey-arch/ledger && cd ledger && ./install.sh
python3 -m ledger init
```

No dependencies. Python 3.9+, standard library only.

## What it looks like

Record what an agent said. This is the only verb an agent or an orchestrator
should ever run:

```
$ ledger record architect \
    --context "Monthly portfolio review, 14 builds" \
    --output "Introduce an event bus and migrate the four cron rails onto it" \
    --signal "Did not check whether the overlap actually causes a problem"
architect run 8 recorded — PENDING.
Rule on it with: ledger acted architect 8 --taken|--rejected|--partial
```

Later, you rule on it. These two verbs are yours:

```
$ ledger acted architect 8 --rejected --note "the overlap has never once collided"
architect run 8 — REJECTED.

$ ledger outcome architect 9 --right
architect run 9 — outcome RIGHT.
```

The nag — advice nobody ever ruled on:

```
$ ledger open
ledger — open entries  (as of 2026-08-14)

architect  run 10   2026-08-11    3 days open
    Split the reporting layer into its own package with a versioned interface
sweeper    run 10   2026-08-12    2 days open
    Three lint rails have been red continuously for nine days; nobody is reading them

2 entry(s) you have not ruled on. `ledger acted <agent> <id> --taken|--rejected|--partial`
```

The read. This is real output over `examples/`, two agents, ten runs each:

```
$ ledger scorecard
ledger — scorecard  (as of 2026-08-14)

agent      runs  taken  rej  part  pend  take rate   of taken  med days
---------  ----  -----  ---  ----  ----  ---------  ---------  --------
sweeper      10      8    0     1     1        89%  6/8 right         1
architect    10      2    7     0     1        22%  2/2 right         1

2 entry(s) still PENDING across 2 agent(s). `ledger open`
```

And the half the whole thing is for. `brief` emits a markdown block you paste
into that agent's system prompt, or hand it at the start of a run:

```
$ ledger brief architect --last 6
## Your ledger — architect

Someone records what you recommended and, later, what they actually did about it. You cannot write those last two fields. This is the record as of 2026-08-14 — your last 6 run(s) of 10.

### The runs

- **run 5** (2026-07-18) — REJECTED
  - asked: Monthly portfolio review, 14 builds
  - you said: Stand up a service boundary between the scheduler and the workers — a rewrite of both call paths
  - noted: No scaling pressure named anywhere in the inputs
  - they said: one machine, one user
- **run 6** (2026-07-24) — REJECTED
  - asked: The config file has grown to 40 keys
  - you said: Migrate the whole config layer to a schema-validated format and rewrite the readers
  - noted: The reported pain was one typo, once
- **run 7** (2026-07-30) — REJECTED
  - asked: Retry logic is duplicated in six places
  - you said: Replace the hand-rolled retry logic with a general-purpose framework and migrate all six callers
  - noted: Four of the six have different backoff needs
  - they said: hoisted one shared helper instead
- **run 8** (2026-08-04) — REJECTED
  - asked: Four cron rails fire on overlapping schedules
  - you said: Introduce an event bus and migrate the four cron rails onto it
  - noted: Did not check whether the overlap actually causes a problem
  - they said: the overlap has never once collided
- **run 9** (2026-08-07) — TAKEN → turned out RIGHT
  - asked: Deploys are failing silently
  - you said: Make the deploy check read the artifact timestamp instead of the exit code
  - noted: The exit code was always 0; the check has never been meaningful
- **run 10** (2026-08-11) — PENDING (3 days)
  - asked: Monthly portfolio review, 14 builds
  - you said: Split the reporting layer into its own package with a versioned interface
  - noted: One consumer today; the versioned interface is for consumers that do not exist

### What your record says about you

- Of these 6 run(s): 1 taken, 4 rejected, 0 partial, 1 never ruled on.
- Take rate 20% of 5 rulings. Most of what you recommend is being turned down. Something about the shape of your advice is wrong, not just the details.
- Of the taken ones, 1 has a verdict: 1 right, 0 wrong, 0 mixed. Too few to trust.
- Median 1 day(s) from your run to a ruling.
- The rejected ones share wording the taken ones do not: "migrate" (3 of 4). That is word overlap, not a diagnosis — but it is where to look first.
- 1 of these was never ruled on (oldest 3 days). Silence is not agreement — it usually means the advice was quietly skipped.

Read that before you answer. Do not re-serve advice this record shows was already turned down, unless something in the new context actually changed.
```

That last block is the thing. The agent is still stateless. It just starts the
run holding its own record.

## How it works

### The record

One markdown file per agent, `ledger/<agent>.md`. Plain markdown because the
file has to be readable in a pull request diff — that is where you notice an
agent's rejections piling up, not in a dashboard nobody opens.

```markdown
## 2026-08-04 — run 8
- **Context in:** Four cron rails fire on overlapping schedules
- **Output:** Introduce an event bus and migrate the four cron rails onto it
- **Signal:** Did not check whether the overlap actually causes a problem
- **Action:** REJECTED (2026-08-05) — the overlap has never once collided
- **Outcome:** OPEN
```

`Context in`, `Output` and `Signal` are what the agent said. `Action` is what
you did. `Outcome` is whether that turned out right, filled in whenever you
know — sometimes weeks later.

Parse and write are byte-exact both ways, including hand edits, unicode, and
multi-line bodies. You can edit the file by hand and the tool will not
reformat what you wrote.

### The one rule that makes it worth anything

**An agent may never write the Action or Outcome slot.**

An agent can describe what it was asked and what it recommended. It cannot
record what you did about that, or whether it worked. The moment it can, the
file is the agent grading its own homework and every number downstream is
worthless.

This is enforced in code, not in the docs. `ledger record` has no `--taken`
flag — not hidden, absent. And the block lives in `ledger/store.py`, in the
field writer, so a script that imports the library instead of shelling out
hits the same wall:

```python
>>> entry.set("Action", "TAKEN")
HumanOnlyField: Action is a human-only slot — `ledger record` cannot write it.
Use `ledger acted` / `ledger outcome`.
```

`ledger acted` and `ledger outcome` are your commands. Nothing else writes
those two lines.

### The reads

- `open` lists every PENDING entry oldest first, with how many days it has sat.
  A PENDING entry is not neutral. It usually means you read the advice, decided
  against it without saying so, and moved on — which is exactly the signal that
  used to evaporate.
- `scorecard` gives per agent: runs, take rate over the entries you actually
  ruled on, how the taken ones turned out, median days from the run to your
  ruling, and how many are still open. Ranked by take rate. Under five rulings
  it prints the numbers and marks the agent with a `*` saying they are too few
  to mean anything — a 100% take rate off two entries is not a track record.
- `brief` is the feedback half. It compresses the last N entries and then
  derives what it honestly can: the counts, the outcome record, the lag, and
  whether the rejected recommendations share wording the taken ones do not.
  That last one is deliberately dumb — it reports word overlap and says so.
  If there are fewer than three rejections, or no shared wording, it says there
  is no pattern rather than inventing one. An invented pattern pasted into an
  agent's system prompt is worse than an empty section, because the agent will
  believe it.

### What it cannot see

It reads five text fields and a date. It does not know why you rejected
something unless you typed a `--note`. It cannot tell a bad recommendation from
a good recommendation you were not ready for. The "of the taken ones, N right"
column only covers advice you took — advice you rejected has no counterfactual
and never will.

### Concurrency and where state lives

Every append and every ruling takes an exclusive lock on that agent's file
(`flock` where available) and writes through a temp file and an atomic rename.
Two orchestrator branches finishing in the same second both get their own run
number instead of one silently overwriting the other. There is a test for it.

State lives in one directory: `ledger/` next to your `ledger.json`, or wherever
you point `dir`. The only other thing written there is a zero-byte
`<agent>.md.lock` beside each ledger; git-ignore it. Nothing is written outside
that directory. No network calls, no telemetry, no account — this reads your
private repo on your laptop and that is the whole trust story.

## Configuration

One JSON file, `ledger.json`, found by walking up from the working directory.
JSON and not TOML because `tomllib` is Python 3.11 and this runs on 3.9.

| key | default | what it does |
|---|---|---|
| `dir` | `"ledger"` | directory holding the per-agent `.md` files, relative to `ledger.json` |

Overrides, highest first: `--dir` on any command, then the `LEDGER_DIR`
environment variable, then `ledger.json`, then the default.

`LEDGER_TODAY=YYYY-MM-DD` pins what the tool thinks today is. That exists so
tests and the committed example output do not drift; it is not something you
need day to day.

The `ledger.json` at the root of this repo points at `examples/`, so every
command in this README works the moment you clone it. Your own `ledger init`
writes one pointing at `ledger/`.

A file only counts as an agent ledger if its first line is
`# <agent> — ledger`. That is what keeps a pasted `brief.md` sitting in the
same directory from showing up in the scorecard as an agent with zero runs.

## What this is not

**It is not observability or tracing.** It records judgments, not spans. There
are no tokens, no latencies, no call graph. If you want to know what the agent
did inside the run, this is the wrong tool — it only knows what the agent
concluded and what you did about it.

**It is not automatic.** Someone has to rule on the entries. A ledger full of
PENDING is worse than no ledger, because it looks like data: an agent with 40
runs and 2 rulings will show a take rate, and that number means nothing. That
is what `ledger open` is for, and why `brief` says out loud when a window is
mostly unruled.

**It will not tell you whether the agent's reasoning was good.** Only whether
you took the advice and whether that worked out. Those are different questions.
An agent can be right and ignored, or wrong and followed, and this file cannot
tell the difference — it can only show you the pattern and let you look.

**It is not a prompt optimizer.** `brief` hands the agent its record. It does
not rewrite the agent, and it will not tell you what to change.

## Part of a family

Six small tools for the case where an AI coding agent does the work and a human
is not watching every step.

| repo | one line |
|---|---|
| [curfew](https://github.com/blakehallisey-arch/curfew) | write-time policy for an unattended agent — deny by rule, not by prompt |
| [breaker](https://github.com/blakehallisey-arch/breaker) | stops a session that is spinning, spreading, or inventing work |
| [shipgate](https://github.com/blakehallisey-arch/shipgate) | will not let a merge through until the checks it actually needs have run |
| [nightwatch](https://github.com/blakehallisey-arch/nightwatch) | the run rail — a queue, a budget lid, a window, and an honest log |
| [draftdiff](https://github.com/blakehallisey-arch/draftdiff) | learns your voice from the edits you make before you hit send |
| **ledger** | gives stateless agents a memory of what you did with their advice |
