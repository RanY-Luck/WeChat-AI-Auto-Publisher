# Discussion Title And Cover Pool Design

## Goal

Refocus generated articles toward discussion-driving relationship and family topics by forcing a fixed provocative title pattern and replacing hot-topic cover selection with a local operator-managed cover pool.

## User Requirement

- Final article titles must use the exact pattern `发现中国有一个奇怪的现象：xxx`
- `xxx` should come from the current topic directly, not from a second model-generated rewrite
- Covers should come from a local folder that the operator uploads manually
- Each run should randomly choose one local cover asset
- The selected cover must be turned into a publishable cover image for the current article instead of being used raw

## Scope

- Replace the final title formatter used by the article-generation flow
- Add a local cover-pool configuration entry
- Add cover-pool selection and publish-cover rendering logic
- Wire the new title and cover behavior into the scheduled `job()` flow
- Add regression tests for title formatting, cover-pool selection, and job integration

## Non-Goals

- No admin UI for managing cover assets
- No attempt to infer the best cover per topic
- No fallback to Weibo hot-topic images for this mode
- No free-form title style switching inside one run

## Title Model

The model may still generate digest, tags, and content, but the final published title should no longer follow the existing `远方夜听 ... | ...` pattern.

Instead, title assembly becomes deterministic:

- Input: current chosen topic text
- Output: `发现中国有一个奇怪的现象：{normalized_topic_fragment}`

Normalization should be conservative:

- trim surrounding whitespace
- collapse repeated internal whitespace
- remove obvious trailing punctuation that would produce awkward doubled punctuation
- preserve the original topic meaning instead of inventing a new claim

This means the model is no longer the source of truth for final title wording.

## Cover Source Model

The scheduler should use a local filesystem directory as the only cover source for this discussion-oriented mode.

Behavior:

- read the configured cover-pool directory
- discover supported image files
- randomly choose one image for the current run
- fail clearly if the directory is missing, empty, or contains no valid images

The operator controls the visual style by curating this directory manually.

## Publish Cover Rendering

The chosen pool asset is only a base image. The actual publish cover should be rendered as a new file for the current run.

Rendering responsibilities:

- open the chosen base image
- crop/resize it to the required WeChat cover ratio
- overlay the final deterministic title on the image
- save a temporary publish-cover file
- return that file path to the existing publisher flow

The rendered cover file should be cleaned up even if the publish flow fails later.

## Configuration

Add additive config fields under `PUBLISH_CONFIG`:

- `discussion_title_enabled`: whether to force the provocative title pattern
- `discussion_cover_pool_dir`: local directory containing uploaded cover assets

Behavior rules:

- when `discussion_title_enabled` is true, the final published title must always use the fixed pattern
- when `discussion_cover_pool_dir` is set, the scheduler should use the local cover pool instead of Weibo cover resolution
- if the configured cover pool is unusable, the job should fail fast with a clear notification instead of silently falling back to unrelated images

## Execution Flow

For each scheduled run:

1. choose topic
2. generate content/digest/tags
3. derive the final deterministic title from topic
4. choose one base image from the local cover pool
5. render a publish cover with the final title overlaid
6. pass the final title and rendered cover into the existing WeChat draft publish flow

This keeps the rest of the workflow unchanged while altering the editorial positioning.

## Testing Strategy

Add regression tests that cover:

- deterministic title formatting from a raw topic string
- local cover-pool discovery and random selection
- rendered publish cover must be a new output file, not the original pool asset path
- `job()` must pass the deterministic title to the publisher and use the rendered cover path
- temporary rendered cover files are cleaned up after success and failure

Tests should avoid real network or model calls by isolating title and cover logic behind pure helpers and mocks.

## Risks

- A fixed title pattern may become repetitive over time; this is acceptable because the user explicitly wants consistency over variety
- A bad operator-curated cover pool can still produce weak visual matching; this is acceptable because visual curation is intentionally manual
- If the selected base image has poor contrast, overlaid title text may be harder to read; implementation should use a stable text panel or shadow treatment to reduce this risk

## Recommended Implementation Direction

Implement small, testable helpers in `scheduler_app.py` for:

- formatting the deterministic discussion title
- discovering local cover-pool assets
- selecting a random pool asset
- rendering the final publish cover from the chosen asset and title

Then update `job()` to treat the deterministic title as the final title of record and to use the rendered local cover output for publishing.
