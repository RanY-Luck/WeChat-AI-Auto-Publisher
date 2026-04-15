# Single Account Deploy Parameters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parameterize Docker deployment resources so one single-account codebase can be deployed multiple times independently.

**Architecture:** Keep container-internal behavior unchanged and move deployment isolation into `.env`-driven Docker Compose values. Update packaging and deployment scripts so the same release flow works for multiple isolated single-account deployments.

**Tech Stack:** Docker Compose, Windows batch, Bash, Python unittest/pytest-style file assertions, Markdown docs

---

### Task 1: Add regression coverage for deployment templates

**Files:**
- Create: `tests/test_single_account_deploy_params.py`

- [ ] **Step 1: Write the failing tests**
- [ ] **Step 2: Run the tests to verify they fail against current hard-coded config**
- [ ] **Step 3: Cover compose variables, env example variables, build script env loading, and deploy script env loading**
- [ ] **Step 4: Re-run the tests after implementation**

### Task 2: Parameterize Docker deployment files

**Files:**
- Modify: `docker-compose.yml`
- Modify: `docker-compose.yml.example`
- Modify: `.env.example`

- [ ] **Step 1: Replace hard-coded container name, image, host ports, and login profile volume with `.env` references**
- [ ] **Step 2: Keep container-internal ports fixed at `6080` and `5900`**
- [ ] **Step 3: Add documented defaults in `.env.example`**

### Task 3: Parameterize packaging and deployment scripts

**Files:**
- Modify: `build_release.bat`
- Modify: `deploy_centos7.sh`

- [ ] **Step 1: Load `.env` variables in the Windows release script**
- [ ] **Step 2: Use resolved `IMAGE_NAME` for `docker build` and `docker save`**
- [ ] **Step 3: Load `.env` variables in the Linux deployment script**
- [ ] **Step 4: Use resolved `IMAGE_NAME` and `CONTAINER_NAME` during deployment**

### Task 4: Update deployment documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the Docker deployment section to match parameterized deployment**
- [ ] **Step 2: Add examples for running account A / account B as separate single-account stacks**
- [ ] **Step 3: Document the new host port and profile volume variables**

### Task 5: Verify end-to-end behavior

**Files:**
- Verify only

- [ ] **Step 1: Run the new deployment regression tests**
- [ ] **Step 2: Render compose config with current `.env`**
- [ ] **Step 3: Confirm the running local single-account container is still on the intended branch and environment**
