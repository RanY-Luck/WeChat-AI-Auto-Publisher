# WeChat HTML Template Rendering Design

## Goal

Allow the publisher to wrap AI-generated article text inside a fixed WeChat HTML template, replacing the placeholder `""` with the generated body content while leaving the decorative header and footer intact.

## Decision

Add an optional template rendering path before the existing draft publish call.

- Store the cleaned HTML template in a dedicated file under `templates/`.
- Replace a single content placeholder in that template with rendered article body HTML.
- Skip the existing full-content formatter when template mode is enabled so the template structure is not mutated.

## Scope

- Add one built-in template file based on the user-provided WeChat HTML snippet.
- Add template rendering helpers inside the publishing layer.
- Wire the template path into both `generate_promo.py` and `scheduler_app.py`.
- Add tests for template cleanup and content insertion.

## Non-Goals

- No multi-template selector UI.
- No remote template loading.
- No change to the current draft-first publish flow.

## Error Handling

- If template mode is enabled but the template file is missing, raise a clear error.
- If the content placeholder is missing, fail fast instead of publishing malformed content.
- Preserve the current behavior for accounts that can only save drafts.

## Testing

- Add a regression test that verifies encoded template HTML is normalized and accepts injected content.
- Add a regression test that verifies template mode bypasses the legacy formatter and preserves the final HTML shell.
