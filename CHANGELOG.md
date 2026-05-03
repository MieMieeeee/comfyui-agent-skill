# Changelog

## 0.1.4 - 2026-05-03

### Documentation
- Add examples section to README with user input and output for all registered workflows.
- Show input images directly in README for image-edit and image-to-video workflows.
- Reframe music and TTS examples from user's natural language perspective.

## 0.1.2 - 2026-05-02

### Features
- Add `doctor` command to check server availability and preflight all registered workflows (nodes/models).

### Documentation
- Make `pipx` the primary recommended install path and clarify command naming and self-hosted usage.

## 0.1.1 - 2026-05-02

### Reliability
- CLI stdout JSON is ASCII-safe for stability across mixed terminal/codepage environments (notably Windows CI).
- Async poll snapshot contract is unified and transient polling errors are tracked.

### Packaging
- Prepare pipx/uv tool install support: packaged workflows/references + per-user writable directories.
- PyPI package name is `comfyui-agent-skill-mie` (keeps `comfyui-skill` as a short alias).
- Align skill metadata name with published package name: `comfyui-agent-skill-mie`.
- Make `pipx` the primary recommended install path in docs and clarify command naming and self-hosted usage.

## 0.1.0 - 2026-05-01

### Features
- Agent skill to run registered ComfyUI workflows via a stable CLI
- Supports image generation, image editing, text-to-video, image-to-video, music/audio generation, and text-to-speech
- Structured JSON results (outputs, metadata, and normalized error codes)
- Preflight checks for missing nodes/models and optional progress events for long runs

### Documentation
- User vs maintainer docs split (README.md / MAINTAINER.md)
- Workflow selection and prompt enhancement references

## 0.1.3 - 2026-05-03

### Features
- Expand workflow analyzer and preflight loader detection: UNETLoader, DualCLIPLoader, VAELoaderKJ, LoraLoaderModelOnly, LatentUpscaleModelLoader, LTXVAudioVAELoader, LTXAVTextEncoderLoader, CLIPVisionLoader.
- Structured `ModelRef` output for missing models (model type and target ComfyUI subfolder).
- Third-party custom plugin detection via `/object_info` `python_module` field.
- Handle duplicate node titles in analyzer with `#N` suffix (e.g. `Load LoRA#2`).
- Add `ltx-23-t2v` and `ltx-23-i2v` workflows replacing the previous distilled variants.
- Add `scripts/sync_package_assets.py` to keep package-internal assets in sync with repo root.

### Fixes
- Fix `ltx-23-i2v` config mapping prompt to negative prompt node instead of positive prompt node.
- Enhance `ltx-23-i2v` validate case prompt to simulate agent vision-based prompt enhancement.

### Documentation
- Clarify `qwen_image_2512_4step` is optimized for posters and images with embedded text.
- Replace all `ltx_23_*_distilled` references with `ltx-23-t2v` / `ltx-23-i2v` across docs and tests.

## Unreleased
