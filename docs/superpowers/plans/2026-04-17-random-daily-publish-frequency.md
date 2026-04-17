# Random Daily Publish Frequency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a random daily scheduling mode that runs the full publish workflow a random number of times per day from `1..N`, while preserving the existing top-3-random topic selection and backward compatibility with fixed-time scheduling.

**Architecture:** Keep the change localized in `scheduler_app.py` by adding helper functions that generate a per-day plan, register only future jobs for the current date, and refresh the plan once the calendar day changes. Expose the feature through additive config fields, then update startup logging and docs so operators can see the generated schedule for the day.

**Tech Stack:** Python, `schedule`, `unittest`, Markdown docs

---

## File Structure

- Modify: `scheduler_app.py`
  Responsibility: own the random daily plan generation, daily rollover refresh, startup logging, and schedule registration while keeping the existing publish workflow unchanged.
- Modify: `config/config.py`
  Responsibility: define the new random daily schedule config defaults for the local runtime config.
- Modify: `config/config.py.example`
  Responsibility: document the new config fields for clean installs and deployments.
- Modify: `README.md`
  Responsibility: explain how to enable random daily scheduling and how it interacts with fixed-time fields.
- Create: `tests/test_random_daily_schedule.py`
  Responsibility: cover random schedule generation and registration logic with deterministic randomness.

### Task 1: Add failing tests for random daily plan generation

**Files:**
- Create: `tests/test_random_daily_schedule.py`
- Modify: `scheduler_app.py`

- [ ] **Step 1: Write the failing test for daily time generation**

```python
def test_generate_random_daily_times_returns_sorted_unique_hhmm_values():
    class FakeRandom:
        def randint(self, start, end):
            return 3

        def sample(self, population, count):
            return [61, 5, 1439]

    times = scheduler_app.generate_random_daily_times(
        daily_random_runs_max=5,
        random_module=FakeRandom(),
    )

    assert times == ["00:05", "01:01", "23:59"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_random_daily_schedule.RandomDailyScheduleTests.test_generate_random_daily_times_returns_sorted_unique_hhmm_values -v`
Expected: FAIL because `generate_random_daily_times` does not exist yet.

- [ ] **Step 3: Write the failing test for same-day future filtering**

```python
def test_filter_future_times_for_today_skips_passed_slots():
    today = date(2026, 4, 17)
    now = datetime(2026, 4, 17, 10, 30)

    result = scheduler_app.filter_future_times_for_today(
        plan_date=today,
        times=["09:00", "10:30", "10:31", "23:59"],
        now=now,
    )

    assert result == ["10:31", "23:59"]
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m unittest tests.test_random_daily_schedule.RandomDailyScheduleTests.test_filter_future_times_for_today_skips_passed_slots -v`
Expected: FAIL because `filter_future_times_for_today` does not exist yet.

### Task 2: Add failing tests for scheduler registration and rollover

**Files:**
- Modify: `tests/test_random_daily_schedule.py`
- Modify: `scheduler_app.py`

- [ ] **Step 1: Write the failing test for random mode registration**

```python
def test_schedule_jobs_registers_random_daily_runs_when_enabled():
    scheduler = FakeScheduler()
    config = SimpleNamespace(PUBLISH_CONFIG={
        "random_daily_schedule_enabled": True,
        "daily_random_runs_max": 3,
        "enable_web_publish": False,
    })

    info = scheduler_app.schedule_jobs(
        config=config,
        scheduler_module=scheduler,
        draft_job_callable=lambda: None,
        now_provider=lambda: datetime(2026, 4, 17, 0, 0),
        random_module=FakeRandomPlan([5, 61]),
    )

    assert info["schedule_mode"] == "random_daily"
    assert info["target_times"] == ["00:05", "01:01"]
    assert scheduler.at_times == ["00:05", "01:01"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_random_daily_schedule.RandomDailyScheduleTests.test_schedule_jobs_registers_random_daily_runs_when_enabled -v`
