# sweeper — ledger

What this agent recommended, and what the human did about it.

`Action` and `Outcome` are human-only slots. `ledger record` cannot write them;
only `ledger acted` and `ledger outcome` can. That split is the whole point of
the file — an agent grading its own advice is not a track record.

## 2026-06-30 — run 1
- **Context in:** Weekly sweep across 14 repos
- **Output:** Add a lock around the queue file — two workers can both take run 7
- **Signal:** Reproduced it; did not check whether the same race exists in the log writer
- **Action:** TAKEN (2026-07-01) — shipped same day
- **Outcome:** RIGHT (2026-07-08) — the duplicate runs stopped

## 2026-07-03 — run 2
- **Context in:** Weekly sweep across 14 repos
- **Output:** Pin the model id in one place — three call sites have drifted to different versions
- **Signal:** Did not check whether any of the three drifts was deliberate
- **Action:** TAKEN (2026-07-04)
- **Outcome:** RIGHT (2026-07-20)

## 2026-07-07 — run 3
- **Context in:** Pre-ship check on the nightly runner
- **Output:** The API key falls back to unset and the step silently skips — make it exit 1
- **Signal:** This is the silent-skip shape again; third time in this repo
- **Action:** TAKEN (2026-07-07) — obvious once it was pointed at
- **Outcome:** RIGHT (2026-07-14)

## 2026-07-11 — run 4
- **Context in:** Weekly sweep across 14 repos
- **Output:** Four repos have committed work that was never pushed; oldest is 19 days
- **Signal:** Cannot tell which of those are deliberately local
- **Action:** PARTIAL (2026-07-12) — pushed two, the other two are private scratch
- **Outcome:** OPEN

## 2026-07-16 — run 5
- **Context in:** Cost review after a surprise bill
- **Output:** The batch job bills the metered key but only ever runs locally — move it to the CLI
- **Signal:** Nailed the meter; guessed at the volume
- **Action:** TAKEN (2026-07-17)
- **Outcome:** RIGHT (2026-08-01) — next bill was a third of the last one

## 2026-07-22 — run 6
- **Context in:** Weekly sweep across 14 repos
- **Output:** Two .env files are tracked by git in a public repo — rotate the keys and untrack them
- **Signal:** Did not check the history, only the working tree
- **Action:** TAKEN (2026-07-22) — rotated within the hour
- **Outcome:** MIXED (2026-07-29) — right about the files, but the keys were also in history and it missed that

## 2026-07-28 — run 7
- **Context in:** Weekly sweep across 14 repos
- **Output:** Downgrade the summarizer to the small model — the job is extraction, not reasoning
- **Signal:** Assumed the summaries are never read by anyone but the cron
- **Action:** TAKEN (2026-07-30)
- **Outcome:** WRONG (2026-08-06) — quality dropped enough that we put it back

## 2026-08-03 — run 8
- **Context in:** Weekly sweep across 14 repos
- **Output:** A cron points at a path that moved in April; it has failed quietly 118 times
- **Signal:** The failure count came from the log, not from the exit code, which was 0
- **Action:** TAKEN (2026-08-03)
- **Outcome:** RIGHT (2026-08-10)

## 2026-08-08 — run 9
- **Context in:** Weekly sweep across 14 repos
- **Output:** The deploy hook writes outside its repo, into a sibling checkout
- **Signal:** Found by reading the hook, not by watching it run
- **Action:** TAKEN (2026-08-09)
- **Outcome:** RIGHT (2026-08-13)

## 2026-08-12 — run 10
- **Context in:** Weekly sweep across 14 repos
- **Output:** Three lint rails have been red continuously for nine days; nobody is reading them
- **Signal:** A permanently red check is the same as no check
- **Action:** PENDING
- **Outcome:** OPEN
