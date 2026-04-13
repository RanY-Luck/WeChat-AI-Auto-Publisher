# DashScope Qwen3 Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add dual-path DashScope model routing so the existing app works with both legacy `qwen-plus` style models and newer `qwen3.6-plus` style models.

**Architecture:** Keep the public `generate_text()` surface stable and route internally by model family. Parse the two DashScope response shapes in one helper so calling code does not change.

**Tech Stack:** Python, `dashscope`, `unittest`, `unittest.mock`

---

### Task 1: Add regression coverage

**Files:**
- Create: `tests/test_dashscope_api.py`
- Test: `tests/test_dashscope_api.py`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Write minimal implementation**
- [ ] **Step 4: Run test to verify it passes**

### Task 2: Preserve runtime behavior

**Files:**
- Modify: `utils/dashscope_api.py`
- Modify: `README.md`

- [ ] **Step 1: Add shared response parsing helper**
- [ ] **Step 2: Keep legacy `Generation.call` path intact**
- [ ] **Step 3: Add `qwen3` multimodal path**
- [ ] **Step 4: Document supported model families**

### Task 3: Verify

**Files:**
- Test: `tests/test_dashscope_api.py`

- [ ] **Step 1: Run targeted unit test**
- [ ] **Step 2: Run `py_compile` import/syntax verification**
