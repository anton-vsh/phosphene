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

### `[ ]` Scene-continuity recipe (no-training, ship first)

Lock two characters into the same environment across cuts using
existing Phosphene primitives — no scene-LoRA training required.
Higher quality and lower operator risk than training a scene LoRA
per location, per research conducted 2026-05-20.

Workflow:
1. Image Studio → Qwen-Image-Edit-2511 multi-ref. Drop 1–3 photos
   of the target location (the room, the lighting, the props).
   Generate a composed still with both characters present in the
   scene.
2. Pick the best still. Send to I2V (or FFLF) with no character
   LoRAs — identity is carried by the still's VAE-encoded latent,
   not by a LoRA delta.
3. Repeat for each cut with the SAME location stills as references.
   Lighting + decor stay consistent.

Effort: ~0.5–1 day, docs + a small UX pass to surface the recipe
from the Train tab (a "Lock to a location" link or hint). No code
changes to the training pipeline.

### `[ ]` Scene / location / room LoRAs (power-user follow-up)

After the no-training recipe ships, add scene LoRAs as the path for
users who want a reusable "location" they can stack with any
character. Builds on the existing style-training pipeline
(`train_type=style` already wired in `/train/start`).

Validated training recipe (per 2026-05-20 research):
- Dataset: 15–20 stills of one place, 4–8 angles, mix of with-people
  / empty-room (60-70% / 30-40%)
- Caption format: describe what VARIES across stills (lighting,
  framing, who's in frame) but NOT the room itself — the trigger
  carries the room. ("Caption everything your LoRA is *not*
  supposed to control" — Civitai/Hunyuan rule of thumb.)
- Resolution: 1024×576 widescreen (matches inference aspect; needs
  the widescreen-training support from commit `3f49ca3`).
- Preset: Quick (rank 16, 600 steps from 30 epochs × 20 imgs) at
  ~30 min wall on M4 Max 64GB.

Stacking with character LoRAs:
- Documented LTX guidance: keep total combined strength under 2.0,
  practical sweet spot below 1.5.
- Starting weights: character 0.9–1.0, scene 0.5–0.7. The character
  LoRA's larger weight deltas need the scene to be turned down so
  the scene effect isn't drowned (matches the 2026-05-20 elontrn
  diag observation about strength dominance).
- Reduce `strength_clip` on the scene LoRA before `strength_model`
  if the room effect is still too faint.

Engineering: ~1.5 days. Extend `TRAIN_TYPES` to include `scene`,
add a fallback caption body string, add a "Locations" subnav under
the Train tab. Touch points: `mlx_ltx_panel.py:785-801, 818, 5241,
5260, 5295-5358` and `lora_lab/train_character.py:277-290`.

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

### `[~]` IC-LoRA pipeline support — HDR ships first, generic infra follows

Research summary (`/tmp/phosphene-walk/ic_vs_id_lora_research.md`):
IC-LoRA is just a regular LoRA delta + a training-data trick + an
inference-time input contract. The DiT itself isn't modified — what
changes is that reference frames are concatenated to noise tokens along
the sequence axis at negative RoPE positions, and the LoRA learns to
copy structure / identity / look from one half to the other via
attention. The HDR LoRA additionally bakes a LogC3 inverse transform
into the decode path to recover 16-bit linear HDR from the VAE's
`[-1, 1]` output range. The upstream MLX port already has the pieces:

- `ltx_pipelines_mlx.ic_lora.ICLoraPipeline` — generic IC-LoRA pipeline
- `ltx_pipelines_mlx.hdr_ic_lora.HDRICLoraPipeline` — HDR subclass that
  auto-detects the LogC3 config from LoRA safetensors metadata and
  saves both an SDR MP4 preview + a companion `.hdr.npz` float32 HDR
  tensor (F, H, W, 3 linear scene-light)
- `ltx_pipelines_mlx.iclora_utils.append_ic_lora_reference_video_conditionings`
  — handles reference-video encoding + RoPE positioning. Tolerates an
  empty `video_conditioning=[]` (text-driven mode: LoRA delta still
  applies, no IC reference needed).

Plan in phases, each shippable on its own:

**Phase 1 — HDR text-driven mode (v3.x).** Re-expose the HDR pill in
the UI. When checked, route the job to a new `generate_hdr` helper
action that instantiates `HDRICLoraPipeline` with the Lightricks HDR
LoRA and an empty `video_conditioning`. Output is the standard SDR
MP4 (LoRA still influences the look via weight delta) plus a sidecar
`.hdr.npz`. Force `quality=balanced` (distilled Q4) since IC-LoRAs
require the distilled checkpoint per upstream docs. Block HDR +
character LoRA stacking with a clear error message (validated as
non-functional combo for v3.x).

**Phase 2 — Reference-video conversion mode (v3.x+).** Add a
reference-video picker that appears when HDR is on, populated by:
(a) recent video outputs from the gallery, or
(b) a fresh file drop.
The reference goes into `video_conditioning=[(path, 1.0)]`. This is
the SDR → HDR re-grade path: take an existing video output, re-encode
through HDR for 16-bit linear output.

**Phase 3 — Motion-Track and Union-Control IC-LoRAs.** Two more
Lightricks IC-LoRAs at `Lightricks/LTX-2.3-22b-IC-LoRA-Motion-Track-Control`
and `Lightricks/LTX-2.3-22b-IC-LoRA-Union-Control`. Both need a
reference video with specific conditioning content (motion-track
needs sparse colored splines from a tracker like SpatialTrackerV2;
union-control needs canny+depth+pose). For Phosphene users this
means we need to either (a) ship spline/depth/pose extractors as a
pre-processing pass, or (b) accept user-provided reference videos.
Likely (b) for v3.x, (a) as a stretch.

**Phase 4 — IC-LoRA training.** Extend `lora_lab` with a paired-dataset
trainer. Each sample is `(reference_clip, target_clip)`. Training loop
builds `concat(ref_tokens_at_negative_RoPE, target_tokens)` and
computes loss only on the target half. LoRA weights file stays a
normal `.safetensors`. Add `train_type='iclora'` to the trainer UI.

**Phase 5 — Character + IC-LoRA stacking.** The prize: stack a
character LoRA (face identity) with an IC-LoRA (e.g. Union-Control)
on the same DiT. Both are weight deltas so it's mechanically possible,
but untested upstream — deltas may fight, distilled-only constraint
limits to balanced quality. Experimental; gate behind a flag until
results are validated.

**Naming note.** Don't conflate "ID-LoRA" with "character LoRA".
The published ID-LoRA (arXiv 2603.10256) is actually an IC-LoRA that
conditions on a reference image + ~5s audio for talking-head video.
Phosphene's character LoRAs are plain weight-delta LoRAs trained on
15-50 photos with a trigger word — Lightricks calls these "character
LoRAs" formally, never "ID-LoRA". Keep "character LoRA" in code and
UI to avoid the collision.

Tracking: the HDR-specific Phase 1 work landed via re-exposing the
hdr toggle (commit `<hdr-ship>`); the generic Phases 2–5 stay open
in this entry.

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
