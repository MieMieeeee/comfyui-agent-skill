---
name: comfyui
description: >
  Unified ComfyUI workflow execution skill for Agents (Claude Code / OpenCode / Hermes).
  Use when the user asks to generate an image, create a picture, produce visual content
  from a text description, or check ComfyUI server status.
  Currently supports text_to_image capability via the z_image_turbo workflow.
  Requires a running ComfyUI server (default http://127.0.0.1:8188).
---

# ComfyUI Skill

## Overview

`comfyui` is a unified ComfyUI workflow execution skill for Agents. It provides a standardized entry point for Agents to call ComfyUI workflows without understanding underlying workflow details.

**Current MVP stage:**

- Implemented capability: `text_to_image`
- Default workflow: `z_image_turbo`

**Future expansion targets:**

- `image_to_image`, `image_to_video`, `status`, `run_workflow`

## Capability Boundary

### Implemented

- Text-to-image (`text_to_image`)
- Server health check via `/system_stats`
- Registered workflow execution
- Unified structured result output

### Default Workflow

- `z_image_turbo` — text-to-image using Z-Image Turbo model

### Not Implemented

- Image-to-image, image-to-video
- Auto-discovery or auto-analysis of workflows
- Generic MCP Server
- Zero-config arbitrary workflow execution

## Prerequisites

1. ComfyUI server running (default `http://127.0.0.1:8188`)
2. Python dependency:
   ```
   pip install git+https://github.com/MieMieeeee/run_comfyui_workflow.git
   ```
3. Required models loaded. See [references/workflow_nodes.md](references/workflow_nodes.md).

## Usage

### Health Check

```bash
python scripts/run.py --check
```

### Generate Image

```bash
python scripts/run.py "a cute cat sitting on a windowsill at golden hour"
```

### Specify Workflow and Server

```bash
python scripts/run.py --workflow z_image_turbo --server http://192.168.1.100:8188 --prompt "a landscape"
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--workflow` | `z_image_turbo` | Workflow to execute |
| `--server` | `http://127.0.0.1:8188` | ComfyUI server URL |
| `--output` | `results/{workflow_id}/` | Output directory |
| `--check` | — | Health check only |

## Input

Current MVP accepts one external input:

- `prompt` (string, required) — text prompt for image generation

Other parameters (width, height, seed, negative prompt) use workflow defaults or registered config values.

## Output

Structured JSON to stdout.

Success:
```json
{
  "success": true,
  "workflow_id": "z_image_turbo",
  "status": "completed",
  "outputs": [{"path": "results/z_image_turbo/xxx.png", "filename": "xxx.png", "size_bytes": 123456}],
  "job_id": "a806c637-xxxx-...",
  "error": null,
  "metadata": {"prompt": "...", "prompt_id": "a806c637-...", "width": 832, "height": 1280}
}
```

Failure:
```json
{
  "success": false,
  "workflow_id": "z_image_turbo",
  "status": "failed",
  "outputs": [],
  "job_id": "xxxx",
  "error": {"code": "EXECUTION_FAILED", "message": "Connection refused"},
  "metadata": {}
}
```

Error codes: `EMPTY_PROMPT`, `WORKFLOW_NOT_FOUND`, `WORKFLOW_LOAD_FAILED`, `EXECUTION_FAILED`, `NO_OUTPUT`, `SAVE_FAILED`, `SERVER_UNAVAILABLE`.

## Extension

To add a new workflow:

1. Place workflow JSON in `assets/workflows/`
2. Register in `workflow_config.py`:
   ```python
   NEW = WorkflowConfig(
       workflow_id="new_wf",
       workflow_file="new_wf.json",
       output_node_title="Save Image",
       positive_prompt_node="CLIP Text Encode (Positive Prompt)",
       capability="text_to_image",
       description="Description of the workflow",
       input_schema={"prompt": {"type": "string", "required": True}},
       defaults={"width": 1024, "height": 1024},
   )
   WORKFLOW_REGISTRY["new_wf"] = NEW
   ```
3. CLI automatically supports `--workflow new_wf`

## Non-Goals

- Auto-support for arbitrary ComfyUI workflows
- Auto-parsing of arbitrary workflow node structures
- Generic MCP Server
- Full platform management UI
