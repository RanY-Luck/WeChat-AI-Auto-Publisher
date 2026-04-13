# WeChat UI Publish In Docker Design

## Goal

Add a Docker-friendly UI publishing path that keeps the current API-based draft creation flow, then uses a browser session to publish the latest WeChat draft at the scheduled publish time.

## Decision

Keep the current article generation and draft save flow intact. Add a second stage that uses Playwright inside the container to:

- reuse a persistent browser profile for WeChat login,
- check login status two hours before publish time,
- notify the operator through Bark with a QR-code link when login is required,
- publish the latest draft at the scheduled time,
- retry failed UI publishes up to three times before alerting.

## Scope

- Keep existing API draft creation, template rendering, and comment-enable behavior.
- Add a Playwright-based web publisher for WeChat backend publishing.
- Add QR-code capture and imgbb upload for Bark login notifications.
- Add Docker runtime support for Chromium, Xvfb, x11vnc, and noVNC.
- Add configuration for UI publish, login precheck, browser profile persistence, Bark fallback, and imgbb expiration.

## Workflow

1. Existing scheduler generates content and saves a WeChat draft.
2. Two hours before publish time, run a login precheck against the WeChat backend.
3. If logged in, do nothing else.
4. If not logged in:
   - open the login page,
   - capture the QR code,
   - upload the QR image to imgbb with a 10-minute expiration,
   - send a Bark notification with the QR link,
   - keep noVNC available as a fallback.
5. At publish time, open the draft list and publish the latest draft.
6. If publish fails, retry up to three times.
7. If all retries fail, send Bark failure notification and save screenshots/logs for manual follow-up.

## Constraints

- The user accepts occasional manual re-login through QR scan.
- The user accepts publishing the latest draft, even though this carries a mispublish risk if a newer draft exists.
- noVNC is the remote interactive fallback path.
- QR code images should expire after 600 seconds.
- `IMGBB_API_KEY` will be stored in `config.py` for now, per user preference.

## Architecture

### Scheduler

`scheduler_app.py` will orchestrate three phases:

- draft generation and save,
- pre-publish login check,
- scheduled UI publish.

The login precheck and publish tasks should remain separately callable so they can be retried or tested independently.

### Web Publisher

Add `utils/wechat_web_publisher.py` with one clear responsibility: interact with the WeChat backend UI. It should expose methods for:

- launching a persistent Playwright browser context,
- checking whether the session is logged in,
- opening the draft list,
- publishing the latest draft,
- capturing diagnostic screenshots.

### QR Notification

Add `utils/imgbb_uploader.py` to upload local QR screenshots to imgbb with expiration support. Extend Bark notification support so the login alert can carry the QR link and a noVNC fallback hint.

### Docker Runtime

The container must include:

- Playwright and Chromium,
- a virtual display server,
- VNC access,
- noVNC web access,
- a mounted persistent browser profile directory.

This runtime should start both the desktop stack and the Python scheduler process from a single entrypoint script.

## Error Handling

- If login precheck fails because the page cannot load, send Bark warning and keep the scheduled publish job intact.
- If imgbb upload fails, send a plain Bark text alert instructing the user to open noVNC and scan there.
- If publish fails because the UI cannot be located, retry three times with screenshots after each failure.
- If publish time arrives while still logged out, skip publish and alert instead of attempting blind actions.

## Testing

- Unit test imgbb upload request construction and expiration handling.
- Unit test Bark login-alert payload generation.
- Unit test scheduler timing calculation for the two-hour precheck.
- Add a lightweight Playwright smoke path behind mocks or abstractions where practical.
- Keep current DashScope and template tests green.

## Non-Goals

- No attempt to automate original-content declaration.
- No first-version support for selecting a draft by title or task id.
- No multi-account publishing support.
- No guarantee of permanent login persistence across WeChat risk-control resets.
