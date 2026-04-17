# Random Daily Publish Frequency Design

## Goal

Add a scheduling mode that runs the full publishing workflow a random number of times per day, where the daily run count is randomly chosen from `1..N`.

## User Requirement

- Support multiple full publish runs per day instead of one fixed evening run
- Allow runs at any hour, including overnight
- Keep topic selection as "randomly choose 1 topic from the top 3 hot topics"
- Keep the existing full workflow for each run:
  `topic selection -> content generation -> save draft -> web publish`

## Scope

- Add a new random daily schedule mode to the scheduler
- Keep existing fixed-time configuration compatible
- Generate a fresh schedule for each calendar day
- Improve logs and startup notifications so the operator can see today's generated plan
- Add regression tests for the schedule generation and registration logic

## Non-Goals

- No UI for editing schedules
- No partial workflow mode
- No custom time window; the schedule may use the full `00:00-23:59` day
- No change to the topic rule beyond preserving the current top-3-random selection

## Scheduling Model

The scheduler gains a daily random-plan mode. When enabled:

- The system randomly chooses a run count from `1..daily_random_runs_max`
- It randomly selects that many unique minute-level timestamps from the full day
- The timestamps are sorted and registered into the scheduler for the current day
- Each registered time runs the existing full workflow job

The plan is regenerated once per day. The implementation should maintain a small in-memory state that records:

- which date the active plan belongs to
- which times were generated for that date

On startup, the scheduler immediately generates and registers the current day's plan. A lightweight periodic maintenance job is also registered so that, after the date changes, the scheduler generates the next day's plan automatically without requiring a process restart.

## Configuration

Keep current fixed-time fields for backward compatibility, but add new fields:

- `random_daily_schedule_enabled`: whether to use random daily scheduling
- `daily_random_runs_max`: maximum number of runs per day; actual count is random from `1..N`

Behavior rules:

- If `random_daily_schedule_enabled` is true, random daily scheduling takes priority over fixed `target_time` and `publish_time`
- If disabled or missing, the current fixed-time behavior remains unchanged
- Invalid or empty `daily_random_runs_max` values fall back to a safe minimum of `1`

## Execution Flow

Each random scheduled run triggers the existing `job()` flow, which already performs:

- hot topic fetch
- restrict to top N candidates using `hot_topic_candidate_limit`
- random topic choice from those candidates
- article generation
- draft save
- web publish integration via the current publish flow

This preserves the current topic behavior: with `hot_topic_candidate_limit = 3`, each run still picks randomly from the top 3 hot topics.

## Logging And Notifications

Add clear visibility into generated plans:

- On startup, log today's generated run count and times
- When the date changes and a new plan is generated, log the new date and generated times
- Startup Bark notification should mention that random daily scheduling is enabled and include today's generated times when available

This reduces operator confusion because a single fixed `20:00` log line will no longer describe the real behavior.

## Testing Strategy

Add scheduler-focused regression tests that cover:

- generated daily run count is within `1..daily_random_runs_max`
- generated timestamps are valid `HH:MM` values
- generated timestamps are unique
- generated timestamps are sorted
- enabling random daily mode registers multiple generated jobs rather than one fixed daily job
- topic selection logic still slices to the configured top 3 and chooses randomly from that slice

Tests should isolate scheduling logic from wall-clock randomness by injecting deterministic random choices where needed.

## Risks

- A full-day random schedule can generate clustered times close together; this is acceptable for the current requirement
- If the process starts late in the day, some generated times for the current day may already have passed; implementation should only register future runs for the current date
- Startup and rollover logic must avoid duplicating today's registrations when maintenance runs multiple times

## Recommended Implementation Direction

Implement the random daily schedule as an additive scheduling layer inside `scheduler_app.py`, with small helper functions for:

- generating today's random run times
- registering one day's run list into the `schedule` module
- refreshing the plan when the date changes

This keeps the change localized, preserves backward compatibility, and minimizes risk compared with a broader rewrite of the scheduler loop.
