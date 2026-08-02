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
| Generate an image from text | `z_image_turbo` | `text_to_image` | Default T2I workflow (photoreal/general); supports `--width` and `--height` together. |
| Generate a poster or image with embedded text | `qwen_image_2512_4step` | `text_to_image` | Excels at text-in-image (Chinese/English characters, posters). Supports `--width` and `--height`; default `512x768`; good HD preset is `704x1280`. |
| Anime / manga / illustration image | `anima_turbo` | `text_to_image` | Clean lines, saturated color, stylized cartoon/anime look. Supports `--width`/`--height`; default `1024x1024`. |
| Artistic / painterly / concept-art image | `krea2_turbo` | `text_to_image` | Fast, stable; leans artistic/painterly realism over plain photoreal. Supports `--width`/`--height`; default `1024x1024`. |
| Create a similar image from a reference picture | `z_image_turbo` after Agent vision | `reference_to_image` | Reference image is not uploaded to ComfyUI; Agent turns image + user intent into one English prompt. |
| Edit a provided image | `klein_edit` | `image_to_image` | Upload image with `--image input_image=path`; do not pass `--width`/`--height`. |
| Mask / cut out an object by describing it | `sam3_mat_image` | `image_to_image` | Text-driven segmentation: `--image` + `-p "object to mask"` (e.g. "the cat"). No manual box-clicking. |
| Face / expression transfer (photo + driving video) | `liveportrait` | `image_to_video` | `--image` (reference face) + `--video` (driving video); no text prompt. Output is MP4. |
| Text prompt to MP4 video | `ltx_23_t2v_distill` | `text_to_video` | Supports paired `--width`/`--height`; default `768x512`; output is MP4. |
| Image + prompt to MP4 video | `ltx_23_i2v_distilled` | `image_to_video` | Requires one valid raster input image; output resolution follows uploaded image; do not pass CLI width/height. |
| Music / instrumental / song-style MP3 | `ace_step_15_music` | `text_to_music` | Use `--prompt` / `-p` as tags; do not use TTS flags. |
| Spoken voice synthesis | `qwen3_tts` | `text_to_speech` | Use `--speech-text` and `--instruct`; do not pass positional prompt. |
| Voice cloning (from a reference sample) | `qwen3_tts_clone` | `text_to_speech` | `-p` (new text) + `--text-input "ref_text=..."` (text spoken in the reference) + `--audio` (reference voice). Similarity drops if ref_text mismatches the sample. |

## Workflow Selection Guidance

The Agent should be the primary decision-maker for workflow choice. Built-in defaults are fallback options and can be overridden by a stronger semantic match among registered workflows.

### `z_image_turbo`
- **Best for**: general-purpose text-to-image requests
- **Prefer when**: the user wants a normal image from text and has no strong poster/text/layout requirement
- **Avoid when**: the user wants posters, banners, embedded text, or marketing layout
- **Agent note**: this is the default fallback T2I workflow

### `qwen_image_2512_4step`
- **Best for**: posters, banners, title-heavy images, text-in-image tasks
- **Prefer when**: the user asks for 海报 / 宣传图 / banner / 标题 / 带字图片
- **Avoid when**: the user only wants a standard photo-like image with no text composition requirement
- **Agent note**: prefer this over the default T2I workflow when text rendering or poster-style layout is important

### `anima_turbo`
- **Best for**: anime / manga / illustration style images
- **Prefer when**: the user asks for 动漫 / 插画 / 二次元 / anime / manga / cartoon style — clean lines and saturated color
- **Avoid when**: the user wants photoreal (use `z_image_turbo`) or embedded text (use `qwen_image_2512_4step`)
- **Agent note**: maps prompt/negative_prompt to CLIP Text Encode; default square `1024x1024`. Anime quality boosters (masterpiece, best quality, score_7_up) work well.

