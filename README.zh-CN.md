# ComfyUI Agent Skill

这是一个 Agent Skill 仓库（Claude Code / Claude.ai / Agent Skills）。对外使用仅要求存在 [SKILL.md](SKILL.md)。

- English README: [README.md](README.md)

## 状态

- 需要本地或可信的自托管 ComfyUI 服务（本仓库不是 hosted service）。
- 这不是托管式生成服务；本包不提供 ComfyUI 后端。
- 本包也不会帮你安装 ComfyUI 本体。
- 稳定接口：仅支持已注册工作流 + CLI 结构化 JSON 输出。
- 安全建议：不要把该 skill 指向不可信的公网 ComfyUI。
- PyPI 包名：`comfyui-agent-skill-mie`（同时提供短别名 `comfyui-skill`）。

## 已注册工作流

稳定（配置均在 `assets/workflows/*.config.json` 中评审过）：

- `z_image_turbo`（文生图）
- `klein_edit`（图像编辑）
- `qwen3_tts`（文本转语音）
- `ltx_23_t2v_distilled`（文生视频）
- `ltx_23_i2v_distilled`（图生视频）
- `ace_step_15_music`（音乐/音频）
- `qwen_image_2512_4step`（文生图）

说明：运行时 registry 来自 `assets/workflows/*.config.json`（以及对应的 `assets/workflows/*.json`）。如果列表与文档不一致，以 configs 与 `python -m comfyui generate --help` 输出为准。

## 给 Skill 使用者（生成 / 编辑 / 视频 / 音频）

当你希望通过本项目 CLI 运行“已注册的 ComfyUI 工作流”时使用：

- 主入口：[SKILL.md](SKILL.md)
- 工作流选择与尺寸说明：[references/workflows.md](references/workflows.md)
- CLI 完整契约（输出目录、submit/poll、JSON schema、错误码）：[references/cli.md](references/cli.md)
- 提示词增强参考：[references/prompt_enhancement/](references/prompt_enhancement/)

## 快速开始

### 安装（推荐：pipx）

```bash
pipx install comfyui-agent-skill-mie
comfyui-agent-skill-mie check
comfyui-agent-skill-mie generate -p "a cute cat sitting on a windowsill at golden hour"
comfyui-skill check
comfyui-skill generate -p "a cute cat sitting on a windowsill at golden hour"
```

### 备选：uv tool install

```bash
uv tool install comfyui-agent-skill-mie
comfyui-agent-skill-mie check
comfyui-agent-skill-mie generate -p "a cute cat sitting on a windowsill at golden hour"
comfyui-skill check
comfyui-skill generate -p "a cute cat sitting on a windowsill at golden hour"
```

### 源码模式（仅用于开发 / 维护）

```bash
uv sync
uv run --no-sync python -m comfyui check
uv run --no-sync python -m comfyui generate -p "a cute cat sitting on a windowsill at golden hour"
```

可选短命令（`uv sync` 安装项目后）：

```bash
uv run --no-sync comfyui-skill check
uv run --no-sync comfyui-skill generate -p "a cute cat sitting on a windowsill at golden hour"
```

从本地 wheel 安装（用于发布前自测）：

```bash
pipx install dist/comfyui_agent_skill_mie-*.whl
```

或从 GitHub 安装：

```bash
pipx install "git+https://github.com/MieMieeeee/comfyui-agent-skill.git"
```

在 tool-install 模式下：工作流与参考文档来自已安装的包内资源；可写数据会落到每用户目录：

- Windows：`%APPDATA%\\comfyui-skill`
- macOS：`~/Library/Application Support/comfyui-skill`
- Linux：`$XDG_DATA_HOME/comfyui-skill` 或 `~/.local/share/comfyui-skill`

短别名：`comfyui-skill`

## 升级

如果你使用 pipx 安装：

```bash
pipx upgrade comfyui-agent-skill-mie
```

如果你使用 uv tool 安装：

```bash
uv tool upgrade comfyui-agent-skill-mie
```

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
