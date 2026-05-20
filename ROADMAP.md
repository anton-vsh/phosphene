# Phosphene roadmap

Living document. Items listed here are committed for upcoming releases but
not yet shipped. Priorities are loose — they move based on what the v3.0
post-ship feedback surfaces. Filed publicly so contributors know where the
project is going.

Status notation: `[ ]` planned · `[~]` in progress · `[x]` shipped (will
be removed from this file once it's in a stable release).

## Near term (post v3.0)

### `[ ]` Three-aspect character LoRAs (vertical / horizontal / general)

The v3.0 character training trains at 576×576 square. This works well
for square + vertical inference, but degrades on widescreen medium
shots — the LoRA never saw the 1024×576 token grid during training,
so face geometry can break in 16:9. The fix: ship three modalities.

- **General** — current behavior, trained at 576×576 square. Default,
  works adequately at every aspect.
- **Horizontal** — trained at 1024×576 (16:9). Pinned to widescreen
  inference for medium shots that need clean face detail.
- **Vertical** — trained at 576×1024 (9:16). Pinned to vertical
  social-format clips.

UI: aspect selector in the Train tab, naming convention
`<trigger>_v2[_wide|_vert].safetensors`. Character picker groups all
three variants under one character; either auto-routes by output
aspect, or shows a small chip to override.

Foundation already in: lora_lab pipeline accepts width × height
independently as of commit `3f49ca3`. Just needs the UI surface.

Estimated effort: 2–3 hours panel work + 3.5h training per variant.

### `[ ]` Scene / location / room LoRAs

Train a LoRA on photos of a single environment so character clips
can be locked to a consistent location with consistent lighting +
decor. Use case: a dialogue between two characters in the same room
across multiple cuts.

Builds on the existing style-training pipeline (`train_type=style`
already wired in `/train/start`). Open questions: minimum dataset
size, training time, and how the scene LoRA stacks with a character
LoRA at inference without one drowning the other (the
character-LoRA-dominates-style-LoRA finding from the 2026-05-20
elontrn diagnostic is the relevant prior art).

Research in progress.

### `[ ]` Multi-character workflow

A real workflow for putting two trained characters in the same
clip. The current two-LoRA stacking math produces a hybrid face
(both identities averaged at every spatial token — see the
2026-05-19 multi-character research). Path forward: Qwen-Image-Edit
multi-ref → composed still → I2V with no LoRAs (identity carried
by the still's VAE latent). The infra exists; this is mostly UX
work to make the four-step flow a single tab.

### `[ ]` Stacking-aware strength balance

When a user stacks a style or scene LoRA on top of a character LoRA,
the character's much-larger weight deltas at strength 1.0 dominate
the style/scene LoRA at strength 1.0 and the style/scene effect
disappears. UI fix: when a user adds a non-character LoRA on top of
a character, auto-reduce `character_strength` to ~0.7 with a
tooltip explaining why. Or expose a single "stylize this character"
preset that handles the math.

### `[ ]` Per-render TeaCache override on the form

The new default TC=1.8 (reverted from a wrongly-calibrated 1.0 on
2026-05-20) works well for most character renders, but power users
may want to dial it for specific scenes. Expose `teacache_thresh`
as a slider on the advanced section of the Generate form.

## Mid term

### `[ ]` In-panel "Report bug" button

Auto-zip recent panel log + system info + the most recent failed
sidecar, pre-fill a GitHub issue. Cuts the support loop from
"please paste the panel log" to one click. (Tracked partly via
issue #2 — Akossimon's pain point.)

### `[ ]` Aspect-bucketed single LoRA (alternative to three modalities)

Instead of training three separate LoRAs per character, train ONE
LoRA on a mix of aspect crops. Robust to any inference aspect at
the cost of slightly weaker per-aspect identity capture. Worth
benchmarking against the three-modality approach once both are
implemented.

### `[ ]` Audio-only LoRA training (voice without face)

The voice LoRA phase already runs as a sub-step of character
training. Expose it as a standalone train_type so a user can train
just a voice (e.g. clone a podcast host's delivery) without
gathering face photos.

### `[ ]` HiDream as a panel-internal install

HiDream-O1-Image-Dev currently requires a separate one-time clone
of the HIDREAM lab repo into `$HIDREAM_LAB_DIR`. Move this to a
standard Pinokio install button so it's one-click parity with the
mflux Qwen-Edit install.

### `[ ]` /queue/retry preserves character_strength

Currently `/queue/retry` rebuilds the form with `character_id` +
`quality` + `loras` but not `character_strength`. Once strength
balancing is exposed in the UI, retries need to round-trip it.

## Longer term

### `[ ]` Multi-keyframe interpolation surface

The SDK supports multi-keyframe interpolation (see
`docs/SDK_KEYFRAME_INTERPOLATION.md`). The panel exposes only the
first/last frame mode. Building a proper multi-keyframe timeline
UI would unlock storyboarding workflows.

### `[ ]` LoRA marketplace integration

CivitAI browsing already works for downloading LTX 2.3 LoRAs.
Adding upload (publish your trained Phosphene LoRA to CivitAI in
one click, with sidecar metadata auto-populated) closes the loop.

### `[ ]` Hosted-cloud rendering fallback

Some users run on Apple Silicon Macs that are too small for Q8 HQ.
A "render this on a beefier rented box" option (BYO HF Inference
Endpoint or Replicate) would let them author character LoRAs
locally and render at HQ remotely. Strictly opt-in — Phosphene's
core promise is local + no cloud + no API key, so this would live
behind a clearly-labeled flag.

## Won't do (until proven otherwise)

### `[x] no cuda fallback`

Phosphene is Apple Silicon + MLX by design. The performance and
unified-memory advantages on M-series chips are the entire reason
the project exists. A CUDA port would be a different project.

### `[x] no Windows / Linux build`

Same reason as above. MLX is Apple-only by Apple's design.

---

If you'd like to contribute to one of the planned items, the GitHub
issues at https://github.com/mrbizarro/phosphene/issues are the right
place — comment on a tracking issue or open a new one referencing the
roadmap entry you're picking up.
