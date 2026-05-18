<p align="center">
  <img src="assets/phosphene_banner.png" alt="Phosphene" width="100%">
</p>

<p align="center">
  <strong>Generative video, image, and character training on your Mac.</strong><br>
  MLX. No PyTorch, no CUDA, no cloud, no API key.<br>
  <a href="https://x.com/PhospheneAI">@PhospheneAI</a> on X · <a href="https://github.com/mrbizarro/phosphene">github.com/mrbizarro/phosphene</a>
</p>

<p align="center">
  <img src="assets/screenshots/phos_01_video_tab.png" alt="Phosphene panel — Video tab" width="100%">
</p>

## You can train a character on your laptop now

Drop 15 to 50 photos of a face into the Train tab. Click Train. Walk away. About three hours later you have a character LoRA, with optional voice, both ready to use from the Video tab. The captions are written by a local Gemma 3. Nothing leaves the machine.

This is the part of Phosphene 3.0 I keep showing people first, because it's still the thing nobody believes works until they watch a clip render. A 7-second 1024x576 character clip lands in about six minutes on an M4 Max.

The panel adapts to your Mac. Under 48 GB? You get a simple surface with Q4 video and the image tab. 64 GB or more? Character training, first/last-frame keyframing, extend, and the Q8 HQ modes all show up. There is one repo and two clean surfaces. You don't have to know which one you're on.

## What's actually in there

**Video.** Text-to-video, image-to-video, and audio-to-video. Every clip comes back with synced audio in the same diffusion pass: lip-sync, footsteps, room tone, whatever the prompt described. First/last-frame keyframing and clip extension are there on the Q8 surface.

**Images.** Two engines on the same tab. Qwen-Image-Edit-2511 for instruction edits and multi-subject composition. HiDream-O1-Image-Dev for photoreal at HD (separate one-time clone — see Setup below). Both are MLX ports, so they share GPU memory cleanly when you switch between them. Cards drop into a unified gallery, and there's an Animate button on each one that pre-fills the I2V form.

**Train Character.** A full LoRA training pipeline inside the panel. Face plus optional voice from the same dataset. Letterbox crop preserves wide-shot proportions, which used to be the silent killer of identity capture. Auto-captioning runs Gemma 3 12B on-device in about ninety seconds for 37 images. The validated default (rank 32, alpha 32, 5000 steps) is the preset, and it is load-bearing. Every time I tuned it I made it worse.

**Audio-to-Video.** New as of today. Drop a WAV or MP3, optionally drop a reference image to anchor frame zero, hit Generate. The audio drives the video. Two-stage pipeline: low-res with CFG, then full-res with the distilled LoRA fused on top. Original input audio is muxed onto the result.

**LoRAs and CivitAI.** Drop `.safetensors` into `mlx_models/loras/`, or browse and install LTX 2.3 LoRAs from CivitAI inside the panel. Rename, download, and delete from each row.

## Hardware

Apple Silicon only. MLX is Apple-only by design.

| RAM | Tier | What runs |
|---|---|---|
| Under 48 GB | Compact (Q4 surface) | Text and image-to-video at smaller sizes. Image tab works. Character, FFLF, Extend, and HQ are hidden. They need Q8. |
| 48 to 79 GB | Comfortable (Q8 surface) | The canonical tier, built on M4 Max 64 GB. Everything works. FFLF and Extend capped at 768 px long side. |
| 80 to 119 GB | Roomy | Most modes at full size. FFLF and Extend up to 1024 px. |
| 120 GB+ | Studio | No size limits. |

LTX 2.3's working memory is real. Standard 1280x704 generation peaks around 22 GiB resident. HQ with the Q8 dev transformer is closer to 38 GiB. Tier detection is at boot, from `body[data-cap-tier="q4|q8"]`, and the panel hides things rather than greying them out. If you want to see what the Q4 surface looks like from a 64 GB machine, set `LTX_FORCE_CAP_TIER=q4`.

## Install

### Via Pinokio (recommended)