Expected: FAIL because `schedule_jobs` does not yet accept injected time/random dependencies or return random-plan metadata.

- [ ] **Step 3: Write the failing test for day rollover refresh**

```python
def test_refresh_random_daily_plan_replaces_plan_after_date_change():
    scheduler = FakeScheduler()
    state = {"plan_date": date(2026, 4, 17), "registered_job_refs": []}

    updated = scheduler_app.refresh_random_daily_plan(
        state=state,
        scheduler_module=scheduler,
        draft_job_callable=lambda: None,
        now_provider=lambda: datetime(2026, 4, 18, 0, 1),
        random_module=FakeRandomPlan([15]),
        daily_random_runs_max=1,
    )

    assert updated["plan_date"] == date(2026, 4, 18)
    assert updated["times"] == ["00:15"]
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m unittest tests.test_random_daily_schedule.RandomDailyScheduleTests.test_refresh_random_daily_plan_replaces_plan_after_date_change -v`
Expected: FAIL because `refresh_random_daily_plan` does not exist yet.

### Task 3: Implement minimal random daily scheduling helpers

**Files:**
- Modify: `scheduler_app.py`
- Test: `tests/test_random_daily_schedule.py`

- [ ] **Step 1: Add the minimal helper implementations**

```python
def generate_random_daily_times(daily_random_runs_max, random_module=None):
    random_module = random_module or random
    max_runs = _safe_int(daily_random_runs_max, default=1, minimum=1)
    run_count = random_module.randint(1, max_runs)
    minutes = sorted(random_module.sample(range(24 * 60), run_count))
    return [f"{minute // 60:02d}:{minute % 60:02d}" for minute in minutes]


def filter_future_times_for_today(plan_date, times, now=None):
    now = now or datetime.now()
    if plan_date != now.date():
        return list(times)
    current = now.strftime("%H:%M")
    return [time_text for time_text in times if time_text > current]
```

- [ ] **Step 2: Run the helper-focused tests**

Run: `python -m unittest tests.test_random_daily_schedule.RandomDailyScheduleTests.test_generate_random_daily_times_returns_sorted_unique_hhmm_values tests.test_random_daily_schedule.RandomDailyScheduleTests.test_filter_future_times_for_today_skips_passed_slots -v`
Expected: PASS

- [ ] **Step 3: Refactor only if duplication remains**

```python
def _minute_to_hhmm(minute):
    return f"{minute // 60:02d}:{minute % 60:02d}"
```

- [ ] **Step 4: Re-run the same tests**

Run: `python -m unittest tests.test_random_daily_schedule.RandomDailyScheduleTests.test_generate_random_daily_times_returns_sorted_unique_hhmm_values tests.test_random_daily_schedule.RandomDailyScheduleTests.test_filter_future_times_for_today_skips_passed_slots -v`
Expected: PASS

### Task 4: Implement schedule registration and daily rollover

**Files:**
- Modify: `scheduler_app.py`
- Test: `tests/test_random_daily_schedule.py`

- [ ] **Step 1: Implement minimal job registration helpers**

```python
def register_random_daily_jobs(scheduler_module, times, draft_job_callable):
    registered = []
    for target_time in times:
        job_ref = scheduler_module.every().day.at(target_time).do(draft_job_callable)
        registered.append(job_ref)
    return registered


def refresh_random_daily_plan(
    state,
    scheduler_module,
    draft_job_callable,
    daily_random_runs_max,
    now_provider=None,
    random_module=None,
):
    now_provider = now_provider or datetime.now
    now = now_provider()
    if state.get("plan_date") == now.date():
        return state

    times = filter_future_times_for_today(
        plan_date=now.date(),
        times=generate_random_daily_times(daily_random_runs_max, random_module=random_module),
        now=now,
    )
    state["plan_date"] = now.date()
    state["times"] = times
    state["registered_job_refs"] = register_random_daily_jobs(scheduler_module, times, draft_job_callable)
    return state
```

