# DashScope Qwen3 Compatibility Design

## Goal

Make the repository support both legacy DashScope text models (`qwen-plus`, `qwen-max`) and newer `qwen3` models such as `qwen3.6-plus` without breaking the current calling code.

## Decision

Use dual-path routing inside `utils/dashscope_api.py`.

- Legacy `qwen` models keep using `dashscope.Generation.call(...)`.
- `qwen3` models use `dashscope.MultiModalConversation.call(...)` with multimodal-style message content.

## Scope

- Keep `PromoGenerator` unchanged.
- Keep the public `DashScopeAPI.generate_text()` API unchanged.
- Add a regression test for both response formats.

## Non-Goals

- No migration to OpenAI-compatible endpoints.
- No refactor of unrelated publishing logic.
- No new runtime dependencies.

## Error Handling

- Preserve existing exception behavior for non-200 responses.
- Add a parsing error when the model response structure is unexpected.

## Testing

- Add a `unittest` regression test that patches DashScope SDK calls.
- Verify the legacy model path returns plain string content.
- Verify the `qwen3` path uses multimodal content and extracts text correctly.
