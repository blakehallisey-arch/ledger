# architect — ledger

What this agent recommended, and what the human did about it.

`Action` and `Outcome` are human-only slots. `ledger record` cannot write them;
only `ledger acted` and `ledger outcome` can. That split is the whole point of
the file — an agent grading its own advice is not a track record.

## 2026-06-29 — run 1
- **Context in:** Monthly portfolio review, 14 builds
- **Output:** Rewrite the ingest pipeline as a plugin framework and migrate the three existing sources onto it
- **Signal:** Sized at two weeks; did not price the migration of the live sources
- **Action:** REJECTED (2026-07-02) — not doing a two-week rewrite for three sources
- **Outcome:** OPEN

## 2026-07-05 — run 2
- **Context in:** Monthly portfolio review, 14 builds
- **Output:** Migrate the job store from flat files to Postgres; the rewrite is about two weeks
- **Signal:** Assumed concurrent writers, which there are not yet
- **Action:** REJECTED (2026-07-06) — flat files are fine at this size
- **Outcome:** OPEN

## 2026-07-09 — run 3
- **Context in:** The CLI has grown to eleven subcommands
- **Output:** Rewrite the CLI on a proper command framework and migrate every subcommand onto it
- **Signal:** Argparse is doing fine; this is a taste argument
- **Action:** REJECTED (2026-07-13)
- **Outcome:** OPEN

## 2026-07-14 — run 4
- **Context in:** Two workers stepped on each other
- **Output:** Add a file lock in the one place that appends — six lines, no new moving parts
- **Signal:** Smallest thing that closes it
- **Action:** TAKEN (2026-07-14)
- **Outcome:** RIGHT (2026-07-21)

## 2026-07-18 — run 5
- **Context in:** Monthly portfolio review, 14 builds
- **Output:** Stand up a service boundary between the scheduler and the workers — a rewrite of both call paths
- **Signal:** No scaling pressure named anywhere in the inputs
- **Action:** REJECTED (2026-07-19) — one machine, one user
- **Outcome:** OPEN

## 2026-07-24 — run 6
- **Context in:** The config file has grown to 40 keys
- **Output:** Migrate the whole config layer to a schema-validated format and rewrite the readers
- **Signal:** The reported pain was one typo, once
- **Action:** REJECTED (2026-07-27)
- **Outcome:** OPEN

## 2026-07-30 — run 7
- **Context in:** Retry logic is duplicated in six places
- **Output:** Replace the hand-rolled retry logic with a general-purpose framework and migrate all six callers
- **Signal:** Four of the six have different backoff needs
- **Action:** REJECTED (2026-08-01) — hoisted one shared helper instead
- **Outcome:** OPEN

## 2026-08-04 — run 8
- **Context in:** Four cron rails fire on overlapping schedules
- **Output:** Introduce an event bus and migrate the four cron rails onto it
- **Signal:** Did not check whether the overlap actually causes a problem
- **Action:** REJECTED (2026-08-05) — the overlap has never once collided
- **Outcome:** OPEN

## 2026-08-07 — run 9
- **Context in:** Deploys are failing silently
- **Output:** Make the deploy check read the artifact timestamp instead of the exit code
- **Signal:** The exit code was always 0; the check has never been meaningful
- **Action:** TAKEN (2026-08-07)
- **Outcome:** RIGHT (2026-08-12)

## 2026-08-11 — run 10
- **Context in:** Monthly portfolio review, 14 builds
- **Output:** Split the reporting layer into its own package with a versioned interface
- **Signal:** One consumer today; the versioned interface is for consumers that do not exist
- **Action:** PENDING
- **Outcome:** OPEN
