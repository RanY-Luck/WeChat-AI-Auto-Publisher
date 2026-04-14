# Multi-Instance WeChat Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deployable multi-instance Docker support so multiple WeChat public-account instances can run on one server with isolated config, ports, logs, and browser login state.

**Architecture:** Keep the existing single-instance image and runtime intact. Add a new multi-instance compose entrypoint plus per-instance template files, then document how operators create instances, map short names to ports, and scan-login the correct account. Preserve the single-instance path as the simple default.

**Tech Stack:** Docker Compose, Python `unittest`, Markdown documentation, env-file based runtime configuration

---

### Task 1: Add regression coverage for multi-instance deployment files

**Files:**
- Modify: `tests/test_docker_startup_examples.py`
- Create: `docker-compose.multi.yml`
- Create: `instances/_template/.env.example`
- Create: `instances/_template/config.py.example`

- [ ] **Step 1: Write the failing tests**

Add assertions that:

- `docker-compose.multi.yml` exists,
- it contains at least two example services using separate instance directories,
- it references per-instance `.env` and `config.py`,
- template files exist under `instances/_template/`,
- the env template documents `INSTANCE_SLUG`, `INSTANCE_NAME`, `BARK_TITLE_PREFIX`, `NOVNC_HOST_PORT`, and `VNC_HOST_PORT`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_docker_startup_examples -v`
Expected: FAIL because the multi-instance compose file and templates do not exist yet

- [ ] **Step 3: Write minimal implementation**

Create:

- `docker-compose.multi.yml`
- `instances/_template/.env.example`
- `instances/_template/config.py.example`

Keep these files documentation-first and example-safe.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_docker_startup_examples -v`
Expected: PASS

### Task 2: Document single-instance and multi-instance deployment clearly

**Files:**
- Modify: `README.md`
- Test: `tests/test_docker_startup_examples.py`

- [ ] **Step 1: Write the failing test**

Add assertions that `README.md` documents:

- `docker-compose.multi.yml`,
- `instances/_template/`,
- `INSTANCE_SLUG`,
- `INSTANCE_NAME`,
- per-instance noVNC/VNC port mapping,
- how to identify which QR code belongs to which instance.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_docker_startup_examples -v`
Expected: FAIL because the README does not yet describe the multi-instance deployment flow

- [ ] **Step 3: Write minimal implementation**

Update README so it:

- keeps the single-instance path,
- adds a multi-instance deployment section,
- explains the instance directory layout,
- explains per-instance compose services,
- explains scan/login mapping with short name + port + Bark title prefix,
- provides example commands for bringing up all instances or one target instance.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_docker_startup_examples -v`
Expected: PASS

### Task 3: Verify deploy docs and compose examples stay coherent

**Files:**
- Modify: `tests/test_docker_startup_examples.py`
- Verify: `docker-compose.multi.yml`
- Verify: `README.md`

- [ ] **Step 1: Run targeted regression tests**

Run: `python -m unittest tests.test_docker_startup_examples tests.test_scheduler_web_publish_config -v`
Expected: PASS

- [ ] **Step 2: Run compose syntax verification**

Run: `docker compose -f docker-compose.multi.yml config`
Expected: PASS

- [ ] **Step 3: Run a single-instance runtime smoke check**

Run: `docker compose up -d`
Expected: PASS with one `wechat-publisher` container using the configured host ports

- [ ] **Step 4: Commit**

```bash
git add README.md docker-compose.yml docker-compose.yml.example docker-compose.multi.yml .env.example instances/_template tests/test_docker_startup_examples.py docs/superpowers/specs/2026-04-13-multi-instance-deploy-design.md docs/superpowers/plans/2026-04-13-multi-instance-deploy.md
git commit -m "feat: add multi-instance deploy docs"
```
