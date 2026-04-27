---
name: comfyui
description: >
  Unified ComfyUI workflow execution skill for Agents (Claude Code / OpenCode / Hermes).
  Use when the user asks to generate an image from text, edit a provided image via
  image_to_image (upload + workflow), generate a similar image from a reference picture
  (reference_to_image — Agent vision + same text_to_image flow), or check ComfyUI
  server status. Supports registered workflows; capabilities and defaults listed below.
  Requires a running ComfyUI server (default http://127.0.0.1:8188).
---

# ComfyUI Skill

## Overview

`comfyui` is a unified ComfyUI workflow execution skill for Agents. It provides a standardized entry point for Agents to call ComfyUI workflows without understanding underlying workflow details.

**Implemented capabilities:**

- `text_to_image` — generate images from text prompts (default workflow: `z_image_turbo`)
- `reference_to_image` — Agent vision + T2I, reference image **not** sent to ComfyUI
- `image_to_image` — upload input image to ComfyUI, edit via prompt while preserving pose/structure/composition (default workflow: `klein_edit`)

**`reference_to_image` (reference image → similar image via Agent vision):**

- The Agent must **view the user's reference image** (multimodal), follow [prompt_enhancement/reference_to_image.md](references/prompt_enhancement/reference_to_image.md) to produce one English prompt, then call `python -m comfyui generate` with that prompt — **same** `z_image_turbo` pipeline as `text_to_image`. The reference image is **not** sent to ComfyUI.
- **This is NOT ComfyUI image-to-image.** It preserves semantic and stylistic direction only — it does **not** guarantee preservation of exact face, pose, composition, camera angle, or background layout. See [reference_to_image.md](references/prompt_enhancement/reference_to_image.md) for details.
- **No** ComfyUI "image-to-text" or extra caption workflow: reverse-prompting is **Agent-only**.

**Future expansion targets:**

- `image_to_video`, `status`, `run_workflow`

## When to Use This Skill

### Should invoke when
- User explicitly asks to **generate an image** from a text description
- User provides a **reference image** and wants a new image in a similar style or semantic direction
- User provides an **input image** and wants to **edit** it (change style, clothing, background, etc.)
- User asks to **check ComfyUI server status**

### Should NOT invoke when
- User only asks to **write or polish a prompt** without generating
- User is only **discussing creative ideas** without requesting actual generation
- ComfyUI server is **unavailable**

## Current Stage Prohibited Assumptions

- Do NOT assume this skill supports arbitrary ComfyUI workflows — only registered ones
- Do NOT assume `reference_to_image` is equivalent to ComfyUI img2img
- Do NOT assume video generation is supported
- Do NOT assume analyzer-generated configs can be used without human review
- `image_to_image` is only supported when a registered img2img workflow exists — it does not automatically apply to all edit requests
- When `check_server` fails, do NOT continue calling generation capabilities
- **Must use `uv run python -m comfyui`** for all CLI invocations. Do NOT use bare `python -m comfyui`.
- **Local `config.local.json`**: do **not** create, edit, or ask the user to change this file **unless** they explicitly want a persistent ComfyUI URL (equivalent to using `--save-server` / `python -m comfyui save-server` themselves). For one-off or Agent runs, prefer `COMFYUI_URL` or `--server` on the CLI. The file is git-ignored; see [VENDORING.md](VENDORING.md) for the optional `COMFYUI_CONFIG_FILE` test override.

## Design Principles

1. **Health check depends on `/system_stats`**: `check_server()` relies on the target ComfyUI environment providing `GET /system_stats`. This is a known convention of the current target runtime, not a universal assumption. If adapting to other ComfyUI environments in the future, the health check strategy may need extension.
2. **Input images: upload only, no preprocessing**: For `image_to_image` and similar capabilities, the Skill only validates file existence, uploads to ComfyUI, and binds the upload result to the configured node parameter. The Skill does **not** perform resize, crop, pad, dimension inference, or any image preprocessing. All size/ratio/latent handling is the responsibility of the specific workflow's internal nodes.

## Capability Boundary

### Core Workflow Capabilities
- Text-to-image (`text_to_image`) — generate images from text prompts via registered ComfyUI workflows
- Image-to-image (`image_to_image`) — upload input image to ComfyUI, edit via prompt with stronger structural guidance than `reference_to_image`; actual preservation depends on the registered workflow. Default workflow: `klein_edit` (Flux2-Klein).

### Agent Enhancement Capabilities
- **Reference-guided image generation** (`reference_to_image`): Agent uses vision to derive a prompt from a user-provided reference image, then runs the same `z_image_turbo` via `python -m comfyui generate` as T2I. Preserves semantic/stylistic direction only — **not** structural or identity-level similarity. **This is NOT ComfyUI img2img.** If the user requires structural fidelity (preserving face, pose, composition, clothing changes), use `image_to_image` instead.

### Operational Capabilities
- Server health check via `/system_stats` (`--check`)
- Save ComfyUI server URL for future use (`--save-server`)
- Workflow analyzer: auto-generate config JSON from workflow JSON for review

### Capability Comparison

| Dimension | `text_to_image` | `reference_to_image` | `image_to_image` |
|-----------|----------------|---------------------|------------------|
| Input | Text prompt | Reference image (Agent vision) + text | Input image (uploaded to ComfyUI) + text |
| ComfyUI receives image? | No | No | **Yes** |
| Implementation | z_image_turbo workflow | Same z_image_turbo workflow | Dedicated img2img workflow |
| Structural fidelity | N/A | Weak — semantic/stylistic direction only | Strong — depends on workflow |
| When to use | "Generate a cat" | "Make something similar to this photo" | "Edit this image", "Change clothes" |

### Default Workflow

- `z_image_turbo` — text-to-image using Z-Image Turbo model (used for both `text_to_image` and `reference_to_image`)

### Not Implemented

- Image-to-video in this skill
- Generic MCP Server
- Zero-config arbitrary workflow execution

## Prerequisites

1. **ComfyUI server** running with `GET /system_stats` endpoint available.
   URL resolution (priority): `--server` CLI flag > `COMFYUI_URL` env var > `config.local.json` > default `http://127.0.0.1:8188`.
   Override config path for tests with env **`COMFYUI_CONFIG_FILE`** (points to a temp JSON file).

2. **Python 3.10+** + **uv**. Install uv if not present:
   ```bash
   pip install uv
   ```

3. **Setup (from skill root — the folder containing `SKILL.md` and `scripts/`):**
   ```bash
   uv sync                          # create .venv, install deps + pytest
   uv run python -m comfyui --help # verify installation
   ```

4. **Vendored Comfy API client**: [`comfy_api_simplified`](https://github.com/MieMieeeee/run_comfyui_workflow) is included under `scripts/comfy_api_simplified/` — no network install needed. See [VENDORING.md](VENDORING.md) to re-sync.

5. **Required models**: see [references/workflow_nodes.md](references/workflow_nodes.md).

## Usage

### Fail-Fast Rules (Required)

**ComfyUI / `python -m comfyui generate` (stdout JSON from the CLI):**

- If ComfyUI server is unavailable, **return `SERVER_UNAVAILABLE` immediately**.
- If workflow is not registered, **return `WORKFLOW_NOT_REGISTERED` immediately**.
- If prompt is missing, **return `EMPTY_PROMPT` immediately**.
- Do **not** search local disk/network for ComfyUI install path or alternative servers.
- Do **not** auto-switch workflow/server silently; fail with explicit JSON error.

**Agent-only (before calling `python -m comfyui generate` for `reference_to_image`):**

- If the user did not provide a **reference image** (or it is unusable), stop and return **`NO_REFERENCE_IMAGE`** (see [Agent error output](#agent-error-output) below). Do not call `python -m comfyui generate`.
- If the runtime **cannot** accept or interpret images (no vision / multimodal), stop and return **`VISION_UNAVAILABLE`**. Do **not** add ComfyUI "caption/interrogate" workflows, scan disk for Comfy install paths, or ask the user to install reverse-prompt nodes. Do not call `python -m comfyui generate`.
- After a valid English prompt is produced, failures are reported **only** via the usual `python -m comfyui generate` JSON (`SERVER_UNAVAILABLE`, etc.).

### Handling `SERVER_UNAVAILABLE`

When `python -m comfyui generate` returns `SERVER_UNAVAILABLE`, the Agent should **help the user diagnose** rather than just reporting the error. Ask the user:

1. **Is ComfyUI running locally?** — If not, the user needs to start it first.
2. **Is ComfyUI on a different machine?** — If so, ask for the address, save it with `--save-server`, then retry.

Example Agent response:
```
ComfyUI server at http://127.0.0.1:8188 is not responding. A few common causes:

1. ComfyUI hasn't been started yet — please start it and try again
2. ComfyUI is running on a different machine or port — tell me the address and I'll save it for future use

Which is your situation?
```

When the user provides a remote address, the Agent should:
1. Save it: `python -m comfyui generate --save-server http://<address>:<port>` 或 `python -m comfyui save-server http://<address>:<port>`
2. Retry the original generation command (no `--server` needed — it's now saved)

Do **not** search the local filesystem for ComfyUI installations. Do **not** guess or try alternative ports.

### Health Check

```bash
python -m comfyui generate --check
# 或 (推荐已 pip install -e .):
python -m comfyui check
```

### Generate Image

```bash
python -m comfyui generate "a cute cat sitting on a windowsill at golden hour"
# 或:
python -m comfyui generate -p "a cute cat sitting on a windowsill at golden hour"
```

`--output` 语义：不传时默认保存到 `results/<workflow_id>/`（即技能目录）。传入相对路径时会拼到该目录下（如 `--output my_folder` → `results/<workflow_id>/my_folder/`）。传入绝对路径时直接透传。图片文件名由 ComfyUI/工作流决定，不由本参数指定。

长耗时生成时可打开 **进度**（WebSocket 事件以 JSON 行输出到 **stderr**）:

```bash
python -m comfyui generate "prompt" --progress
python -m comfyui generate -p "prompt" --progress
```

程序化调用（Agent / 服务）可传 `execute_workflow(..., progress_callback=fn)`，参数为 `dict`（`phase` 如 `queued`、`executing`、`status`、`finished` 等）。

### Specify Workflow and Server

```bash
python -m comfyui generate --workflow z_image_turbo --server http://192.168.1.100:8188 --prompt "a landscape"
python -m comfyui generate --workflow z_image_turbo --server http://192.168.1.100:8188 -p "a landscape"
```

### Save server (CLI)

```bash
python -m comfyui generate --save-server http://192.168.1.100:8188
python -m comfyui save-server http://192.168.1.100:8188
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--workflow` | `z_image_turbo` | Workflow to execute |
| `--prompt`, `-p` | — | Prompt text (alternative to positional prompt) |
| `--image` | — | `key=path` or bare path; repeat for multiple keys (I2I workflows) |
| `--count` | `1` | Number of images to generate |
| `--server` | config or `http://127.0.0.1:8188` | ComfyUI server URL (this invocation only) |
| `--save-server` | — | (`python -m comfyui generate` only) Save server URL to `config.local.json`; use `python -m comfyui save-server URL` for the module form |
| `--output` | `results/<workflow>/` | Relative path → appended to default dir; absolute path → used as-is. Omit to use default. Filename chosen by ComfyUI/workflow. |
| `--check` | — | Health check only (`python -m comfyui generate`); use `python -m comfyui check` as alternative |
| `--progress` | off | Print JSON progress lines to stderr during generation |

## Input

- `prompt` (string, required) — text prompt for image generation
- `image` inputs (optional) — for workflows with `value_type: image` in `node_mapping` (e.g. `klein_edit`), pass local file paths via `--image key=path` or a single bare path when the workflow has exactly one image role. See [node_mapping](#node_mapping-schema) and Examples under Prompt Enhancement.

Width, height, and negative prompt are configured per-workflow via `node_mapping` in the config JSON (not exposed as CLI flags). In current built-in workflows, seed is auto-randomized unless the workflow config specifies otherwise.

## Prompt Enhancement

Before calling `python -m comfyui generate`, enhance the user's prompt using the appropriate enhancement instructions:

1. Determine the image type based on user intent
2. Read the corresponding enhancement instructions from `references/prompt_enhancement/`
3. Follow the instructions to expand the user's simple description into a detailed prompt
4. Call `python -m comfyui generate` with the enhanced prompt

**`reference_to_image` order (Agent must have vision for the reference image):**

1. Ensure reference image is present; else return `NO_REFERENCE_IMAGE`.
2. Read [prompt_enhancement/reference_to_image.md](references/prompt_enhancement/reference_to_image.md).
3. Synthesize one English prompt from the **image** + user's short text (e.g. "类似""同风格"); if vision is unavailable, return `VISION_UNAVAILABLE` and **do not** call `python -m comfyui generate`.
4. `python -m comfyui generate "<enhanced English prompt>"` from skill root (same as T2I).

Available enhancement types:

| Type | File | Use when |
|------|------|----------|
| `character` | [prompt_enhancement/character.md](references/prompt_enhancement/character.md) | User asks for portrait, person, character, figure photo |
| `reference_to_image` | [prompt_enhancement/reference_to_image.md](references/prompt_enhancement/reference_to_image.md) | User provides a **reference image** and wants a new image in a similar **semantic/stylistic direction** (not structural fidelity) |
| `image_to_image` | [prompt_enhancement/image_to_image.md](references/prompt_enhancement/image_to_image.md) | User provides an **input image** and wants to **edit** it (change style, clothing, background, etc.) |

Example flow (`text_to_image` / `character`):
```
User: "生成一个穿黑色皮衣的女孩"
  → Type: character
  → Read references/prompt_enhancement/character.md
  → Enhance: "Photorealistic, ultra-detailed portrait of a young woman..."
  → Call: python -m comfyui generate "Photorealistic, ultra-detailed portrait of a young woman..."
```

Example flow (`reference_to_image`):
```
User: [image] + "生成一个类似的图"
  → Preconditions: can view image; else VISION_UNAVAILABLE or NO_REFERENCE_IMAGE
  → Type: reference_to_image
  → Read references/prompt_enhancement/reference_to_image.md
  → Enhance from vision + user text: "Photorealistic, ultra-detailed ..." (one paragraph)
  → Call: python -m comfyui generate "Photorealistic, ultra-detailed ..."
```

Example flow (`image_to_image`):
```
User: [image] + "换成职业装"
  → Type: image_to_image
  → Read references/prompt_enhancement/image_to_image.md
  → Enhance: Agent analyzes image + user intent → "Change only the clothing to a tailored charcoal..."
  → Call: python -m comfyui generate --workflow klein_edit --image input_image=photo.png --prompt "Change only the clothing..."
```

## Output

### Agent error output

When the failure is **not** from `python -m comfyui generate` (missing reference image, or no vision), return a small JSON object so callers do not confuse it with Comfy errors:

```json
{
  "source": "agent",
  "success": false,
  "error": {"code": "VISION_UNAVAILABLE", "message": "Cannot read reference image in this runtime."}
}
```

Codes: `NO_REFERENCE_IMAGE` (no attachment/path or empty), `VISION_UNAVAILABLE` (multimodal/vision not available or image unreadable). Do not use `SERVER_UNAVAILABLE` here; that is reserved for Comfy/CLI.

### `python -m comfyui generate` (ComfyUI) JSON

Structured JSON to **stdout** from the CLI (success or Comfy-related failure).

#### After Success: Presenting Results to User

When `python -m comfyui generate` returns `"success": true`, the Agent **should present the generated image(s) to the user**:

1. **If the Agent can display images** (e.g. Read tool supports image files, multimodal output): read the file at `outputs[].path` and display it directly to the user.
2. **If the Agent cannot display images**: report the file path(s) to the user so they can open them manually.

Do **not** just silently parse the JSON and move on — the user expects to see or know about the result.

Success:
```json
{
  "success": true,
  "workflow_id": "z_image_turbo",
  "status": "completed",
  "outputs": [{"path": "results/z_image_turbo/xxx.png", "filename": "xxx.png", "size_bytes": 123456}],
  "job_id": "a806c637-xxxx-...",
  "error": null,
  "metadata": {"prompt": "...", "prompt_id": "a806c637-...", "width": 832, "height": 1280, "seed": 12345}
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

Error codes: `EMPTY_PROMPT`, `CONFIG_ERROR`, `MAPPING_NOT_FOUND`, `WORKFLOW_NOT_REGISTERED`, `WORKFLOW_FILE_NOT_FOUND`, `WORKFLOW_LOAD_FAILED`, `EXECUTION_FAILED`, `NO_OUTPUT`, `SAVE_FAILED`, `SERVER_UNAVAILABLE`, `NO_INPUT_IMAGE`, `INPUT_IMAGE_NOT_FOUND`, `IMAGE_UPLOAD_FAILED`, `INVALID_PARAM`, `INVALID_PARAM_TYPE`.

Planned error codes: `NODE_NOT_FOUND`, `PARAM_NOT_FOUND`.

Common issues:
- `SERVER_UNAVAILABLE`: ComfyUI not running at the configured address — start it first
- `WORKFLOW_NOT_REGISTERED`: this workflow is not currently supported by the skill. For maintainers: register it by adding a reviewed `*.config.json` under `assets/workflows/`.
- `WORKFLOW_FILE_NOT_FOUND`: workflow JSON file missing from `assets/workflows/`
- `NO_OUTPUT` / nodes red in ComfyUI UI: model files missing — check [references/workflow_nodes.md](references/workflow_nodes.md)

For `--count > 1`, output format is:
```json
{
  "count": 2,
  "success": true,
  "results": [{ "...": "single-result-schema" }, { "...": "single-result-schema" }]
}
```

## Extension

### Adding a New Workflow

1. Place workflow JSON in `assets/workflows/`
2. Run the analyzer to auto-generate a config template:
   ```bash
   uv run python scripts/analyze_workflow.py assets/workflows/new_workflow.json
   ```
   This creates `assets/workflows/new_workflow.config.json` with discovered nodes and mapped params.
3. Review and edit the generated config:
   - Fill in `capability` and `description`
   - Verify `node_mapping` entries (the analyzer uses heuristics — confirm correctness)
   - Remove `_discovered_nodes` (review-only section)
4. After the config is manually reviewed and kept, the workflow becomes available via `--workflow new_workflow`

### node_mapping Schema

Each workflow config uses a `node_mapping` dict that maps parameter roles to workflow nodes:

```json
{
  "prompt": {"node_title": "CLIP Text Encode (Positive Prompt)", "param": "text", "value_type": "string", "required": true},
  "negative_prompt": {"node_title": "CLIP Text Encode (Negative Prompt)", "param": "text", "value_type": "string"},
  "seed": {"node_title": "KSampler", "param": "seed", "value_type": "integer", "auto_random": true},
  "width": {"node_title": "EmptySD3LatentImage", "param": "width", "value_type": "integer", "default": 832},
  "height": {"node_title": "EmptySD3LatentImage", "param": "height", "value_type": "integer", "default": 1280},
  "input_image": {"node_title": "Load Image", "param": "image", "value_type": "image", "input_strategy": "upload", "required": true}
}
```

Each mapping entry: `{"node_title": str, "param": str, "value_type"?: str ("string"|"integer"|"image"), "input_strategy"?: str ("upload"|"direct"), "required"?: bool, "auto_random"?: bool, "default"?: any}`

The dict key is the **role name** used in CLI `--image key=path` and executor `input_images`. For example, `"input_image"` in node_mapping means `--image input_image=photo.png`.

- `input_strategy: "upload"` — upload file to ComfyUI first, then set param to `"{subfolder}/{name}"` (for image types)
- `input_strategy: "direct"` — set param value directly (default for string/integer types)

## Non-Goals

- Auto-support for arbitrary ComfyUI workflows
- Auto-parsing of arbitrary workflow node structures
- Generic MCP Server
- Full platform management UI

## Reference

- Detailed architecture and design docs: `00-说明索引.md` ~ `05-*.md` in the project root
- Workflow node reference: [references/workflow_nodes.md](references/workflow_nodes.md)
- Tests: `pytest scripts/tests/` — run before modifying executor or config
