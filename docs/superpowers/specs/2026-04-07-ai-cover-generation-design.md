# AI Cover Generation Design

## Goal

Add AI-generated cover support to the publishing flow using Alibaba Cloud Bailian `wan2.7-image-pro`, while preserving the existing solid-color cover as a fallback.

## User-Approved Decisions

- Keep the current solid-color cover generator as the fallback path.
- Generate AI covers from `title + digest` only.
- The visual direction is text-free, fresh, calming, and suitable for emotional WeChat article covers.
- AI generation latency is acceptable before publishing.
- The feature should apply to both manual publishing and scheduled publishing.

## Context

Today the repository creates a placeholder solid-color image in both publishing entry points:

- `generate_promo.py`
- `scheduler_app.py`

That image is then passed into `WeChatPublisher`, which resizes it to the current upload-safe size before uploading to WeChat.

This means AI cover generation should be introduced before the existing upload stage, and it should output a normal local image file so the rest of the publishing pipeline stays unchanged.

## Scope

- Add a shared AI cover generation module for both publish entry points.
- Call Bailian image generation with `wan2.7-image-pro`.
- Generate image prompts from article `title + digest`.
- Download the generated image locally before publish.
- Normalize the generated image to the required cover ratio and current WeChat-safe output size.
- Fall back automatically to the existing solid-color cover when AI cover generation fails.

## Non-Goals

- No changes to article text generation behavior.
- No redesign of the WeChat upload flow.
- No provider abstraction for multiple image vendors in this iteration.
- No user-facing prompt editing UI in this iteration.

## External API Assumptions

Based on the current Alibaba Cloud official documentation:

- `wan2.7-image-pro` is available through the image generation API.
- The API supports custom output width and height, including wide ratios compatible with `2.35:1`.
- Returned image URLs are temporary and must be downloaded immediately.
- Actual generated dimensions can vary slightly from the requested size.

Design implication:

- Request a near-target wide image from the model, then perform final local crop and resize to guarantee stable downstream behavior.

## Proposed Architecture

### 1. Shared API Client Extension

Extend `utils/dashscope_api.py` with a dedicated image-generation method.

Responsibilities:

- Build and send the Bailian request for image generation.
- Poll or wait for completion if the API is asynchronous.
- Parse the response and return the generated image URL or URLs.
- Keep HTTP/API concerns out of business logic.

Non-responsibilities:

- Prompt composition
- Downloading files
- Image post-processing
- Fallback behavior

### 2. Shared Cover Service

Add `utils/cover_generator.py` as the single entry point for cover generation.

Suggested interface:

```python
generate_cover(title: str, digest: str) -> str
```

Return value:

- Absolute or local filesystem path to the final cover image file.

Responsibilities:

- Build a stable image prompt from `title + digest`.
- Add fixed style guidance: text-free, fresh, healing, suitable for a WeChat article cover.
- Call the DashScope image-generation client.
- Download the first usable image result to a temporary local file.
- Validate the downloaded file.
- Crop and resize the image to the final output size.
- Fall back to the existing solid-color cover if any step fails.
- Emit structured logs describing whether AI cover generation succeeded or which stage fell back.

### 3. Publishing Entry Points

Update both entry points to call the shared cover service instead of generating covers inline:

- `generate_promo.py`
- `scheduler_app.py`

Desired effect:

- Both manual and scheduled publishing use identical cover behavior.
- Cover-generation logic is no longer duplicated across entry points.

### 4. Existing WeChat Publisher

`utils/wechat_publisher.py` remains the upload boundary.

It should continue receiving a normal file path for `cover_image`, so the upload pipeline does not need structural changes.

## Prompt Design

The prompt should be generated from:

- article title
- article digest

The prompt should explicitly instruct the model to produce:

- no text, typography, logo, watermark, or caption inside the image
- calm, clean, fresh, emotionally warm visual tone
- cover-suitable composition with clear focal subject and negative space
- high-quality horizontal composition for article cover usage

Prompt strategy:

