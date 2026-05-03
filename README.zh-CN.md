# ComfyUI Agent Skill

这是一个 Agent Skill 仓库（Claude Code / Claude.ai / Agent Skills）。对外使用仅要求存在 [SKILL.md](SKILL.md)。

- English README: [README.md](README.md)

## 状态

- 稳定接口：仅支持已注册工作流 + CLI 结构化 JSON 输出。
- PyPI 包名：`comfyui-agent-skill-mie`（同时提供短别名 `comfyui-skill`）。

## 安装

本包是已注册 ComfyUI 工作流的本地/自托管客户端。

- **需要本地或可信的自托管 ComfyUI 服务器**
- **不是**托管式生成服务
- **不会**帮你安装 ComfyUI 本体

### 推荐：使用 pipx 安装

```bash
pipx install comfyui-agent-skill-mie
```

### 备选：使用 uv tool 安装

```bash
uv tool install comfyui-agent-skill-mie
```

### 开发 / 维护模式（源码克隆）

```bash
git clone https://github.com/MieMieeeee/comfyui-agent-skill.git
cd comfyui-agent-skill
uv sync
uv run --no-sync python -m comfyui check
```

## 命令

### 推荐命令

安装后使用主命令：

```bash
comfyui-agent-skill-mie check
comfyui-agent-skill-mie generate -p "a cute cat sitting on a windowsill at golden hour"
```

### 短别名

也可使用更短的兼容别名：

```bash
comfyui-skill check
comfyui-skill generate -p "a cute cat sitting on a windowsill at golden hour"
```

## 升级

### pipx

```bash
pipx upgrade comfyui-agent-skill-mie
```

### uv tool

```bash
uv tool upgrade comfyui-agent-skill-mie
```

## 默认服务器地址与网络说明

默认本地地址：

```text
http://127.0.0.1:8188
```

当 CLI/Agent 与 ComfyUI 运行在**同一环境**时，这是最可靠的默认值。

如果 Agent 运行在 **WSL、容器或沙箱**中，而 ComfyUI 运行在**宿主机**，`127.0.0.1` 可能指向运行时自身而非宿主机。此时请尝试：

```bash
comfyui-agent-skill-mie check --server http://localhost:8188
comfyui-agent-skill-mie check --server http://<宿主机IP>:8188
```

如需持久化非默认服务器地址：

```bash
comfyui-agent-skill-mie save-server http://localhost:8188
```

在 tool-install 模式下，工作流与参考文档来自已安装的包内资源，可写数据会落到每用户目录：

- Windows：`%APPDATA%\comfyui-skill`
- macOS：`~/Library/Application Support/comfyui-skill`
- Linux：`$XDG_DATA_HOME/comfyui-skill` 或 `~/.local/share/comfyui-skill`

## 已注册工作流

稳定（配置均在 `assets/workflows/*.config.json` 中评审过）：

- `z_image_turbo`（文生图）
- `klein_edit`（图像编辑）
- `qwen3_tts`（文本转语音）
- `ltx-23-t2v`（文生视频）
- `ltx-23-i2v`（图生视频）
- `ace_step_15_music`（音乐/音频）
- `qwen_image_2512_4step`（文生图，适合海报、含文字的图片）

说明：运行时 registry 来自 `assets/workflows/*.config.json`（以及对应的 `assets/workflows/*.json`）。如果列表与文档不一致，以 configs 与 `comfyui-agent-skill-mie generate --help` 输出为准。

## 示例

### 文生图（`z_image_turbo`）

提示词：
```
年轻女生撑着透明伞，坐在草地上，肖像构图，柔和自然光，细节清晰，写实摄影风格
```

![z_image_turbo 输出](assets/examples/z_image_turbo.png)

### 参考生图（`z_image_turbo`）

参考图片：

![参考输入](assets/input/person.png)

用户输入：
```
生成同款服装的人在咖啡厅吃小蛋糕的图
```

增强后的提示词（Agent 视觉分析参考图后生成）：
```
Photorealistic, ultra-detailed portrait of a young woman with a short messy dark brown bob, wearing a chunky oatmeal-colored ribbed-knit scarf and an oversized cardigan with bold horizontal stripes in navy blue, mustard yellow, and teal green. She is sitting at a cozy cafe table, eating a small cake with a fork, warm cafe interior with soft ambient lighting, relaxed and happy expression, shallow depth of field, 85mm f/2.0, cozy atmosphere
```

![参考生图输出](assets/examples/reference_to_image.png)

### 文字海报（`qwen_image_2512_4step`）

