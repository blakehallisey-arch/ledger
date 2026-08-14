#!/usr/bin/env bash
# Regenerates the two example ledgers plus scorecard.txt and brief.md.
# Everything in examples/ is real CLI output, so this is how it stays real.
# LEDGER_TODAY pins "today" so the day counts do not drift every time.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
cd "$ROOT"

export LEDGER_DIR="$HERE"
export LEDGER_TODAY=2026-08-14
L="python3 -m ledger"

rm -f "$HERE/sweeper.md" "$HERE/architect.md"

# --------------------------------------------------------------------------
# sweeper — an infrastructure hygiene agent. Small, checkable findings.
# Its advice mostly gets taken, and mostly turns out right.

$L record sweeper --date 2026-06-30 \
  --context "Weekly sweep across 14 repos" \
  --output "Add a lock around the queue file — two workers can both take run 7" \
  --signal "Reproduced it; did not check whether the same race exists in the log writer" >/dev/null
$L acted sweeper 1 --taken --date 2026-07-01 --note "shipped same day"
$L outcome sweeper 1 --right --date 2026-07-08 --note "the duplicate runs stopped"

$L record sweeper --date 2026-07-03 \
  --context "Weekly sweep across 14 repos" \
  --output "Pin the model id in one place — three call sites have drifted to different versions" \
  --signal "Did not check whether any of the three drifts was deliberate" >/dev/null
$L acted sweeper 2 --taken --date 2026-07-04
$L outcome sweeper 2 --right --date 2026-07-20

$L record sweeper --date 2026-07-07 \
  --context "Pre-ship check on the nightly runner" \
  --output "The API key falls back to unset and the step silently skips — make it exit 1" \
  --signal "This is the silent-skip shape again; third time in this repo" >/dev/null
$L acted sweeper 3 --taken --date 2026-07-07 --note "obvious once it was pointed at"
$L outcome sweeper 3 --right --date 2026-07-14

$L record sweeper --date 2026-07-11 \
  --context "Weekly sweep across 14 repos" \
  --output "Four repos have committed work that was never pushed; oldest is 19 days" \
  --signal "Cannot tell which of those are deliberately local" >/dev/null
$L acted sweeper 4 --partial --date 2026-07-12 --note "pushed two, the other two are private scratch"

$L record sweeper --date 2026-07-16 \
  --context "Cost review after a surprise bill" \
  --output "The batch job bills the metered key but only ever runs locally — move it to the CLI" \
  --signal "Nailed the meter; guessed at the volume" >/dev/null
$L acted sweeper 5 --taken --date 2026-07-17
$L outcome sweeper 5 --right --date 2026-08-01 --note "next bill was a third of the last one"

$L record sweeper --date 2026-07-22 \
  --context "Weekly sweep across 14 repos" \
  --output "Two .env files are tracked by git in a public repo — rotate the keys and untrack them" \
  --signal "Did not check the history, only the working tree" >/dev/null
$L acted sweeper 6 --taken --date 2026-07-22 --note "rotated within the hour"
$L outcome sweeper 6 --mixed --date 2026-07-29 --note "right about the files, but the keys were also in history and it missed that"

$L record sweeper --date 2026-07-28 \
  --context "Weekly sweep across 14 repos" \
  --output "Downgrade the summarizer to the small model — the job is extraction, not reasoning" \
  --signal "Assumed the summaries are never read by anyone but the cron" >/dev/null
$L acted sweeper 7 --taken --date 2026-07-30
$L outcome sweeper 7 --wrong --date 2026-08-06 --note "quality dropped enough that we put it back"

$L record sweeper --date 2026-08-03 \
  --context "Weekly sweep across 14 repos" \
  --output "A cron points at a path that moved in April; it has failed quietly 118 times" \
  --signal "The failure count came from the log, not from the exit code, which was 0" >/dev/null
$L acted sweeper 8 --taken --date 2026-08-03
$L outcome sweeper 8 --right --date 2026-08-10

$L record sweeper --date 2026-08-08 \
  --context "Weekly sweep across 14 repos" \
  --output "The deploy hook writes outside its repo, into a sibling checkout" \
  --signal "Found by reading the hook, not by watching it run" >/dev/null
