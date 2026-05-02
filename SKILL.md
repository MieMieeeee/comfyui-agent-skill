---
name: comfyui
description: >
  Unified ComfyUI workflow execution skill for Agents (Claude Code / OpenCode / Hermes).
  Use when the user asks to generate images, edit images, create reference-guided images,
  generate text-to-video or image-to-video clips, create music/audio, synthesize speech,
  or check a ComfyUI server. Supports registered workflows only and requires a running
  ComfyUI server (default http://127.0.0.1:8188).
---

# ComfyUI Skill

## Purpose

Run registered ComfyUI workflows through a stable Agent-facing CLI, with prompt enhancement, fail-fast errors, and structured JSON results.

## When to Use

Use this skill when the user asks to:

- Generate an image from text.
- Generate a new image inspired by a reference image.
- Edit an input image while preserving some structure or subject details.
- Generate text-to-video or image-to-video MP4 output.
- Generate music / instrumental / song-style MP3 output.
- Synthesize spoken voice audio with Qwen3-TTS.
- Check whether a ComfyUI server is available.

Do not use this skill when the user only wants prompt writing, brainstorming, or discussion without actual generation. Do not use it when the ComfyUI server is unavailable.

## Hard Rules

- Source mode: run CLI commands from the skill root (the directory containing `SKILL.md` and `scripts/`).
- Tool-install mode: `comfyui-agent-skill-mie` / `comfyui-skill` can be run from any directory.
- Use `uv run --no-sync python -m comfyui` for runtime calls. Do not use bare `python -m comfyui` in Agent instructions.
- Use registered workflows only. Do not run arbitrary unreviewed ComfyUI workflow JSON.
- If server health fails, stop generation and return/handle `SERVER_UNAVAILABLE`; do not search disk for ComfyUI installs or guess ports.
- Do not create or edit `config.local.json` unless the user explicitly wants a persistent server URL. For one-off runs, use `--server` or `COMFYUI_URL`.
- For `reference_to_image`, inspect the reference image with Agent vision and create a prompt. Do not upload that reference image to ComfyUI.
- For `image_to_image` and `image_to_video`, upload the provided local image with `--image`.
- Analyzer-generated workflow configs require human review before activation.

## Setup

Prerequisites:

- ComfyUI server with `GET /system_stats` available.
- Python 3.10+ and `uv`.
- Required ComfyUI models/custom nodes for the selected workflow.

Initial setup from the skill root:

```bash
uv sync
uv run --no-sync python -m comfyui --help
```

Tool-install mode:

```bash
comfyui-agent-skill-mie --help
comfyui-agent-skill-mie check
```

## Quick Workflow Choice

Minimal decision tree:

- User gives text only → `generate -p "..."` (defaults to `z_image_turbo`)
- User gives a reference image and wants a new similar image → vision → `reference_to_image` prompt → run `z_image_turbo`
- User gives an input image and wants edits → `generate --workflow klein_edit --image input_image=... -p "..."`
- User wants TTS / voice audio → `generate --workflow qwen3_tts --speech-text "..." --instruct "..."`
- User wants video → `ltx_23_t2v_distill` (text→video) or `ltx_23_i2v_distilled` (image→video)

| User intent | Workflow / mode | Required command shape |
|-------------|-----------------|------------------------|
| Text to image | `z_image_turbo` default | `generate -p "prompt"` |
| Qwen Image 2512 | `qwen_image_2512_4step` | `generate --workflow qwen_image_2512_4step -p "prompt"` |
| Similar image from reference | Agent vision + T2I | Read reference image, create English prompt, then T2I |
| Edit image | `klein_edit` | `generate --workflow klein_edit --image input_image=photo.png -p "edit prompt"` |
| Text to video | `ltx_23_t2v_distill` | `generate --workflow ltx_23_t2v_distill -p "shot prompt"` |
| Image to video | `ltx_23_i2v_distilled` | `generate --workflow ltx_23_i2v_distilled --image input_image=photo.png -p "motion prompt"` |
| Text to music | `ace_step_15_music` | `generate --workflow ace_step_15_music -p "music tags"` |
| Text to speech | `qwen3_tts` | `generate --workflow qwen3_tts --speech-text "..." --instruct "..."` |

For workflow-specific size rules, capability boundaries, and examples, read [references/workflows.md](references/workflows.md).

## Core Commands

Health check:

```bash
uv run --no-sync python -m comfyui check
```

Generate an image:

```bash
uv run --no-sync python -m comfyui generate -p "a cute cat sitting on a windowsill at golden hour"
```

Generate with a specific workflow and server:

```bash
uv run --no-sync python -m comfyui generate --workflow z_image_turbo --server http://192.168.1.100:8188 -p "a landscape"
```

Save a persistent server URL only when the user asks for it:

```bash
uv run --no-sync python -m comfyui save-server http://192.168.1.100:8188
```

Preflight a workflow before a long run:

```bash
uv run --no-sync python -m comfyui generate --workflow qwen_image_2512_4step --preflight
```

Show progress for long jobs:

```bash
uv run --no-sync python -m comfyui generate --workflow ltx_23_t2v_distill -p "cinematic waves at sunset, slow pan" --progress
```

Full CLI options, output path behavior, async submit/poll, and error code details are in [references/cli.md](references/cli.md).

## Prompt Enhancement

Before generation, convert the user's intent into the right workflow inputs.

| Type | Read this file | Use when |
|------|----------------|----------|
| `character` | [references/prompt_enhancement/character.md](references/prompt_enhancement/character.md) | Portrait, person, character, figure photo |
| `reference_to_image` | [references/prompt_enhancement/reference_to_image.md](references/prompt_enhancement/reference_to_image.md) | User provides a reference image and wants a new similar image |
| `image_to_image` | [references/prompt_enhancement/image_to_image.md](references/prompt_enhancement/image_to_image.md) | User provides an input image and wants to edit it |
| `text_to_speech` | [references/prompt_enhancement/text_to_speech.md](references/prompt_enhancement/text_to_speech.md) | User gives a short voice description and needs full Qwen3-TTS instruction |

Reference-to-image flow:

1. Ensure a usable reference image exists; otherwise return Agent error `NO_REFERENCE_IMAGE`.
2. Ensure this runtime can inspect images; otherwise return Agent error `VISION_UNAVAILABLE`.
3. Read the reference prompt enhancement file and create one English prompt.
4. Call T2I generation with that prompt. Do not pass the reference image to ComfyUI.

Image-to-image flow:

1. Ensure a local image path is available.
2. Read the image edit prompt enhancement file.
3. Call `klein_edit` with `--image input_image=path`.

Text-to-speech flow:

1. Split user intent into spoken content and voice/style instruction.
2. Read the TTS prompt enhancement file.
3. Call `qwen3_tts` with `--speech-text` and `--instruct`; do not use positional prompt.

## Fail-Fast and Recovery

CLI failures are structured JSON on stdout. Agent-only pre-check failures for reference images should also be JSON.

Agent-only error shape:

```json
{
  "source": "agent",
  "success": false,
  "error": {"code": "VISION_UNAVAILABLE", "message": "Cannot read reference image in this runtime."}
}
```

Required fail-fast behavior:

- Missing prompt: return/handle `EMPTY_PROMPT`.
- Unregistered workflow: return/handle `WORKFLOW_NOT_REGISTERED`.
- Server unavailable: return/handle `SERVER_UNAVAILABLE` and ask whether ComfyUI is running locally or on another machine.
- Missing reference image before `reference_to_image`: return Agent error `NO_REFERENCE_IMAGE`; do not call CLI.
- No vision for `reference_to_image`: return Agent error `VISION_UNAVAILABLE`; do not call CLI.
- Missing image for image workflows: return/handle `NO_INPUT_IMAGE` or `INPUT_IMAGE_NOT_FOUND`.
- Missing custom nodes/models during preflight: return/handle `PREFLIGHT_MISSING_NODES` or `PREFLIGHT_MISSING_MODELS`.

When the user provides a remote ComfyUI address, save it only if they want persistence:

```bash
uv run --no-sync python -m comfyui save-server http://<address>:<port>
```

Otherwise retry the original command with `--server http://<address>:<port>`.

## Output Handling

After successful generation, present the result to the user. Do not silently parse JSON and stop.

- For images, display the file when the runtime supports local image display; otherwise provide the absolute/local path from `outputs[].path`.
- For MP3/MP4, provide the path or use the runtime's media display/playback capability when available.
- Prefer omitting `--output`; the CLI writes to a per-job directory under `results/` and returns exact paths in JSON.
- For `--count > 1`, parse the wrapper object and present each result.

See [references/cli.md](references/cli.md) for JSON schemas and output directory rules.

## References

- [references/workflows.md](references/workflows.md) — workflow selection, capabilities, size rules, examples.
- [references/cli.md](references/cli.md) — CLI contract, async jobs, output paths, JSON schemas, error codes.
- `references/prompt_enhancement/` — prompt enhancement instructions.
