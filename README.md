# ComfyUI Agent Skill

This repository is an Agent Skill folder (Claude Code / Claude.ai / Agent Skills). The only required file is [SKILL.md](SKILL.md).

## For Skill Users (Generate / Edit / Video / Audio)

Use this when you want to run registered ComfyUI workflows via the CLI in this repo.

- Primary entry: [SKILL.md](SKILL.md)
- Workflow selection and sizing: [references/workflows.md](references/workflows.md)
- Full CLI contract (output paths, async submit/poll, JSON schemas, error codes): [references/cli.md](references/cli.md)
- Prompt enhancement playbooks: [references/prompt_enhancement/](references/prompt_enhancement/)

## Quick Start

From the repo root:

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
