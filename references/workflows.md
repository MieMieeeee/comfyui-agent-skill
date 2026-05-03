# ComfyUI Workflow Reference

This file is the workflow-selection reference for Agents using the ComfyUI skill. Keep `SKILL.md` short; load this file when a task depends on workflow-specific inputs, size behavior, or capability boundaries.

## Table of Contents

- [Workflow Selection](#workflow-selection)
- [Capability Boundaries](#capability-boundaries)
- [Input and Size Mapping](#input-and-size-mapping)
- [Common Commands](#common-commands)
- [Aspect Ratio Guidance](#aspect-ratio-guidance)
- [Model and Node Requirements](#model-and-node-requirements)

## Workflow Selection

| User intent | `workflow_id` | Capability | Key rule |
|-------------|---------------|------------|----------|
| Generate an image from text | `z_image_turbo` | `text_to_image` | Default T2I workflow; supports `--width` and `--height` together. |
| Generate a poster or image with embedded text | `qwen_image_2512_4step` | `text_to_image` | Excels at text-in-image (Chinese/English characters, posters). Supports `--width` and `--height`; default `512x768`; good HD preset is `704x1280`. |
| Create a similar image from a reference picture | `z_image_turbo` after Agent vision | `reference_to_image` | Reference image is not uploaded to ComfyUI; Agent turns image + user intent into one English prompt. |
| Edit a provided image | `klein_edit` | `image_to_image` | Upload image with `--image input_image=path`; do not pass `--width`/`--height`. |
| Text prompt to MP4 video | `ltx-23-t2v` | `text_to_video` | Supports paired `--width`/`--height`; default `768x512`; output is MP4. |
| Image + prompt to MP4 video | `ltx-23-i2v` | `image_to_video` | Requires one valid raster input image; output resolution follows uploaded image; do not pass CLI width/height. |
| Music / instrumental / song-style MP3 | `ace_step_15_music` | `text_to_music` | Use `--prompt` / `-p` as tags; do not use TTS flags. |
| Spoken voice synthesis | `qwen3_tts` | `text_to_speech` | Use `--speech-text` and `--instruct`; do not pass positional prompt. |

## Capability Boundaries

`text_to_image` writes a positive prompt, optional dimensions, and a random seed into a registered T2I workflow. Negative prompt behavior remains in workflow config. `z_image_turbo` is the default for general-purpose image generation. `qwen_image_2512_4step` excels at posters and images with embedded text (Chinese/English characters, typography).

`reference_to_image` is Agent vision plus T2I. The Agent must inspect the reference image, read `references/prompt_enhancement/reference_to_image.md`, create a single English prompt, then call a T2I workflow. It preserves semantic and stylistic direction only; it does not guarantee exact face, pose, camera angle, clothing, layout, or background fidelity.

`image_to_image` uploads the user's local image to ComfyUI and binds it to the configured image node. Use it when the user asks to edit, preserve structure, change clothing/background/style, or otherwise operate on the actual provided pixels.

`text_to_video` uses `ltx-23-t2v`. Width and height, when provided, are mapped to the workflow's `EmptyImage` node and drive the LTX latent size through `GetImageSize`.

`image_to_video` uses `ltx-23-i2v`. The workflow reads uploaded image size with `GetImageSize`; export resolution follows that uploaded image. If the user wants a different output size, change the input image or workflow, not CLI width/height.

`text_to_music` uses Ace Step and outputs MP3. The prompt acts like music tags: genre, mood, instrumentation, tempo, vocal/instrumental hints, and structure. It is not text-to-speech.

`text_to_speech` uses Qwen3-TTS VoiceDesign and outputs MP3. It needs spoken content plus voice/style instruction. It is not music generation.

## Input and Size Mapping

| Capability | Agent/user input | ComfyUI/executor mapping |
|------------|------------------|--------------------------|
| `text_to_image` | User description, enhanced to one positive English prompt; optional explicit aspect/size | Positive prompt; optional `width`/`height`; random seed |
| `reference_to_image` | Reference image + short user intent | Agent vision produces prompt; reference image is not sent to ComfyUI |
| `image_to_image` | Local image path + edit instruction | Upload and bind `input_image`; positive prompt; random seed |
| `text_to_video` | Shot, camera, subject, motion, style | Positive/negative prompt; `EmptyImage` width/height; MP4 output |
| `image_to_video` | Valid image path + motion/camera prompt | Upload `input_image`; positive/negative prompt; output size follows input image |
| `text_to_music` | Music tags / arrangement description | Writes prompt into Ace Step tags; MP3 output |
| `text_to_speech` | Spoken script + voice instruction | Writes `speech_text` and `instruct`; MP3 output |

Width/height are valid only when all of these are true:

- The workflow config has both `width` and `height` in `node_mapping`.
- The workflow does not use `size_strategy: "workflow_managed"`.
- Both values are provided together.

Do not pass `--width`/`--height` to `klein_edit`, `ltx-23-i2v`, `ace_step_15_music`, or `qwen3_tts`.

Registered defaults:

| Workflow | Default size behavior |
|----------|-----------------------|
| `z_image_turbo` | `832x1280` unless overridden with paired width/height |
| `qwen_image_2512_4step` | `512x768` unless overridden with paired width/height |
| `ltx-23-t2v` | `768x512` unless overridden with paired width/height |
| `klein_edit` | `workflow_managed`; no CLI dimensions |
| `ltx-23-i2v` | Upload image size; no CLI dimensions |
| Audio workflows | No image dimensions |

`resolution_presets` and `default_resolution` in config are Agent-facing metadata. Runtime still follows `node_mapping` defaults plus CLI overrides.

## Common Commands

Default T2I:

```bash
uv run --no-sync python -m comfyui generate -p "Photorealistic portrait of a tabby cat by a rain-streaked window, golden hour"
```

Qwen Image 2512:

```bash
uv run --no-sync python -m comfyui generate --workflow qwen_image_2512_4step --width 704 --height 1280 -p "English prompt, detailed scene"
```

Image edit:

```bash
uv run --no-sync python -m comfyui generate --workflow klein_edit --image input_image=photo.png -p "Change only the jacket to a tailored charcoal business suit, preserve pose and face"
```

Text-to-video:

```bash
uv run --no-sync python -m comfyui generate --workflow ltx-23-t2v --width 1280 --height 704 -p "Cinematic shot of waves at sunset, slow pan, natural motion"
```

Image-to-video:

```bash
uv run --no-sync python -m comfyui generate --workflow ltx-23-i2v --image input_image=photo.png -p "Subtle camera drift, soft daylight, preserve the subject"
```

Text-to-music:

```bash
uv run --no-sync python -m comfyui generate --workflow ace_step_15_music -p "Epic orchestral trailer, rising brass, thunderous percussion, minor key"
```

Text-to-speech:

```bash
uv run --no-sync python -m comfyui generate --workflow qwen3_tts --speech-text "你好，这是一段测试语音。" --instruct "温柔清晰的女声，语速适中。"
```

## Aspect Ratio Guidance

If the user asks for multiple aspect ratios, run the workflow multiple times. One CLI invocation uses one width/height pair for all prompts in that invocation.

| Intent | Example |
|--------|---------|
| Square image | `--width 1024 --height 1024` |
| Landscape image | `--width 1280 --height 832` |
| Portrait image | `--width 832 --height 1280` |
| Landscape LTX video HD | `--width 1280 --height 704` |
| Landscape LTX video FHD | `--width 1920 --height 1088` |

For `ltx-23-i2v`, output aspect ratio follows the uploaded image. To make square/landscape/portrait variants, provide different input images or adjust the workflow.

## Model and Node Requirements

Required model/node details live in [workflow_nodes.md](workflow_nodes.md). If generation returns `NO_OUTPUT`, or ComfyUI UI shows red nodes, check that reference first.