### `krea2_turbo`
- **Best for**: artistic / painterly realism, concept art, product visualization
- **Prefer when**: the user asks for 写实 / 艺术 / 概念设计 / 产品图 that leans artistic rather than plain photoreal or anime
- **Avoid when**: the user wants pure anime (use `anima_turbo`) or photoreal portraits (use `z_image_turbo`)
- **Agent note**: the prompt maps to a dedicated user-prompt node (not CLIP Encode); the workflow's own optional enhance chain is left untouched. No negative prompt role.

### `klein_edit`
- **Best for**: editing a provided input image while preserving pose/structure
- **Prefer when**: the user provides an image and asks to change details (clothing/background/style, retouch, inpaint)
- **Avoid when**: the user only provides text and wants a new image from scratch
- **Agent note**: requires `--image input_image=...` and does not support CLI width/height

### `sam3_mat_image`
- **Best for**: text-driven image segmentation / matting (mask an object by describing it)
- **Prefer when**: the user asks to 抠图/cut out/isolate/mask an object, or remove a background, by naming the target ("the red car", "a person")
- **Avoid when**: the user wants to edit content (use `klein_edit`) or video matting
- **Agent note**: `-p` is the object description to segment (not a creative prompt). Requires `--image`.

### `liveportrait`
- **Best for**: face / expression / pose transfer from a driving video onto a reference face photo
- **Prefer when**: the user provides a face photo + a driving video and wants the photo to mimic the video's expression/pose (lip-sync, talking head, vtuber-style)
- **Avoid when**: the user wants full-body motion transfer or text-to-video
- **Agent note**: requires `--image` (face) + `--video` (driving video); no text prompt. Output is MP4.

### `ltx_23_t2v_distill`
- **Best for**: text-to-video generation
- **Prefer when**: the user wants an MP4 from a shot prompt (camera/motion)
- **Avoid when**: the user provides an input image (use I2V)
- **Agent note**: width/height are supported when provided together

### `ltx_23_i2v_distilled`
- **Best for**: image-to-video generation from a provided image
- **Prefer when**: the user provides an input image and wants motion/camera prompt applied
- **Avoid when**: the user only provides text (use T2V)
- **Agent note**: output resolution follows input image; do not pass width/height

### `ace_step_15_music`
- **Best for**: music/audio generation (MP3)
- **Prefer when**: the user asks for music, instrumental tracks, songs, or background scoring
- **Avoid when**: the user wants spoken narration (use TTS)
- **Agent note**: treat the prompt as tags; do not use TTS flags or width/height

### `qwen3_tts`
- **Best for**: text-to-speech voice synthesis (MP3)
- **Prefer when**: the user wants spoken audio with a voice/style instruction
- **Avoid when**: the user wants music generation (use Ace Step) or to clone a specific voice (use `qwen3_tts_clone`)
- **Agent note**: require `--speech-text` and `--instruct`; no positional prompt

### `qwen3_tts_clone`
- **Best for**: cloning a specific voice from a short reference sample
- **Prefer when**: the user provides a reference voice clip and wants new text spoken in that voice
- **Avoid when**: the user wants generic TTS without a reference (use `qwen3_tts`)
- **Agent note**: `-p` is the new text to speak; `--text-input "ref_text=..."` is the text actually spoken in the reference audio; `--audio` is the reference clip. Similarity drops if `ref_text` mismatches the sample.

## Capability Boundaries

`text_to_image` writes a positive prompt, optional dimensions, and a random seed into a registered T2I workflow. Negative prompt behavior remains in workflow config. `z_image_turbo` is the default for general-purpose image generation. `qwen_image_2512_4step` excels at posters and images with embedded text (Chinese/English characters, typography).

`reference_to_image` is Agent vision plus T2I. The Agent must inspect the reference image, read `references/prompt_enhancement/reference_to_image.md`, create a single English prompt, then call a T2I workflow. It preserves semantic and stylistic direction only; it does not guarantee exact face, pose, camera angle, clothing, layout, or background fidelity.

