# WeChat HTML Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional WeChat HTML template mode that injects AI-generated article content into a fixed template before saving the article draft.

**Architecture:** Keep the current publishing pipeline and add one template-aware branch inside `WeChatPublisher`. The CLI and scheduler will opt into that branch by passing a template name, while non-template publishing keeps the current formatting behavior.

**Tech Stack:** Python, `requests`, `unittest`, `unittest.mock`

---

### Task 1: Add regression coverage for template rendering

**Files:**
- Create: `tests/test_wechat_template_rendering.py`
- Test: `tests/test_wechat_template_rendering.py`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Write minimal implementation**
- [ ] **Step 4: Run test to verify it passes**

### Task 2: Add template rendering support

**Files:**
- Create: `templates/wechat_default.html`
- Modify: `utils/wechat_publisher.py`
- Modify: `generate_promo.py`
- Modify: `scheduler_app.py`

- [ ] **Step 1: Add a built-in template file with a content placeholder**
- [ ] **Step 2: Add template normalization and rendering helpers**
- [ ] **Step 3: Add a template-aware formatting path**
- [ ] **Step 4: Pass the template selection from the CLI and scheduler**

### Task 3: Verify behavior and document it

**Files:**
- Modify: `README.md`
- Test: `tests/test_wechat_template_rendering.py`

- [ ] **Step 1: Run targeted unit tests**
- [ ] **Step 2: Run syntax verification**
- [ ] **Step 3: Document the template mode and file path**