提示词：
```
A watercolor style poster. Centered large Chinese characters: 五一节快乐. Clean composition, soft colors, textured paper, high quality.
```

![qwen_image_2512_4step 输出](assets/examples/qwen_image_2512_4step.png)

### 图像编辑（`klein_edit`）

输入：

![klein_edit 输入](assets/input/person.png)

提示词：
```
只把人物的衣服换成连衣裙，保持脸部、发型、姿势、背景、光照与构图不变，真实自然
```

![klein_edit 输出](assets/examples/klein_edit.png)

### 文生视频（`ltx-23-t2v`）

提示词：
```
一只猫懒洋洋地打哈欠，轻微镜头推近，柔和光线，真实自然运动，稳定画面
```

[ltx-23-t2v 输出（MP4）](assets/examples/ltx-23-t2v.mp4)

### 图生视频（`ltx-23-i2v`）

输入：

![ltx-23-i2v 输入](assets/input/person.png)

提示词：
```
A cinematic close-up portrait of a young woman with a tousled chin-length bob, wearing a chunky-knit taupe scarf and an oversized striped cardigan. She gazes upward with a melancholic, contemplative expression, soft diffused twilight light illuminating her face from the upper left. Gentle breeze moves her hair. The camera slowly drifts laterally with subtle breathing motion. Shallow depth of field, atmospheric film grain, quiet and emotional mood.
```

[ltx-23-i2v 输出（MP4）](assets/examples/ltx-23-i2v.mp4)

### 音乐生成（`ace_step_15_music`）

用户输入：
```
生成一段轻柔的钢琴氛围音乐
```

增强后的提示词（发送给工作流）：
```
gentle piano ambient, soft warm pads, slow tempo, night writing mood, calm, quiet, slightly healing, minimal, smooth reverb
```

[ace_step_15_music 输出（MP3）](assets/examples/ace_step_15_music.mp3)

### 语音合成（`qwen3_tts`）

用户输入：
```
生成御姐语音："谢谢你一直陪伴我到现在。"
```

CLI 调用：
```bash
comfyui-skill generate --workflow qwen3_tts --speech-text "谢谢你一直陪伴我到现在。" --instruct "模拟御姐角色：成熟自信、略带温柔，吐字清晰，语速适中，情绪真诚克制。"
```

[qwen3_tts 输出（MP3）](assets/examples/qwen3_tts.mp3)

## 参考文档

- [SKILL.md](SKILL.md) — Agent 使用主入口
- [references/workflows.md](references/workflows.md) — 工作流选择、尺寸说明与示例
- [references/cli.md](references/cli.md) — CLI 完整契约、异步任务、输出路径、JSON schema、错误码
- [references/prompt_enhancement/](references/prompt_enhancement/) — 提示词增强参考
- [references/workflow_nodes.md](references/workflow_nodes.md) — 模型与节点依赖说明

## 故障排查

- 建议先跑环境自检（服务可达性 + 所有已注册工作流的 preflight）：
  - `comfyui-skill doctor`（推荐）
  - `comfyui-agent-skill-mie doctor`
  - `uv run --no-sync python -m comfyui doctor`（源码模式）
- 如果 agent/skill 运行在 WSL/容器/沙箱里，而 ComfyUI 运行在宿主机，那么 `127.0.0.1` 可能指向运行时自身而非宿主机。请尝试 `--server http://localhost:8188` 或宿主机 IP（必要时用 `save-server` 持久化）。
- `SERVER_UNAVAILABLE`：无法访问目标 ComfyUI。请启动 ComfyUI，或用 `--server http://<ip>:8188` 指定正确地址。
- `PREFLIGHT_MISSING_NODES`：缺少自定义节点；请在 ComfyUI 端安装/启用对应插件。
- `PREFLIGHT_MISSING_MODELS`：缺少模型文件；请在 ComfyUI 端下载对应模型。
- `NO_OUTPUT`：工作流执行但未能获取产物；检查工作流输出节点以及 ComfyUI 日志/UI。
- 对于 `PREFLIGHT_MISSING_NODES` / `PREFLIGHT_MISSING_MODELS` / `NO_OUTPUT`，可参考依赖说明：[references/workflow_nodes.md](references/workflow_nodes.md)。

## 给维护者（新增 / 评审工作流）

维护文档刻意不放进 `SKILL.md`，以保持对使用者的指引简洁。

- 维护者入口：[MAINTAINER.md](MAINTAINER.md)
- 工作流注册与评审指南：[references/extension.md](references/extension.md)