`image_to_image` uploads the user's local image to ComfyUI and binds it to the configured image node. Use it when the user asks to edit, preserve structure, change clothing/background/style, or otherwise operate on the actual provided pixels.

`text_to_video` uses `ltx_23_t2v_distill`. Width and height, when provided, are mapped to the workflow's `EmptyImage` node and drive the LTX latent size through `GetImageSize`.

`image_to_video` uses `ltx_23_i2v_distilled`. The workflow reads uploaded image size with `GetImageSize`; export resolution follows that uploaded image. If the user wants a different output size, change the input image or workflow, not CLI width/height.

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

Do not pass `--width`/`--height` to `klein_edit`, `ltx_23_i2v_distilled`, `ace_step_15_music`, or `qwen3_tts`.

Registered defaults:

| Workflow | Default size behavior |
|----------|-----------------------|
| `z_image_turbo` | `832x1280` unless overridden with paired width/height |
| `qwen_image_2512_4step` | `512x768` unless overridden with paired width/height |
| `anima_turbo` | `1024x1024` unless overridden with paired width/height |
| `krea2_turbo` | `1024x1024` unless overridden with paired width/height |
| `ltx_23_t2v_distill` | `768x512` unless overridden with paired width/height |
| `klein_edit` | `workflow_managed`; no CLI dimensions |
| `ltx_23_i2v_distilled` | Upload image size; no CLI dimensions |
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

Anime / illustration (Anima):

```bash
uv run --no-sync python -m comfyui generate --workflow anima_turbo -p "masterpiece, best quality, 1girl, blue hair, green eyes, white dress, cherry blossoms, soft lighting"
```

Artistic / concept art (Krea-2):

```bash
uv run --no-sync python -m comfyui generate --workflow krea2_turbo -p "a sleek concept car in a neon-lit studio, cinematic lighting, reflective surfaces"
```

Image edit:

```bash
uv run --no-sync python -m comfyui generate --workflow klein_edit --image input_image=photo.png -p "Change only the jacket to a tailored charcoal business suit, preserve pose and face"
```

Text-driven matting (SAM3):

```bash
uv run --no-sync python -m comfyui generate --workflow sam3_mat_image --image photo.png -p "the cat"
```

Face/expression transfer (LivePortrait):

```bash
uv run --no-sync python -m comfyui generate --workflow liveportrait --image face.png --video driving.mp4
```

Text-to-video:

```bash
uv run --no-sync python -m comfyui generate --workflow ltx_23_t2v_distill --width 1280 --height 704 -p "Cinematic shot of waves at sunset, slow pan, natural motion"
```

Image-to-video:

```bash
uv run --no-sync python -m comfyui generate --workflow ltx_23_i2v_distilled --image input_image=photo.png -p "Subtle camera drift, soft daylight, preserve the subject"
```

Text-to-music:

```bash
uv run --no-sync python -m comfyui generate --workflow ace_step_15_music -p "Epic orchestral trailer, rising brass, thunderous percussion, minor key"
```

Text-to-speech:

```bash
uv run --no-sync python -m comfyui generate --workflow qwen3_tts --speech-text "你好，这是一段测试语音。" --instruct "温柔清晰的女声，语速适中。"
```

Voice cloning (Qwen3-TTS VoiceClone):

```bash
uv run --no-sync python -m comfyui generate --workflow qwen3_tts_clone -p "你好，这是用克隆音色念的新文本。" --text-input "ref_text=参考音频里实际念的原话" --audio sample.mp3
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

For `ltx_23_i2v_distilled`, output aspect ratio follows the uploaded image. To make square/landscape/portrait variants, provide different input images or adjust the workflow.

## Model and Node Requirements

Required model/node details live in [workflow_nodes.md](workflow_nodes.md). If generation returns `NO_OUTPUT`, or ComfyUI UI shows red nodes, check that reference first.