$L acted sweeper 9 --taken --date 2026-08-09
$L outcome sweeper 9 --right --date 2026-08-13

$L record sweeper --date 2026-08-12 \
  --context "Weekly sweep across 14 repos" \
  --output "Three lint rails have been red continuously for nine days; nobody is reading them" \
  --signal "A permanently red check is the same as no check" >/dev/null

# --------------------------------------------------------------------------
# architect — proposes what to build next. Almost everything it says is
# turned down, and the turned-down ones all have the same shape.

$L record architect --date 2026-06-29 \
  --context "Monthly portfolio review, 14 builds" \
  --output "Rewrite the ingest pipeline as a plugin framework and migrate the three existing sources onto it" \
  --signal "Sized at two weeks; did not price the migration of the live sources" >/dev/null
$L acted architect 1 --rejected --date 2026-07-02 --note "not doing a two-week rewrite for three sources"

$L record architect --date 2026-07-05 \
  --context "Monthly portfolio review, 14 builds" \
  --output "Migrate the job store from flat files to Postgres; the rewrite is about two weeks" \
  --signal "Assumed concurrent writers, which there are not yet" >/dev/null
$L acted architect 2 --rejected --date 2026-07-06 --note "flat files are fine at this size"

$L record architect --date 2026-07-09 \
  --context "The CLI has grown to eleven subcommands" \
  --output "Rewrite the CLI on a proper command framework and migrate every subcommand onto it" \
  --signal "Argparse is doing fine; this is a taste argument" >/dev/null
$L acted architect 3 --rejected --date 2026-07-13

$L record architect --date 2026-07-14 \
  --context "Two workers stepped on each other" \
  --output "Add a file lock in the one place that appends — six lines, no new moving parts" \
  --signal "Smallest thing that closes it" >/dev/null
$L acted architect 4 --taken --date 2026-07-14
$L outcome architect 4 --right --date 2026-07-21

$L record architect --date 2026-07-18 \
  --context "Monthly portfolio review, 14 builds" \
  --output "Stand up a service boundary between the scheduler and the workers — a rewrite of both call paths" \
  --signal "No scaling pressure named anywhere in the inputs" >/dev/null
$L acted architect 5 --rejected --date 2026-07-19 --note "one machine, one user"

$L record architect --date 2026-07-24 \
  --context "The config file has grown to 40 keys" \
  --output "Migrate the whole config layer to a schema-validated format and rewrite the readers" \
  --signal "The reported pain was one typo, once" >/dev/null
$L acted architect 6 --rejected --date 2026-07-27

$L record architect --date 2026-07-30 \
  --context "Retry logic is duplicated in six places" \
  --output "Replace the hand-rolled retry logic with a general-purpose framework and migrate all six callers" \
  --signal "Four of the six have different backoff needs" >/dev/null
$L acted architect 7 --rejected --date 2026-08-01 --note "hoisted one shared helper instead"

$L record architect --date 2026-08-04 \
  --context "Four cron rails fire on overlapping schedules" \
  --output "Introduce an event bus and migrate the four cron rails onto it" \
  --signal "Did not check whether the overlap actually causes a problem" >/dev/null
$L acted architect 8 --rejected --date 2026-08-05 --note "the overlap has never once collided"

$L record architect --date 2026-08-07 \
  --context "Deploys are failing silently" \
  --output "Make the deploy check read the artifact timestamp instead of the exit code" \
  --signal "The exit code was always 0; the check has never been meaningful" >/dev/null
$L acted architect 9 --taken --date 2026-08-07
$L outcome architect 9 --right --date 2026-08-12

$L record architect --date 2026-08-11 \
  --context "Monthly portfolio review, 14 builds" \
  --output "Split the reporting layer into its own package with a versioned interface" \
  --signal "One consumer today; the versioned interface is for consumers that do not exist" >/dev/null

# --------------------------------------------------------------------------
# The two committed reads, straight out of the tool.

$L scorecard > "$HERE/scorecard.txt"
$L brief architect --last 10 > "$HERE/brief.md"

echo "wrote sweeper.md architect.md scorecard.txt brief.md"
