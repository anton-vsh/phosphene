# Phosphene 3.0 launch thread — draft

Twelve tweets. Each ≤ 280 chars. Bracketed `[MEDIA]` notes mark where Mr Bizarro plugs a clip or screencast. Before/after framing per Mr Bizarro's brief — everything claimed here is verified against the panel as it ships.

The thread should run on `@PhospheneAI` (and optionally cross-posted to `@AIBizarrothe`).

---

## 1 — Hook

> Phosphene 3.0 ships today.
>
> A free, local video + image + character-training suite for Apple Silicon. No cloud. No subscriptions. Runs entirely on your Mac.
>
> 6-minute 7-second clips at 1024×576. Trained characters with voice. Multi-subject image composition.
>
> Thread →
>
> [MEDIA: hero clip — the cleanest 7-second character render we have, ideally with audio. Vertical or square so it autoplays on timeline.]

---

## 2 — Q8 went from "exists" to "default"

> Before 3.0: HQ mode was technically there but practically too slow to use. ~15 minutes for a 7-second clip if you were patient enough.
>
> Now: ~6 min at 1024×576 with the Codex skip-step optimization. It's the default for character renders. Q4 stays available for low-RAM Macs.
>
> [MEDIA: split-screen — Q4 distilled output on the left vs Q8 HQ on the right, same prompt + seed. Same character, sharper detail on the right.]

---

## 3 — Train your own characters

> New "Train Character" tab. Drop 30–80 photos. Click Train. Get a face LoRA + an optional voice LoRA back.
>
> Gemma 3 12B captions the dataset for you. Letterbox crop preserves wide and portrait sources. ~3 hours per character on an M4 Max 64 GB.
>
> [MEDIA: short screencast — drag images into the drop zone, click Train, jump-cut to a rendered clip of that character speaking with their trained voice.]

---

## 4 — Characters are first-class now

> Character mode used to be a chip strip buried inside the Text tab. 3.0 makes it a top-level mode with its own picker — round avatars, click to switch, music-note badge on the ones with voice.
>
> Manage modal lets you rename or delete. The picker stays visible.
>
> [MEDIA: short screencast — clicking through 5 characters, the prompt textarea auto-fills the trigger word, picker stays put.]

---

## 5 — Image Studio

> Phosphene 2.0 had no image generation. 3.0 ships an Image Studio with three engine families, all native MLX:
>
> • Qwen-Image-Edit-2511 — fast, reliable, multi-ref
> • HiDream-O1-Dev (our own MLX port) — best for multi-subject
> • FLUX.1 family via mflux
>
> [MEDIA: gallery — 6-image grid of varied looks generated in the Studio. Mix portraits, landscapes, and one multi-ref composition.]

---

## 6 — Multi-subject composition

> Want "the man from reference 1 and the woman from reference 2 at a dinner table"? Both Qwen Edit and our HiDream-O1 port handle 2–3 reference subjects natively.
>
> The panel auto-coaches the prompt format the moment you drop a second ref.
>
> [MEDIA: side-by-side — ref1 (face A) + ref2 (face B) → output with both subjects clearly composited. Use the Elon + Trump test we ran today.]

---

## 7 — HiDream-O1, ported to MLX

> HiDream released their O1 image model on May 14. We had an MLX port running on a Mac Studio five days later. 8B params, BF16 (17 GB) or Q8 (10 GB).
>
> Text-to-image, instruction edit, multi-reference subject personalization. ~67 s per 1024² on a 64 GB Mac.
>
> [MEDIA: HiDream gallery — show off the quality. Photoreal portrait at 2048², a stylized scene, a multi-subject composition.]

---

## 8 — Full panel redesign

> The Manual / Studio / Train tabs were renamed Video / Images / Train Character with new icons. Capability tier auto-detection adapts the UI to your hardware — Q4 Macs get a clean limited surface, Q8 Macs see everything.
>
> Eleven UX contradictions audited and fixed.
>
> [MEDIA: full panel screencast — sweep across the three tabs showing how each surface differs, settle on the Video tab with character picker visible.]

---

## 9 — Adaptive performance

> The wall-time estimate used to be a hardcoded baseline measured on someone else's rig. 3.0 records your actual gen times per engine and learns. After two renders the estimate matches reality.
>
> Same patterns now wire TeaCache through Extend mode for a free 1.2× speedup.
>
> [MEDIA: screen recording — submit two image gens, watch the "static" estimate flip to "observed" with the actual measured number from your machine.]

---

## 10 — Reproducibility

> Load Params on any past clip now restores the actual seed used (not the -1 random sentinel). And if the clip used a character, the form opens in Character mode with that character pre-selected. You can iterate without losing your place.
>
> [MEDIA: short screencast — click "Load Params" on a clip in the gallery, watch the entire form populate: prompt, character, quality strip, seed.]

---

## 11 — Why we built this

> Phosphene is built by one person — me. It's been four months of evenings and weekends shipping this to where it is now.
>
> The plan: a complete off-grid creator suite. Video, images, audio, character training, editing — every part of a creator's workflow, running on your Mac.

---

## 12 — How to help

> If Phosphene earns its keep on your Mac, the Patreon keeps it shipping. Tiers from $5 (Backer) to $250 (Studio) cover features, priority bug fixes, and early access to character LoRAs I train.
>
> [PATREON_URL]
>
> Install: pinokio.computer → search Phosphene. Code: github.com/mrbizarro/phosphene. Follow @PhospheneAI for releases.

---

## Notes for posting

- Tweets 2, 5, 6, 7 are the strongest "show what 3.0 does" — those need the best media.
- Tweets 8, 9, 10 are screencast-heavy. Keep each clip ≤ 15 seconds.
- Tweet 11 is the human moment. Don't dilute it with media.
- Tweet 12 is the ask. Put the Patreon link FIRST in the tweet body, not last, so it's visible in previews.
- Cross-post Tweet 1 + Tweet 12 to `@AIBizarrothe`. The rest goes only on `@PhospheneAI`.
- If thread reach is low, consider re-posting Tweet 2, 5, 6, 7 as standalone tweets the next day.
