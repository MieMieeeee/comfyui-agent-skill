# ComfyUI Agent Skill

This repository is an Agent Skill folder (Claude Code / Claude.ai / Agent Skills). The only required file is [SKILL.md](SKILL.md).

- 中文文档: [README.zh-CN.md](README.zh-CN.md)

## Status

- Requires a local or trusted self-hosted ComfyUI server (this repo is not a hosted service).
- Not a hosted generation service; this package does not provide a ComfyUI backend.
- This package does not install ComfyUI itself.
- Stable interface: registered workflows only + CLI with structured JSON output.
- Recommended trust model: do not point this at an untrusted public ComfyUI endpoint.
- PyPI package: `comfyui-agent-skill-mie` (includes `comfyui-skill` alias).

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

### Install (Recommended: pipx)

```bash
pipx install comfyui-agent-skill-mie
comfyui-agent-skill-mie check
comfyui-agent-skill-mie generate -p "a cute cat sitting on a windowsill at golden hour"
comfyui-skill check
comfyui-skill generate -p "a cute cat sitting on a windowsill at golden hour"
```

### Alternative: uv tool install

```bash
uv tool install comfyui-agent-skill-mie
comfyui-agent-skill-mie check
comfyui-agent-skill-mie generate -p "a cute cat sitting on a windowsill at golden hour"
comfyui-skill check
comfyui-skill generate -p "a cute cat sitting on a windowsill at golden hour"
```

### Source mode (for development / maintainers)

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

From a local wheel (for testing before PyPI publish):

```bash
pipx install dist/comfyui_agent_skill_mie-*.whl
```

Or install from GitHub:

```bash
pipx install "git+https://github.com/MieMieeeee/comfyui-agent-skill.git"
```

In tool-install mode, workflows/references are read from the installed package, while writable data goes to a per-user directory:

- Windows: `%APPDATA%\\comfyui-skill`
- macOS: `~/Library/Application Support/comfyui-skill`
- Linux: `$XDG_DATA_HOME/comfyui-skill` or `~/.local/share/comfyui-skill`

Short alias also available: `comfyui-skill`

## End-to-End Example (User input → decision → workflow → result)

This project is designed for agent-first workflow selection:

- The Agent makes the primary workflow decision using [SKILL.md](SKILL.md), workflow capability metadata, and [references/workflows.md](references/workflows.md).
- The CLI only provides a low-risk fallback when no explicit `--workflow` is chosen.

### 1) User input (natural language)

> "帮我做一张海报，标题写「夏日促销」，风格现代简洁，主色调蓝白。"

### 2) Decision (what gets chosen and why)

- Task type: text-to-image
- Strong cue: poster / embedded text requirement ("海报", "标题写…")
- Prefer a stronger match over the general fallback T2I workflow
- Selected workflow: `qwen_image_2512_4step`
- Size choice: `704x1280` (HD portrait preset for posters)

### 3) CLI command (agent explicitly chooses the workflow)

In this example, the agent explicitly chooses `qwen_image_2512_4step`; the CLI fallback selector is only a convenience when no explicit workflow is passed.

```bash
comfyui-skill generate \
  --workflow qwen_image_2512_4step \
  --width 704 --height 1280 \
  -p "Modern minimalist marketing poster, blue and white palette, bold Chinese title text '夏日促销', clean layout, high contrast, product-focused composition"
```

### 4) Example JSON result (stdout)

```json
{
  "success": true,
  "workflow_id": "qwen_image_2512_4step",
  "status": "completed",
  "outputs": [
    {
      "path": "C:\\\\Users\\\\<you>\\\\AppData\\\\Roaming\\\\comfyui-skill\\\\results\\\\20260504\\\\120301_<job_id>\\\\output.png",
      "filename": "output.png",
      "size_bytes": 1234567
    }
  ],
  "error": null,
  "job_id": "<prompt_id>",
  "metadata": {
    "seed": 123456789,
    "prompt_id": "<prompt_id>",
    "prompt": "Modern minimalist marketing poster ...",
    "width": 704,
    "height": 1280
  }
}
```

## Adding Your Own Workflow (User Extension Example)

If you want to add your own ComfyUI workflow and make it available as a registered workflow, treat it as “connecting a proven ComfyUI graph as a new capability”:

### 1) Create a local workflow registry directory

Choose a directory for your local workflow registrations:

```text
D:\comfyui-skill-custom\
  assets\
    workflows\
```

### 2) Import an exported ComfyUI workflow JSON

First make sure the workflow works inside ComfyUI, then export it as API-format JSON. After that, run:

```powershell
$env:COMFYUI_SKILL_ROOT="D:\comfyui-skill-custom"
python -m comfyui import-workflow .\my_workflow.json --id my_custom_workflow
```

This creates:

```text
assets/workflows/my_custom_workflow.json
assets/workflows/my_custom_workflow.config.template.json
```

### 3) Review and activate the config

- Open `assets/workflows/my_custom_workflow.config.template.json`
- Confirm the minimal required fields:
  - `description`, `capability`, `output_kind`, and the exposed inputs in `node_mapping`
- Optional: improve agent choice by adding selection metadata:
  - `intent_categories`, `input_modes`, `priority`, `keywords_any`, `selection_guidance`
- Rename the reviewed file to:

```text
assets/workflows/my_custom_workflow.config.json
```

Only `*.config.json` files are treated as registered workflows.

### 4) Run using your custom registry

Point runtime resources at your custom registry directory:

```powershell
$env:COMFYUI_SKILL_RESOURCE_ROOT="D:\comfyui-skill-custom"
comfyui-skill generate --workflow my_custom_workflow -p "test prompt"
```

If you omit `--workflow`, the CLI may apply low-risk fallback selection (for example, poster-like keywords) but it will not attempt to fully “understand” your workflow. Agent-first selection remains the intended model.

## Upgrade

If you installed via pipx:

```bash
pipx upgrade comfyui-agent-skill-mie
```

If you installed via uv tool:

```bash
uv tool upgrade comfyui-agent-skill-mie
```

## Troubleshooting

- Run an environment doctor check (server + workflow preflight):
  - `comfyui-skill doctor` (recommended)
  - `comfyui-agent-skill-mie doctor`
  - `uv run --no-sync python -m comfyui doctor` (source mode)
- If the agent/skill runs inside WSL/container/sandbox while ComfyUI runs on the host OS, `127.0.0.1` may point to the runtime itself instead of the host. Try `--server http://localhost:8188` or the host machine IP (and optionally persist it via `save-server`).
- `SERVER_UNAVAILABLE`: ComfyUI is not reachable at the target URL. Start ComfyUI or re-run with `--server http://<ip>:8188`.
- `PREFLIGHT_MISSING_NODES`: install/enable required custom nodes on the ComfyUI server.
- `PREFLIGHT_MISSING_MODELS`: download required model files on the ComfyUI server.
- `NO_OUTPUT`: workflow ran but no media could be retrieved; check the workflow output node and server logs/UI.
- For `PREFLIGHT_MISSING_NODES`, `PREFLIGHT_MISSING_MODELS`, or `NO_OUTPUT`, consult the dependency reference: [references/workflow_nodes.md](references/workflow_nodes.md).

## For Maintainers (Add / Review Workflows)

Maintenance docs are intentionally kept out of `SKILL.md` to keep the skill instructions user-focused.

- Maintainer entry: [MAINTAINER.md](MAINTAINER.md)
- Detailed workflow registration guide: [references/extension.md](references/extension.md)
