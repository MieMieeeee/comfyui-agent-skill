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
- `ltx-23-t2v` (text-to-video)
- `ltx-23-i2v` (image-to-video)
- `ace_step_15_music` (music/audio)
- `qwen_image_2512_4step` (text-to-image, excels at posters and images with embedded text)

Source of truth: the runtime registry is derived from `assets/workflows/*.config.json` (and the corresponding `assets/workflows/*.json` workflow files). If this list drifts, trust the configs and `python -m comfyui generate --help` output.

## Examples

### Text to Image (`z_image_turbo`)

Prompt:
```
年轻女生撑着透明伞，坐在草地上，肖像构图，柔和自然光，细节清晰，写实摄影风格
```

![z_image_turbo output](assets/examples/z_image_turbo.png)

### Reference to Image (`z_image_turbo`)

Reference image:

![reference input](assets/input/person.png)

User input:
```
生成类似人物在跑步的图
```

Enhanced prompt (Agent vision analyzes the reference and generates):
```
Photorealistic, ultra-detailed portrait of a young woman with a short messy dark brown bob, wearing a chunky oatmeal-colored ribbed-knit scarf and an oversized cardigan with bold horizontal stripes in navy blue, mustard yellow, and teal green. She is running through a sunlit park path, dynamic motion, hair flowing with movement, soft golden hour light, shallow depth of field, 85mm f/2.0, natural and energetic expression
```

<!-- Output will be added after first validate run -->

### Text Poster (`qwen_image_2512_4step`)

Prompt:
```
A watercolor style poster. Centered large Chinese characters: 五一节快乐. Clean composition, soft colors, textured paper, high quality.
```

![qwen_image_2512_4step output](assets/examples/qwen_image_2512_4step.png)

### Image Edit (`klein_edit`)

Input:

![klein_edit input](assets/input/person.png)

Prompt:
```
只把人物的衣服换成连衣裙，保持脸部、发型、姿势、背景、光照与构图不变，真实自然
```

![klein_edit output](assets/examples/klein_edit.png)

### Text to Video (`ltx-23-t2v`)

Prompt:
```
一只猫懒洋洋地打哈欠，轻微镜头推近，柔和光线，真实自然运动，稳定画面
```

[ltx-23-t2v output (MP4)](assets/examples/ltx-23-t2v.mp4)

### Image to Video (`ltx-23-i2v`)

Input:

![ltx-23-i2v input](assets/input/person.png)

Prompt:
```
A cinematic close-up portrait of a young woman with a tousled chin-length bob, wearing a chunky-knit taupe scarf and an oversized striped cardigan. She gazes upward with a melancholic, contemplative expression, soft diffused twilight light illuminating her face from the upper left. Gentle breeze moves her hair. The camera slowly drifts laterally with subtle breathing motion. Shallow depth of field, atmospheric film grain, quiet and emotional mood.
```

[ltx-23-i2v output (MP4)](assets/examples/ltx-23-i2v.mp4)

### Text to Music (`ace_step_15_music`)

User input:
```
生成一段轻柔的钢琴氛围音乐
```

Enhanced prompt sent to workflow:
```
gentle piano ambient, soft warm pads, slow tempo, night writing mood, calm, quiet, slightly healing, minimal, smooth reverb
```

[ace_step_15_music output (MP3)](assets/examples/ace_step_15_music.mp3)

### Text to Speech (`qwen3_tts`)

User input:
```
生成御姐语音："谢谢你一直陪伴我到现在。"
```

CLI call:
```bash
comfyui-skill generate --workflow qwen3_tts --speech-text "谢谢你一直陪伴我到现在。" --instruct "模拟御姐角色：成熟自信、略带温柔，吐字清晰，语速适中，情绪真诚克制。"
```

[qwen3_tts output (MP3)](assets/examples/qwen3_tts.mp3)

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