- Use a fixed style wrapper plus the content-specific title and digest.
- Keep the prompt deterministic and concise to reduce drift.
- Do not inject full article content in this iteration.

## Image Size Strategy

User requirement:

- final visual ratio should be `2.35:1`

Repository constraint:

- current WeChat upload flow standardizes cover images to `900x383`

Design decision:

- Request `2350x1000` from Bailian to stay close to `2.35:1`.
- After download, perform local center-crop and resize to `900x383`.

Reasoning:

- The model can be asked for the target ratio, but final local processing keeps the output stable even if the returned dimensions differ slightly.
- `900x383` preserves the current publishing behavior and avoids introducing new WeChat upload risk in this iteration.

## Configuration

Add an `AI_COVER_CONFIG` section to `config/config.py` and `config/config.py.example`.

Suggested fields:

- `enabled`: enable or disable AI cover generation
- `model`: default `wan2.7-image-pro`
- `width`: default `2350`
- `height`: default `1000`
- `timeout_seconds`: generation timeout bound
- `style_prompt`: fixed style supplement
- `fallback_to_default`: default `True`
- `temp_dir`: directory for downloaded and processed cover files

Behavior:

- When `enabled` is `False`, skip AI generation and use the fallback cover directly.
- When `enabled` is `True`, attempt AI generation first and fall back on failure.

## Error Handling

AI cover generation is an enhancement, not a publish blocker.

Failure policy:

- If text generation succeeds but AI cover generation fails, publishing continues with the solid-color fallback cover.
- If fallback cover generation also fails, keep the current failure behavior for missing cover assets.

Failure stages that should be logged distinctly:

- API request failure
- asynchronous task timeout or failure
- malformed API response or missing image URL
- image download failure
- invalid or unreadable image file
- crop or resize failure
- fallback generation failure

Notification behavior:

- Prefer degraded-success messaging such as "AI cover failed, used fallback cover" instead of reporting the whole job as failed.

## Data Flow

1. Promo generation produces `title` and `digest`.
2. Publishing entry point calls `cover_generator.generate_cover(title, digest)`.
3. Cover generator builds a prompt and requests a single image from Bailian.
4. The result image URL is downloaded immediately to a local temporary file.
5. The image is normalized to `900x383`.
6. The final local file path is passed into `WeChatPublisher.format_for_wechat(...)`.
7. Existing WeChat upload flow uploads the normalized cover.
8. If any AI step fails, cover generator returns a fallback solid-color cover path instead.

## Testing Strategy

Follow the existing repository testing style with focused regression coverage.

### Unit Tests

Add tests for:

- prompt building from `title + digest`
- response parsing for image generation results
- fallback path when API generation fails
- fallback path when download or post-processing fails
- final crop/resize behavior producing `900x383`

### Entry-Point Coverage

Add or update tests so both:

- manual publish flow
- scheduled publish flow

call the same shared cover-generation service.

### Test Isolation

- Mock remote API calls and downloads.
- Use temporary files for image-processing tests.
- Avoid requiring real Bailian credentials in tests.

## Open Implementation Notes

- Reuse the current solid-color cover logic rather than maintaining two unrelated fallback implementations.
- Consider moving the existing inline cover-generation code into the new shared module so fallback behavior is also centralized.
- Keep file cleanup behavior explicit so downloaded temporary images do not accumulate.
- Preserve existing publish semantics: cover generation should happen before article formatting and publish submission.

## Risks

- Bailian image APIs may be asynchronous and introduce longer publish latency than text-only generation.
- Returned response schemas may differ from text-generation schemas and require separate parsing logic.
- Temporary image URLs may expire quickly if download is delayed.
- Generated content may occasionally violate the "no text" instruction, so future iterations may need stronger prompt wording or lightweight validation.

## Recommendation

Implement a shared `cover_generator` service and route both publish entry points through it.

This is the best balance for the current repository because it:

- keeps behavior consistent across entry points
- avoids duplicating AI and fallback logic
- preserves the stable WeChat upload boundary
- adds the new capability without turning cover generation into a hard publish dependency