- [ ] **Step 2: Run the registration tests**

Run: `python -m unittest tests.test_random_daily_schedule.RandomDailyScheduleTests.test_schedule_jobs_registers_random_daily_runs_when_enabled tests.test_random_daily_schedule.RandomDailyScheduleTests.test_refresh_random_daily_plan_replaces_plan_after_date_change -v`
Expected: still FAIL until `schedule_jobs` is wired to the new helpers.

- [ ] **Step 3: Update `schedule_jobs` to branch on random mode**

```python
if publish_config.get("random_daily_schedule_enabled"):
    state = refresh_random_daily_plan(
        state={},
        scheduler_module=scheduler_module,
        draft_job_callable=draft_job_callable,
        daily_random_runs_max=publish_config.get("daily_random_runs_max"),
        now_provider=now_provider,
        random_module=random_module,
    )
    scheduler_module.every(10).minutes.do(refresh_random_daily_plan, ...)
    return {
        "schedule_mode": "random_daily",
        "target_times": state["times"],
        "web_publish_enabled": bool(publish_config.get("enable_web_publish")),
    }
```

- [ ] **Step 4: Run the registration tests again**

Run: `python -m unittest tests.test_random_daily_schedule.RandomDailyScheduleTests.test_schedule_jobs_registers_random_daily_runs_when_enabled tests.test_random_daily_schedule.RandomDailyScheduleTests.test_refresh_random_daily_plan_replaces_plan_after_date_change -v`
Expected: PASS

### Task 5: Update startup logging and config compatibility

**Files:**
- Modify: `scheduler_app.py`
- Modify: `config/config.py`
- Modify: `config/config.py.example`

- [ ] **Step 1: Write the failing config-defaults test**

```python
def test_config_example_documents_random_daily_schedule_fields():
    text = Path("config/config.py.example").read_text(encoding="utf-8")
    assert '"random_daily_schedule_enabled"' in text
    assert '"daily_random_runs_max"' in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_random_daily_schedule.RandomDailyScheduleTests.test_config_example_documents_random_daily_schedule_fields -v`
Expected: FAIL because the new fields are not documented yet.

- [ ] **Step 3: Add minimal config defaults and startup log branch**

```python
PUBLISH_CONFIG = {
    ...
    "random_daily_schedule_enabled": False,
    "daily_random_runs_max": 3,
}

if schedule_info.get("schedule_mode") == "random_daily":
    logger.info(f"今天随机计划执行 {len(schedule_info['target_times'])} 次: {', '.join(schedule_info['target_times'])}")
else:
    logger.info(f"🚀 发帖机器人已启动！将在每天 {target_time} 自动生成并保存草稿。")
```

- [ ] **Step 4: Run the config-defaults test**

Run: `python -m unittest tests.test_random_daily_schedule.RandomDailyScheduleTests.test_config_example_documents_random_daily_schedule_fields -v`
Expected: PASS

### Task 6: Update README and run focused verification

**Files:**
- Modify: `README.md`
- Test: `tests/test_random_daily_schedule.py`

- [ ] **Step 1: Add the README section for random daily scheduling**

```markdown
PUBLISH_CONFIG = {
    "random_daily_schedule_enabled": True,
    "daily_random_runs_max": 5,
}
```

- [ ] **Step 2: Run the full new test file**

Run: `python -m unittest tests.test_random_daily_schedule -v`
Expected: PASS

- [ ] **Step 3: Run existing scheduler/topic regression coverage**

Run: `python -m unittest tests.test_weibo_topic_limit -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add scheduler_app.py config/config.py config/config.py.example README.md tests/test_random_daily_schedule.py docs/superpowers/plans/2026-04-17-random-daily-publish-frequency.md
git commit -m "feat: add random daily publish frequency"
```
