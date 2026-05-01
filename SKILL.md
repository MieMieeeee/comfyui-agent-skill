---
name: comfyui
description: >
  Unified ComfyUI workflow execution skill for Agents (Claude Code / OpenCode / Hermes).
  Use when the user asks to generate an image from text (including qwen_image_2512_4step),
  edit a provided image via image_to_image (upload + workflow), generate a similar image
  from a reference picture (reference_to_image — Agent vision + same text_to_image flow),
  text-to-video or image-to-video (LTX workflows), text-to-music (Ace Step MP3),
  synthesize speech (qwen3_tts), or check ComfyUI server status. Supports registered
  workflows only; capabilities and defaults listed below.
  Requires a running ComfyUI server (default http://127.0.0.1:8188).
---

# ComfyUI Skill

## Overview

`comfyui` is a unified ComfyUI workflow execution skill for Agents. It provides a standardized entry point for Agents to call ComfyUI workflows without understanding underlying workflow details.

**Implemented capabilities:**

- `text_to_image` — generate images from text prompts (default workflow: `z_image_turbo`; alternate registered workflow: **`qwen_image_2512_4step`** — Qwen Image 2512 4-step lightning, **`--width`/`--height`** supported, default **512×768**)
- `reference_to_image` — Agent vision + T2I, reference image **not** sent to ComfyUI
- `image_to_image` — upload input image to ComfyUI, edit via prompt while preserving pose/structure/composition (default workflow: `klein_edit`)
- `text_to_video` — text prompt → MP4 (`workflow`: **`ltx_23_t2v_distill`**). **`--width`/`--height`** 可选（**须成对**），写入工作流中的 **`EmptyImage`** 节点，经 GetImageSize 驱动整段 LTX 潜空间；**默认 768×512**（`landscape_fast`）。`assets/workflows/ltx_23_t2v_distill.config.json` 中的 **`resolution_presets`** 供 Agent 推荐档位（如 1280×704、1920×1088），**非**独立 CLI 开关。视频在 Comfy 历史中常以 **`gifs`** 键返回；技能使用 `output_kind: "video"` 拉取。
- `image_to_video` — upload **one** input image + prompt → MP4 (`workflow`: **`ltx_23_i2v_distilled`**)。工作流用 **`GetImageSize`** 读取上传图宽高，驱动 **`EmptyImage` / `ImageResizeKJv2`** 等，**导出分辨率与上传图像素一致**（**勿**用 CLI **`--width`/`--height`**，会报 `INVALID_PARAM`）。使用 `--image input_image=path`（仅一个 image 角色时可只写路径）。输入须为 Comfy/PIL 可打开的 **有效光栅图**。
- `text_to_music` — text prompt maps to **tags** on the Ace Step encoder → MP3 (`workflow`: **`ace_step_15_music`**). Use normal **`--prompt` / positional prompt**, **not** `--speech-text`/`--instruct` (those are **`text_to_speech`** only).
- `text_to_speech` — Qwen3-TTS VoiceDesign: spoken content plus voice/style **instruct** → MP3 (`workflow`: `qwen3_tts`). Requires ComfyUI custom nodes **`FB_Qwen3TTSVoiceDesign`** and **`SaveAudioMP3`** (see workflow pack used when exporting `qwen3_tts.json`).

**`reference_to_image` (reference image → similar image via Agent vision):**

- The Agent must **view the user's reference image** (multimodal), follow [prompt_enhancement/reference_to_image.md](references/prompt_enhancement/reference_to_image.md) to produce one English prompt, then call `uv run --no-sync python -m comfyui generate` with that prompt — **same** `z_image_turbo` pipeline as `text_to_image` unless the user asks for another registered T2I workflow. The reference image is **not** sent to ComfyUI.
- **This is NOT ComfyUI image-to-image.** It preserves semantic and stylistic direction only — it does **not** guarantee preservation of exact face, pose, composition, camera angle, or background layout. See [reference_to_image.md](references/prompt_enhancement/reference_to_image.md) for details.
- **No** ComfyUI "image-to-text" or extra caption workflow: reverse-prompting is **Agent-only**.

**Future expansion targets:**

- Generic `status` / `run_workflow` UX polish; additional registered workflows as needed

## When to Use This Skill

### Should invoke when
- User explicitly asks to **generate an image** from a text description
- User provides a **reference image** and wants a new image in a similar style or semantic direction
- User provides an **input image** and wants to **edit** it (change style, clothing, background, etc.)
- User asks to **synthesize speech / voice audio** from spoken script plus style instructions (use workflow `qwen3_tts` with `--speech-text` and `--instruct`)
- User asks for **text-to-video** or **image-to-video** (use `ltx_23_t2v_distill` or `ltx_23_i2v_distilled` respectively)
- User asks for **music / instrumental / song-style audio** as MP3 from a text description (use `ace_step_15_music` with `--prompt`; not the same as TTS)
- User explicitly wants **Qwen Image 2512** lightning T2I (`qwen_image_2512_4step`)
- User asks to **check ComfyUI server status**

### Should NOT invoke when
- User only asks to **write or polish a prompt** without generating
- User is only **discussing creative ideas** without requesting actual generation
- ComfyUI server is **unavailable**

## Current Stage Prohibited Assumptions

- Do NOT assume this skill supports arbitrary ComfyUI workflows — only registered ones
- Do NOT assume `reference_to_image` is equivalent to ComfyUI img2img
- Do NOT assume **arbitrary** video or music pipelines exist — only registered workflows (`ltx_23_*`, `ace_step_15_music`, etc.)
- Do NOT assume analyzer-generated configs can be used without human review
- `image_to_image` is only supported when a registered img2img workflow exists — it does not automatically apply to all edit requests
- When `check_server` fails, do NOT continue calling generation capabilities
- **Must use `uv run --no-sync python -m comfyui`** for all CLI invocations. Do NOT use bare `python -m comfyui`.
- **Local `config.local.json`**: do **not** create, edit, or ask the user to change this file **unless** they explicitly want a persistent ComfyUI URL (equivalent to using `--save-server` / `uv run --no-sync python -m comfyui save-server` themselves). For one-off or Agent runs, prefer `COMFYUI_URL` or `--server` on the CLI. The file is git-ignored; see [VENDORING.md](VENDORING.md) for the optional `COMFYUI_CONFIG_FILE` test override.

## Design Principles

1. **Health check depends on `/system_stats`**: `check_server()` relies on the target ComfyUI environment providing `GET /system_stats`. This is a known convention of the current target runtime, not a universal assumption. If adapting to other ComfyUI environments in the future, the health check strategy may need extension.
2. **Input images: upload only, no preprocessing**: For `image_to_image`, **`image_to_video`** (`ltx_23_i2v_distilled`), and similar capabilities, the Skill only validates file existence, uploads to ComfyUI, and binds the upload result to the configured node parameter. The Skill does **not** perform resize, crop, pad, dimension inference, or any image preprocessing. All size/ratio/latent handling is the responsibility of the specific workflow's internal nodes. Uploaded files must be **valid images** (Comfy/PIL-openable); corrupt or mislabeled files fail at `LoadImage`.

## Capability Boundary

### Core Workflow Capabilities
- Text-to-image (`text_to_image`) — generate images from text prompts via registered ComfyUI workflows (default `z_image_turbo`; optional **`qwen_image_2512_4step`**)
- Image-to-image (`image_to_image`) — upload input image to ComfyUI, edit via prompt with stronger structural guidance than `reference_to_image`; actual preservation depends on the registered workflow. Default workflow: `klein_edit` (Flux2-Klein).
- Text-to-video (`text_to_video`) — **`ltx_23_t2v_distill`**; 输出分辨率由 **`node_mapping` → `EmptyImage` 的 width/height** 及 CLI 覆盖决定（默认见配置；**`default_resolution` / `resolution_presets`** 为文档与 Agent 参考）。其它时长/步数等仍由工作流图决定。
- Image-to-video (`image_to_video`) — **`ltx_23_i2v_distilled`**; 必传 **`--image`**；**导出分辨率随上传图尺寸**（工作流内链路），**不支持** CLI 改宽高。
- Text-to-music (`text_to_music`) — **`ace_step_15_music`**; outputs MP3; long runs possible (workflow default duration/BPM are inside the graph unless extended via config/API later).

### Agent Enhancement Capabilities
- **Reference-guided image generation** (`reference_to_image`): Agent uses vision to derive a prompt from a user-provided reference image, then runs the same `z_image_turbo` via `uv run --no-sync python -m comfyui generate` as T2I. Preserves semantic/stylistic direction only — **not** structural or identity-level similarity. **This is NOT ComfyUI img2img.** If the user requires structural fidelity (preserving face, pose, composition, clothing changes), use `image_to_image` instead.

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

### Additional Registered Workflows

| `workflow_id` | Capability | Notes |
|---------------|------------|------|
| `qwen_image_2512_4step` | `text_to_image` | Qwen 4-step; CLI **`--width`/`--height`**；默认 **512×768**；建议档位见 config 中 `resolution_presets`（如 **704×1280** 高清） |
| `ltx_23_t2v_distill` | `text_to_video` | LTX T2V；CLI **`--width`/`--height`** 写 **`EmptyImage`**；默认 **768×512**；`resolution_presets`：landscape 快/高清/超清 |
| `ltx_23_i2v_distilled` | `image_to_video` | LTX I2V；**`--image`**；导出分辨率 **以上传图为准**（**勿**传 **`--width`/`--height`**） |
| `ace_step_15_music` | `text_to_music` | Ace Step 1.5 → MP3; **`--prompt`** supplies **tags** (not TTS flags) |

### Not Implemented

- Arbitrary unregistered ComfyUI graphs as first-class capabilities
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

3. **(Recommended for multi-agent setups)** Set `UV_PROJECT_ENVIRONMENT` to externalize the venv outside the project tree, avoiding concurrent `.venv` write conflicts:
   - **Windows:** `set UV_PROJECT_ENVIRONMENT=%LOCALAPPDATA%\comfyui-skill\venv`
   - **Linux/macOS:** `export UV_PROJECT_ENVIRONMENT=~/.cache/comfyui-skill/venv`
   - If omitted, `uv` uses the default `.venv` in the project root (fine for single-agent use).

4. **Setup (from skill root — the folder containing `SKILL.md` and `scripts/`):**
   ```bash
   uv sync                                   # create venv, install deps + pytest
   uv run --no-sync python -m comfyui --help # verify installation
   ```
   Run `uv sync` once after initial setup or dependency changes. All runtime invocations use `--no-sync` to avoid mutating the venv.

5. **Vendored Comfy API client**: [`comfy_api_simplified`](https://github.com/MieMieeeee/run_comfyui_workflow) is included under `scripts/comfy_api_simplified/` — no network install needed. See [VENDORING.md](VENDORING.md) to re-sync.

6. **Required models**: see [references/workflow_nodes.md](references/workflow_nodes.md).

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
1. Save it: `uv run --no-sync python -m comfyui save-server http://<address>:<port>`
2. Retry the original generation command (no `--server` needed — it's now saved)

Do **not** search the local filesystem for ComfyUI installations. Do **not** guess or try alternative ports.

### Health Check

```bash
uv run --no-sync python -m comfyui check
```

### Generate Image (default `z_image_turbo`)

```bash
uv run --no-sync python -m comfyui generate "a cute cat sitting on a windowsill at golden hour"
# 或:
uv run --no-sync python -m comfyui generate -p "a cute cat sitting on a windowsill at golden hour"
```

### Qwen Image 2512 (`qwen_image_2512_4step`)

Alternate **`text_to_image`** workflow; ensure models pass **`--preflight`** before long runs.

```bash
uv run --no-sync python -m comfyui generate --workflow qwen_image_2512_4step -p "English prompt, detailed scene"
# Optional resolution — fast (512×768, default) or hd (704×1280):
uv run --no-sync python -m comfyui generate --workflow qwen_image_2512_4step --width 704 --height 1280 -p "..."
```

### Text-to-video / Image-to-video (LTX)

**T2V（`ltx_23_t2v_distill`）**：宽高由 `node_mapping` 映射到 **`EmptyImage`**（驱动 GetImageSize → `EmptyLTXVLatentVideo`）。省略 `--width`/`--height` 时用配置里的 **default**；长任务请加 **`--progress`**。

**I2V（`ltx_23_i2v_distilled`）**：`node_mapping` **不含** `width`/`height`；**导出像素随上传图**，**不要**传 `--width`/`--height`。

```bash
uv run --no-sync python -m comfyui generate --workflow ltx_23_t2v_distill \
  -p "Cinematic shot: waves at sunset, slow pan, natural motion."
# 显式横屏高清（与 resolution_presets.landscape_hd 一致时）:
uv run --no-sync python -m comfyui generate --workflow ltx_23_t2v_distill \
  --width 1280 --height 704 \
  -p "Cinematic shot: waves at sunset, slow pan, natural motion."
```

```bash
uv run --no-sync python -m comfyui generate --workflow ltx_23_i2v_distilled \
  --image input_image=photo.png \
  -p "Subtle camera drift, soft daylight, preserve subject."
```

### Text-to-music (Ace Step MP3)

Use **`--prompt`** (maps to workflow **tags**). Do **not** use `--speech-text` / `--instruct` (those are **`qwen3_tts`** only).

```bash
uv run --no-sync python -m comfyui generate --workflow ace_step_15_music \
  -p "Epic orchestral trailer, rising brass, thunderous percussion, minor key."
```

**输出目录（统一产物根）：**

- **推荐：** 常规用法 **不要传 `--output`**。使用内置默认路径即可；生成成功后从 **stdout JSON** 读取 `outputs[].path`（以及 `job_id`），将**完整本地路径**告知或展示给用户。Agent 调用 CLI 时同样优先省略 `--output`，除非用户明确要求固定目录。
- **何时需要 `--output`：** 用户指定必须写入某绝对路径、或要与外部流水线对齐的目录时再传。

默认不写 `--output` 时，每次任务在技能根目录下使用独立子目录，避免长期堆积与同名覆盖：

- 路径格式：**`results/%Y%m%d/%H%M%S_{job_id}/`**
  - `job_id` 为 ComfyUI 返回的 `prompt_id`（与 JSON 里的 `job_id` 字段一致）。
  - **同一目录存放该次任务的全部产出**：图片、音频，以及后续扩展的视频或其它媒体文件（凡由本技能从 ComfyUI 拉回并保存的成品文件均在此路径下；文件名仍由工作流/节点决定）。

**`--output` 行为：**

- **不传**：使用上述默认层级（每次执行新建一层日期 + 时间 + job id 目录）。
- **相对路径**（如 `--output my_folder` 或 `batch/run1`）：在 **`…/%H%M%S_{job_id}/`** 下再追加该相对路径，即  
  `results/%Y%m%d/%H%M%S_{job_id}/my_folder/`。
- **绝对路径**：整批输出写入该目录（不再套默认日期目录）；适合固定归档位置。
- **以常见媒体扩展名结尾的路径**（如 `out.png`、`clip.mp4`）：取其**父目录**作为保存目录（与此前语义一致）。

**维护建议：** 可按日期目录 `results/YYYYMMDD/` 批量清理或归档；任务级子目录便于按 `job_id` 追溯单次运行。

长耗时生成时可打开 **进度**（WebSocket 事件以 JSON 行输出到 **stderr**）:

```bash
uv run --no-sync python -m comfyui generate "prompt" --progress
uv run --no-sync python -m comfyui generate -p "prompt" --progress
```

程序化调用（Agent / 服务）可传 `execute_workflow(..., progress_callback=fn)`，参数为 `dict`（`phase` 如 `queued`、`executing`、`status`、`finished` 等）。

### Specify Workflow and Server

```bash
uv run --no-sync python -m comfyui generate --workflow z_image_turbo --server http://192.168.1.100:8188 --prompt "a landscape"
uv run --no-sync python -m comfyui generate --workflow z_image_turbo --server http://192.168.1.100:8188 -p "a landscape"
```

### Text-to-speech (Qwen3-TTS)

Use **`--speech-text`** for the line to speak and **`--instruct`** for timbre/style/delivery (Chinese or English per model). Do **not** pass positional/`--prompt` for this workflow — use the two flags only.

```bash
uv run --no-sync python -m comfyui generate --workflow qwen3_tts \
  --speech-text "你好，这是一段测试语音。" \
  --instruct "温柔清晰的女声，语速适中。"
```

Async queue (submit without waiting):

```bash
uv run --no-sync python -m comfyui generate --submit --workflow qwen3_tts \
  --speech-text "……" \
  --instruct "……"
```

### Save server (CLI)

```bash
uv run --no-sync python -m comfyui save-server http://192.168.1.100:8188
```

### Subcommands

`python -m comfyui` supports three subcommands:

| Subcommand | Description |
|------------|-------------|
| `check` | Health check via `GET /system_stats` |
| `save-server URL` | Save server URL to `config.local.json` |
| `generate [options]` | Run a workflow (default if no subcommand given) |

Do **not** pass `--check` or `--save-server` to the `generate` subcommand — they are top-level subcommands only.

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--workflow` | `z_image_turbo` | Workflow to execute (`z_image_turbo`, `qwen_image_2512_4step`, `klein_edit`, `ltx_23_t2v_distill`, `ltx_23_i2v_distilled`, `ace_step_15_music`, `qwen3_tts`, …) |
| `--prompt`, `-p` | — | Prompt text (alternative to positional prompt). Used for T2I/T2V/I2V/music; **not** used for `qwen3_tts` (`capability: text_to_speech`) |
| `--speech-text` | — | Spoken content for **`qwen3_tts` only** |
| `--instruct` | — | Voice/style instruction for **`qwen3_tts` only** |
| `--image` | — | `key=path` or bare path; repeat for multiple keys (`klein_edit`, **`ltx_23_i2v_distilled`** `input_image`, …) |
| `--count` | `1` | Repeat count per prompt (mainly image workflows; video/music behavior follows executor) |
| `--width`, `--height` | — | **须同时传入或同时省略。** 仅适用于在 `node_mapping` 中**同时**声明了 `width` 与 `height` 的工作流（如 `z_image_turbo`、`qwen_image_2512_4step`、**`ltx_23_t2v_distill`**，写入 **`EmptyImage` 或 `EmptySD3LatentImage`**，见各 `*.config.json`）。**`ltx_23_i2v_distilled` 无宽高映射**（图生视频以上传图为准，传 CLI 宽高会 `INVALID_PARAM`）。**勿用于**：**`size_strategy: workflow_managed`**（**`klein_edit`**）、**音频输出**（`ace_step_15_music`、`qwen3_tts`）。 |
| `--server` | config or `http://127.0.0.1:8188` | ComfyUI server URL (this invocation only) |
| `--output` | （见上文）默认 `results/%Y%m%d/%H%M%S_{job_id}/` | **推荐省略。** 若指定：相对路径追加在默认任务目录下；绝对路径为固定目录。成品文件名由 ComfyUI/工作流决定；路径以返回 JSON 为准。 |
| `--progress` | off | Print JSON progress lines to stderr during generation |
| `--preflight` | — | **仅预检**：对当前 `--workflow` 的工作流 JSON 通过 Comfy `GET /object_info` 与 `GET /models` 检查节点是否已注册、加载器引用的模型是否在列表中；向 stdout 打印 JSON 后退出，**不需要** prompt（可与 `python -m comfyui generate` 或 `run.py` 同用） |
| `--skip-preflight` | off | 跳过生成与 `--submit` 前的自动预检（排障用，不推荐常开） |

在 **`GET /system_stats` 已判定可用** 之后、**真正入队/执行** 之前，默认会做一次预检；未通过时返回 `PREFLIGHT_*` 错误码（见下方 Error codes），且不会向 Comfy 提交该工作流。

## Input

- `prompt` (string, required for non-TTS media) — text prompt for image / video / music workflows (`ace_step_15_music`: mapped to **tags**)
- `image` inputs (optional / required per workflow) — for workflows with `value_type: image` in `node_mapping` (e.g. `klein_edit`, **`ltx_23_i2v_distilled`**), pass local file paths via `--image key=path` or a single bare path when the workflow has exactly one image role. See [node_mapping](#node_mapping-schema) and Examples under Prompt Enhancement.

**宽高：** 凡 `node_mapping` 中**同时**含 **`width` / `height`** 且 **`size_strategy` 不是 `workflow_managed`** 的工作流，CLI 可用 **`--width` / `--height`（必须成对）** 覆盖；省略则用配置里的 **`default`**（例如 **`z_image_turbo`** 832×1280；**`qwen_image_2512_4step`** 512×768；**`ltx_23_t2v_distill`** 768×512）。**`ltx_23_i2v_distilled`** 不映射宽高 — **导出分辨率以上传图像素为准**。**`resolution_presets` / `default_resolution`**（适用工作流）由 JSON 加载供 Agent 参考；运行时仍以 **`node_mapping` 默认值 + CLI 覆盖** 为准。**`klein_edit`**、**`ace_step_15_music`**、**`qwen3_tts`**、**`ltx_23_i2v_distilled`** **勿传** 宽高（最后一项传了会报错）。**negative prompt** 仍由工作流配置决定。**seed** 默认随机。

### 生图流程：用户输入会映射到什么（不只有提示词）

| 能力 | 用户 / Agent 侧 | 实际写入 ComfyUI 或执行器 |
|------|-----------------|---------------------------|
| `text_to_image` | 描述语句 → Prompt Enhancement 后的**正面英文 prompt**；若用户**明确要求画幅**，Agent 解析后传 **`--width W --height H`**（与默认二选一）；可选用 **`--workflow qwen_image_2512_4step`** | **Positive prompt**；**宽/高**为 CLI 指定值或工作流默认（`z_image_turbo` 832×1280；**qwen** 512×768）；**seed** 每次随机 |
| `reference_to_image` | 参考图 + 用户短语文本 | **参考图不传 ComfyUI**；仅合成 **一条英文 prompt**（视觉归纳 + 意图）；画幅处理同 `text_to_image`（默认仍走 `z_image_turbo`，除非用户明确要求 qwen） |
| `image_to_image` | **本地输入图路径** + 编辑意图 → enhancement 后的 prompt | **上传并绑定 `input_image`**；**Positive prompt**；**seed** 随机；`klein_edit` 为 **workflow_managed**，**不支持**通过本 CLI 改输出宽高 |
| `text_to_video` | 镜头与运动描述；若要档位对齐 `resolution_presets`，传成对 **`--width` `--height`** | **`ltx_23_t2v_distill`**：正/负 prompt；**`EmptyImage`** 宽高（默认 768×512）；产出 **MP4** |
| `image_to_video` | **合法图片路径** + 运动/镜头描述（**不要**传 CLI 宽高） | **`ltx_23_i2v_distilled`**：**上传** `input_image`；正/负 prompt；**导出分辨率与上传图一致**；产出 **MP4** |
| `text_to_music` | 风格/配器/BPM 意图等 **tags 式**描述（可英文） | **`ace_step_15_music`**：写入 **`tags`**（来自 `--prompt`）；**非** TTS；产出 **MP3** |

### 画幅：方图 / 横图 / 竖图（多张不同比例）

当用户明确要求例如「一张方图、一张横图、一张竖图」时，需要在 **`z_image_turbo`、`qwen_image_2512_4step`** 或其它映射了 `width`/`height` 的文生图工作流上 **分多次** 调用（每次一对 **`--width` `--height`**）。**LTX 文生视频（`ltx_23_t2v_distill`）** 若要对同一脚本尝试多种导出分辨率，同样需要 **多次调用**。**图生视频（`ltx_23_i2v_distilled`）** 导出分辨率随 **每张上传图** 变化 — 换分辨率请 **换输入图** 或在工作流侧处理，**勿**指望 CLI 宽高。当前 CLI **单次调用内** 所有 prompt 共用同一套宽高（仅适用于支持 CLI 映射的工作流）。

**推荐像素（可与模型/节点对齐微调；宜为常见对齐倍数）：**

| 意图 | 示例分辨率 | 说明 |
|------|------------|------|
| 方图 | `--width 1024 --height 1024` | 正方形 |
| 横图（横向） | `--width 1280 --height 832` | 宽 > 高 |
| 竖图（纵向） | `--width 832 --height 1280` | 与内置默认竖幅一致 |

**小结：** 用户自然语言主要变成 **正面提示词**；**图生图**上传 **用户图像**。**文生图 / LTX 文生视频**在映射了宽高时，可由 **`--width`/`--height`** 指定像素；**LTX 图生视频**以上传图为准。**负向与 seed** 仍按配置；**`klein_edit`** 为 **`workflow_managed`**，勿传宽高。

## Prompt Enhancement

Before calling `uv run --no-sync python -m comfyui generate`, enhance the user's prompt using the appropriate enhancement instructions:

1. Determine the image type based on user intent
2. Read the corresponding enhancement instructions from `references/prompt_enhancement/`
3. Follow the instructions to expand the user's simple description into a detailed prompt
4. Call `uv run --no-sync python -m comfyui generate` with the enhanced prompt

**`reference_to_image` order (Agent must have vision for the reference image):**

1. Ensure reference image is present; else return `NO_REFERENCE_IMAGE`.
2. Read [prompt_enhancement/reference_to_image.md](references/prompt_enhancement/reference_to_image.md).
3. Synthesize one English prompt from the **image** + user's short text (e.g. "类似""同风格"); if vision is unavailable, return `VISION_UNAVAILABLE` and **do not** call `python -m comfyui generate`.
4. `uv run --no-sync python -m comfyui generate "<enhanced English prompt>"` from skill root (same as T2I).

Available enhancement types:

| Type | File | Use when |
|------|------|----------|
| `character` | [prompt_enhancement/character.md](references/prompt_enhancement/character.md) | User asks for portrait, person, character, figure photo |
| `reference_to_image` | [prompt_enhancement/reference_to_image.md](references/prompt_enhancement/reference_to_image.md) | User provides a **reference image** and wants a new image in a similar **semantic/stylistic direction** (not structural fidelity) |
| `image_to_image` | [prompt_enhancement/image_to_image.md](references/prompt_enhancement/image_to_image.md) | User provides an **input image** and wants to **edit** it (change style, clothing, background, etc.) |
| `text_to_speech` | [prompt_enhancement/text_to_speech.md](references/prompt_enhancement/text_to_speech.md) | User provides a **short voice description** (e.g. "御姐音早晨问候") and needs it expanded into a full instruct for Qwen3-TTS |

Example flow (`text_to_image` / `character`):
```
User: "生成一个穿黑色皮衣的女孩"
  → Type: character
  → Read references/prompt_enhancement/character.md
  → Enhance: "Photorealistic, ultra-detailed portrait of a young woman..."
  → Call: uv run --no-sync python -m comfyui generate "Photorealistic, ultra-detailed portrait of a young woman..."
```

Example flow (`reference_to_image`):
```
User: [image] + "生成一个类似的图"
  → Preconditions: can view image; else VISION_UNAVAILABLE or NO_REFERENCE_IMAGE
  → Type: reference_to_image
  → Read references/prompt_enhancement/reference_to_image.md
  → Enhance from vision + user text: "Photorealistic, ultra-detailed ..." (one paragraph)
  → Call: uv run --no-sync python -m comfyui generate "Photorealistic, ultra-detailed ..."
```

Example flow (`image_to_image`):
```
User: [image] + "换成职业装"
  → Type: image_to_image
  → Read references/prompt_enhancement/image_to_image.md
  → Enhance: Agent analyzes image + user intent → "Change only the clothing to a tailored charcoal..."
  → Call: uv run --no-sync python -m comfyui generate --workflow klein_edit --image input_image=photo.png --prompt "Change only the clothing..."
```

Example flow (`text_to_music` — **not** TTS):

```
User: "生成一段史诗管弦配乐，悲壮感"
  → workflow: ace_step_15_music
  → Expand tags-style description if needed (English or rich Chinese descriptors per user preference)
  → Call: uv run --no-sync python -m comfyui generate --workflow ace_step_15_music -p "Epic orchestral, solemn brass, slow build..."
```

Example flow (`text_to_speech`):
```
User: "生成一段御姐音的早晨问候语音"
  → Type: text_to_speech
  → Read references/prompt_enhancement/text_to_speech.md（先「性别意图判定」：御姐 → 女声向，再按女声锚定扩写 instruct，避免低沉单独触发男声模型偏好）
  → Enhance instruct / speech_text 按文档拆分扩写
  → Call: uv run --no-sync python -m comfyui generate --workflow qwen3_tts --speech-text "……" --instruct "……"
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

When `python -m comfyui generate` returns `"success": true`, the Agent **应向用户展示产出**（图片优先直接展示；**音频 MP3、视频 MP4** 给出路径或按运行环境播放 / 附链接）：

1. **若能展示对应媒体**（例如 Read 支持图片）：读取 `outputs[].path` 并展示。
2. **若无法内联展示**：告知用户本地路径以便自行打开。

Do **not** just silently parse the JSON and move on — the user expects to see or know about the result.

Success:
```json
{
  "success": true,
  "workflow_id": "z_image_turbo",
  "status": "completed",
  "outputs": [{"path": "results/20260429/143052_a806c637-xxxx/xxx.png", "filename": "xxx.png", "size_bytes": 123456}],
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

Error codes: `DEPENDENCY_UNAVAILABLE`, `EMPTY_PROMPT`, `CONFIG_ERROR`, `MAPPING_NOT_FOUND`, `WORKFLOW_NOT_REGISTERED`, `WORKFLOW_FILE_NOT_FOUND`, `WORKFLOW_LOAD_FAILED`, `EXECUTION_FAILED`, `NO_OUTPUT`, `SAVE_FAILED`, `SERVER_UNAVAILABLE`, `NO_INPUT_IMAGE`, `INPUT_IMAGE_NOT_FOUND`, `IMAGE_UPLOAD_FAILED`, `INVALID_PARAM`, `INVALID_PARAM_TYPE`, `MULTIPLE_PROMPTS_NOT_SUPPORTED`, `PREFLIGHT_SERVER_UNREACHABLE`, `PREFLIGHT_MISSING_NODES`, `PREFLIGHT_MISSING_MODELS`, `PREFLIGHT_FAILED` (`DEPENDENCY_UNAVAILABLE` = runtime Python deps missing after package install, run `uv sync`; only emitted when the `comfyui` package itself is loadable but transitive deps like `requests` are not. If the package itself is not installed, Python produces a non-JSON traceback — treat non-JSON stdout/stderr as an environment setup issue. 后四者为运行前资源预检，见 [scripts/comfyui/preflight.py](scripts/comfyui/preflight.py) 与 `--preflight`)。

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
   uv run --no-sync python scripts/analyze_workflow.py assets/workflows/new_workflow.json
   ```
   This creates `assets/workflows/new_workflow.config.template.json` with discovered nodes and mapped params.
   Review the template, then rename to `new_workflow.config.json` when ready. Use `--force` to overwrite an existing `.config.json` directly.
3. Review and edit the generated config:
   - Fill in `capability` and `description`
   - Verify `node_mapping` entries (the analyzer uses heuristics — confirm correctness)
   - Remove `_discovered_nodes` (review-only section)
4. After the config is manually reviewed and kept (renamed to `.config.json`), the workflow becomes available via `--workflow new_workflow`

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

Workflow-level fields (siblings of `node_mapping`): `capability`, `description`, `size_strategy` (`workflow_managed` = executor/CLI skip applying mapped width/height), `output_kind` (`image` | `audio` | `video` — video outputs are often exposed under Comfy history **`gifs`**; the executor resolves `images` / `gifs` / `videos`), **`resolution_presets`** (optional dict of named `{width,height,label}` — loaded into **`WorkflowConfig`**, Agent-facing), **`default_resolution`** (optional preset key string).

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
