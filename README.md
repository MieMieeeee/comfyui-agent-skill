# ComfyUI Agent Skill

This repository is an Agent Skill folder (Claude Code / Claude.ai / Agent Skills). The only required file is [SKILL.md](SKILL.md).

## Status

- Requires a local or trusted self-hosted ComfyUI server (this repo is not a hosted service).
- Stable interface: registered workflows only + CLI with structured JSON output.
- Recommended trust model: do not point this at an untrusted public ComfyUI endpoint.

## Registered Workflows

Stable (reviewed configs in `assets/workflows/*.config.json`):

- `z_image_turbo` (text-to-image)
- `klein_edit` (image edit)
- `qwen3_tts` (text-to-speech)
- `ltx_23_t2v_distill` (text-to-video)
- `ltx_23_i2v_distilled` (image-to-video)
- `ace_step_15_music` (music/audio)
- `qwen_image_2512_4step` (text-to-image)

Source of truth: the runtime registry is derived from `assets/workflows/*.config.json` (and the corresponding `assets/workflows/*.json` workflow files). If this list drifts, trust the configs and `python -m comfyui generate --help` output.

## For Skill Users (Generate / Edit / Video / Audio)

Use this when you want to run registered ComfyUI workflows via the CLI in this repo.

- Primary entry: [SKILL.md](SKILL.md)
- Workflow selection and sizing: [references/workflows.md](references/workflows.md)
- Full CLI contract (output paths, async submit/poll, JSON schemas, error codes): [references/cli.md](references/cli.md)
- Prompt enhancement playbooks: [references/prompt_enhancement/](references/prompt_enhancement/)

## Quick Start

### Option A: Use from source (repo root)

```bash
uv sync
uv run --no-sync python -m comfyui check
uv run --no-sync python -m comfyui generate -p "a cute cat sitting on a windowsill at golden hour"
```

Optional short command (after `uv sync` installs the project):

```bash
uv run --no-sync comfyui-skill check
uv run --no-sync comfyui-skill generate -p "a cute cat sitting on a windowsill at golden hour"
```

### Option B: Install as a tool (no git clone)

```bash
pipx install dist/comfyui_skill-*.whl
comfyui-skill check
comfyui-skill generate -p "a cute cat sitting on a windowsill at golden hour"
```

Or with uv:

```bash
uv tool install dist/comfyui_skill-*.whl
comfyui-skill check
comfyui-skill generate -p "a cute cat sitting on a windowsill at golden hour"
```

If you don't have a wheel yet, you can install from GitHub:

```bash
pipx install "git+https://github.com/MieMieeeee/comfyui-agent-skill.git"
```

In tool-install mode, workflows/references are read from the installed package, while writable data goes to a per-user directory:

- Windows: `%APPDATA%\\comfyui-skill`
- macOS: `~/Library/Application Support/comfyui-skill`
- Linux: `$XDG_DATA_HOME/comfyui-skill` or `~/.local/share/comfyui-skill`

## Troubleshooting

- `SERVER_UNAVAILABLE`: ComfyUI is not reachable at the target URL. Start ComfyUI or re-run with `--server http://<ip>:8188`.
- `PREFLIGHT_MISSING_NODES`: install/enable required custom nodes on the ComfyUI server.
- `PREFLIGHT_MISSING_MODELS`: download required model files on the ComfyUI server.
- `NO_OUTPUT`: workflow ran but no media could be retrieved; check the workflow output node and server logs/UI.
- For `PREFLIGHT_MISSING_NODES`, `PREFLIGHT_MISSING_MODELS`, or `NO_OUTPUT`, consult the dependency reference: [references/workflow_nodes.md](references/workflow_nodes.md).

## For Maintainers (Add / Review Workflows)

Maintenance docs are intentionally kept out of `SKILL.md` to keep the skill instructions user-focused.

- Maintainer entry: [MAINTAINER.md](MAINTAINER.md)
- Detailed workflow registration guide: [references/extension.md](references/extension.md)