1. Install [Pinokio](https://pinokio.computer).
2. In Pinokio: **Discover** -> **Download from URL** -> paste `https://github.com/mrbizarro/phosphene`.
3. Click **Install**.
4. Click **Start** -> **Open Panel** -> http://127.0.0.1:8198.

Pinokio handles the hardware gate, the upstream `dgrauet/ltx-2-mlx` clone, the uv-managed Python 3.11 venv, the runtime patches, and the filtered model download (~28 GB: Q4 plus the Gemma encoder).

For the Q8 HQ tier (required for Character, FFLF, Extend), click **Download Q8** in the panel sidebar after first launch. About 37 GB, one time.

If you have a Hugging Face token, paste it under **Settings** in the panel. Downloads run roughly 10x faster, and the same token unlocks the gated LoRAs (HDR and Lightricks Control).

### Manual install

```bash
# 1. Clone Phosphene + the upstream MLX port (pinned to v0.14.0).
git clone https://github.com/mrbizarro/phosphene.git
cd phosphene
git clone https://github.com/dgrauet/ltx-2-mlx.git ltx-2-mlx
cd ltx-2-mlx && git checkout v0.14.0 && cd ..

# 2. Create the Python 3.11 venv inside ltx-2-mlx (uv-managed).
cd ltx-2-mlx
uv venv --python 3.11 --seed env

# 3. Install the MLX pipeline + trainer packages. Pin mlx to 0.31.1 —
#    0.31.2 attenuates the LTX vocoder by 22 dB.
./env/bin/uv pip install --python env/bin/python \
  'mlx==0.31.1' 'mlx-lm==0.31.1' 'mlx-metal==0.31.1'
./env/bin/uv pip install --python env/bin/python \
  ./packages/ltx-core-mlx ./packages/ltx-pipelines-mlx ./packages/ltx-trainer
./env/bin/uv pip install --python env/bin/python \
  pyyaml pydantic tqdm rich
# mlx-vlm powers Gemma 3 auto-caption. --no-deps so it doesn't drag mlx-lm past 0.31.1.
./env/bin/uv pip install --python env/bin/python --no-deps 'mlx-vlm==0.4.4'
# Agent + downloader + hub pin range.
./env/bin/pip install pillow numpy 'huggingface-hub>=1.5.0,<2.0' \
  'hf_transfer>=0.1.6' 'litellm>=1.83.14' 'smolagents>=1.24.0'
cd ..

# 4. Apply the runtime patches (idempotent, fail loud on upstream drift).
./ltx-2-mlx/env/bin/python3.11 patch_ltx_codec.py

# 5. Download the Q4 LTX weights + the Gemma 3 4-bit encoder (~28 GB total).
HF_HUB_ENABLE_HF_TRANSFER=1 ./ltx-2-mlx/env/bin/hf download \
  dgrauet/ltx-2.3-mlx-q4 --local-dir mlx_models/ltx-2.3-mlx-q4
HF_HUB_ENABLE_HF_TRANSFER=1 ./ltx-2-mlx/env/bin/hf download \
  mlx-community/gemma-3-12b-it-4bit --local-dir mlx_models/gemma-3-12b-it-4bit

# 6. (Optional) Image tab — install mflux + apply the FBCache patch.
./ltx-2-mlx/env/bin/pip install 'mflux==0.17.5'
./ltx-2-mlx/env/bin/pip install --force-reinstall --no-deps 'mflux==0.17.5'
./ltx-2-mlx/env/bin/python3.11 patch_mflux_fbcache.py

# 7. (Optional) HiDream — separate one-time clone for the photoreal engine.
#    Clone HIDREAM-O1-MLX-LAB-active into your home directory, or set
#    HIDREAM_LAB_DIR to point at it.
#    git clone <hidream-lab-repo> ~/HIDREAM-O1-MLX-LAB-active

# 8. Launch the panel.
./ltx-2-mlx/env/bin/python3.11 mlx_ltx_panel.py
```

About the version pins: `mlx 0.31.2` attenuates the LTX vocoder by 22 dB. Stay on 0.31.1. `ltx-2-mlx` is pinned to `v0.14.0` — upstream is about to ship breaking changes. `mflux 0.17.5` is the version `patch_mflux_fbcache.py` is line-targeted against.

## Using it

There are four workflow tabs at the top: **Video**, **Images**, **Audio**, **Train Character**. Each one is a single page.

<table>
<tr>
<td width="50%"><img src="assets/screenshots/phos_05_character_mode.png" alt="Video tab · Character mode — compact avatar picker"></td>
<td width="50%"><img src="assets/screenshots/phos_02_images_tab.png" alt="Images tab — multi-reference subject composition"></td>
</tr>
<tr>
<td align="center"><sub><b>Video / Character mode</b> · round-avatar picker, voice indicator, manage modal</sub></td>
<td align="center"><sub><b>Images</b> · Qwen Edit, HiDream-O1, multi-ref composition</sub></td>
</tr>
<tr>
<td width="50%"><img src="assets/screenshots/phos_03_audio_tab.png" alt="Audio tab — audio drives the generation"></td>
<td width="50%"><img src="assets/screenshots/phos_04_train_tab.png" alt="Train Character tab — dataset + auto-caption + voice LoRA"></td>
</tr>
<tr>
<td align="center"><sub><b>Audio</b> · voice or music clip drives generation; optional reference image anchors frame 0</sub></td>
<td align="center"><sub><b>Train Character</b> · drop 15-50 photos, Gemma 3 auto-captions, optional voice LoRA</sub></td>
</tr>
</table>

A few things worth knowing as you go:

- **Video, text mode.** Describe the soundscape the same way you describe the scene. The audio generation reads your prompt.
- **Video, image mode.** Prompt with motion beats, not the still-image description. About one beat per two to three seconds of clip.
- **Video, character mode.** Pick an avatar, include your trigger word in the prompt. Q8 Draft (736x416) for iteration, Q8 Pro (1024x576) for final.
- **Images.** Drop one to three references for edit or multi-ref work. Empty zone is text-only. Qwen-Image-Edit handles instructions like "change the white jacket to red" while preserving the rest of the scene.
- **Train Character.** Center crop is for tight portraits. Letterbox is for wide-shot proportions. The rank-32, alpha-32, 5000-step preset is the one I'd start with.

## Migrating from 2.0

Quit Pinokio (or the panel terminal), then **Update**, then **Start**. Renders, settings, queue, models, and LoRAs all survive (Pinokio's `fs.link` persistent drive). The first update can take a few minutes.

> **If you came from 2.0 and Train Character or auto-caption look broken after the first Update, click Update once more.** The first run uses the old 2.0 update script that already sits on your disk; only after that does the new 3.0 script land. Running Update a second time installs the trainer and mlx-vlm packages 3.0 added.

A few other things worth knowing about 3.0:

- Character is its own mode pill on Video now, not a buried chip.
- Q8 HQ is the default for character clips. The server refuses Q4 with a character selected, so identity can't silently degrade.
- TeaCache is wired through Extend and A2V stage 1.
- Vertical-player chrome lives outside the right edge, so 9:16 clips aren't covered.

## What's in the repo

- `mlx_ltx_panel.py` is the panel HTTP server. One file, around 22k lines, with HTML, CSS, and JS inlined as the page string. Worker thread plus helper subprocess management plus capability tier detection.
- `mlx_warm_helper.py` is the long-running inference subprocess. Holds T2V, I2V, Extend, HQ, and Keyframe pipelines. Reads job specs from stdin, emits events to stdout.
- `image_engine.py` dispatches the Image tab. Backends `hidream`, `mflux`, `mock`. Each spawns its own subprocess with `start_new_session=True` so `/stop` kills the whole tree.
- `patch_ltx_codec.py` applies idempotent runtime patches: lossless H.264, free-DiT-before-decode, VAE temporal streaming for long clips.
- `lora_lab/` is vendored from the [`lora-lab`](https://github.com/mrbizarro/lora-lab) authoring tree. Training works out of the box; set `LTX_LORA_LAB_ROOT` to iterate against an external clone.
- `mlx_models/` and `mlx_outputs/` both persist across Pinokio Reset via fs.link.

I also ported [HiDream-O1-Image-Dev BF16](https://huggingface.co/mlx-community/HiDream-O1-Image-Dev-mlx-bf16) (8B Qwen3-VL backbone, unified pixel-patch transformer, MIT) for the Images tab. HiDream is a separate one-time clone (see Setup below).

## License and credits

Panel: MIT, see [LICENSE](LICENSE). LTX Video 2.3 weights: Lightricks' license. MLX: Apache 2.0. Gemma 3 12B: Google's terms. PiperSR: AGPL-3.0.

Phosphene is a wrapper over good model work. The names that matter:

- [Lightricks](https://github.com/Lightricks/LTX-Video) for LTX 2.3 and the joint audio-plus-video architecture
- [@dgrauet](https://github.com/dgrauet/ltx-2-mlx) for the MLX port. The reason any of this runs on Apple Silicon.
- [Apple ML team](https://github.com/ml-explore/mlx) for MLX
- [HiDream-ai](https://huggingface.co/HiDream-ai/HiDream-O1-Image-Dev) for HiDream-O1 weights and the reference implementation
- [filipstrand/mflux](https://github.com/filipstrand/mflux) for the MLX-native FLUX and Qwen-Edit family
- [mlx-community](https://huggingface.co/mlx-community) for Gemma 3 12B 4-bit
- [ModelPiper / PiperSR](https://github.com/ModelPiper/PiperSR) for optional 2x upscale on the Apple Neural Engine
- [@cocktailpeanut](https://twitter.com/cocktailpeanut) for Pinokio

What Phosphene adds on top: persistent batch queue, warm helper subprocess, hardware-tier feature gating, lossless H.264 output with sidecars, the capability-tier UI surface, the in-panel character training pipeline, the Image tab dispatch and adaptive estimates, and the Pinokio install scripts.

## Support development

Phosphene is free and open source.

- Follow [@PhospheneAI](https://x.com/PhospheneAI) on X for releases and clips
- Patreon: https://www.patreon.com/PhospheneAI
- Issues and PRs: https://github.com/mrbizarro/phosphene

## Network note

Phosphene runs locally. No telemetry. A clean production install checks GitHub every 30 minutes for an update badge, and only touches Hugging Face or CivitAI when you download models or LoRAs. Disable the update check with `PHOSPHENE_DISABLE_VERSION_CHECK=1`. The panel binds to `127.0.0.1` with no auth. It's not designed for LAN exposure or tunneling.
