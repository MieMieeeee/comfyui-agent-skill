# Changelog

## 0.1.1 - 2026-05-02

### Reliability
- CLI stdout JSON is ASCII-safe for stability across mixed terminal/codepage environments (notably Windows CI).
- Async poll snapshot contract is unified and transient polling errors are tracked.

### Packaging
- Prepare pipx/uv tool install support: packaged workflows/references + per-user writable directories.
- PyPI package name is `comfyui-agent-skill-mie` (keeps `comfyui-skill` as a short alias).

## 0.1.0 - 2026-05-01

### Features
- Agent skill to run registered ComfyUI workflows via a stable CLI
- Supports image generation, image editing, text-to-video, image-to-video, music/audio generation, and text-to-speech
- Structured JSON results (outputs, metadata, and normalized error codes)
- Preflight checks for missing nodes/models and optional progress events for long runs

### Documentation
- User vs maintainer docs split (README.md / MAINTAINER.md)
- Workflow selection and prompt enhancement references

## Unreleased
