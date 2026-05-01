# ComfyUI Skill 拆分发现

## 当前状态

- `SKILL.md` 已超过 500 行，包含触发条件、能力边界、工作流细节、CLI 选项、输出 schema、错误码和扩展维护说明。
- 这些内容都重要，但并非每次 Agent 触发技能时都需要全部加载。

## 拆分依据

- `skill-creator` 建议 `SKILL.md` 保持精简，复杂技能使用 progressive disclosure，将长内容移动到 `references/`。
- `SKILL.md` 的 frontmatter 应保持简单，核心字段为 `name` 和 `description`。
- 引用文档应由 `SKILL.md` 直接链接，避免让 Agent 多层跳转。

## 拆分边界

- `references/workflows.md`：工作流选择、能力矩阵、尺寸/输入映射、视频/音乐/TTS 差异。
- `references/cli.md`：命令、参数、server URL 优先级、输出路径、JSON schema、错误码、submit/poll 行为。
- `references/extension.md`：新增 workflow、analyzer 模板、config review、`node_mapping` schema。

## 风险

- 过度拆分会让 Agent 找不到关键命令，因此 `SKILL.md` 必须保留最常用命令示例。
- 错误码和 fail-fast 合约必须保持在 `SKILL.md` 有摘要，在 `references/cli.md` 有完整表。
- 工作流尺寸规则容易误用，`SKILL.md` 要保留简短决策表，细节放 `references/workflows.md`。

## 对标 OpenClaw：可借鉴点（后续路线）

结论：优先做 1/3/4，忽略 2。

1) 工作流导入体验（Import）
- 把“导入 workflow JSON → 生成 mapping 模板 → 人工 review 激活”变成单一入口，降低维护者操作成本。
- 默认只生成 `*.config.template.json`，不自动启用未 review 的 config，保持安全边界。

3) 安装与入口命令
- 除 `uv run --no-sync python -m comfyui ...` 外，提供一个更短的 console script，方便人类用户或其他 Agent 环境直接调用。

4) 文档上手与排障
- README 提供更清晰的 Quick Start 与 Troubleshooting（围绕错误码与 preflight 结果）。

2) Multi-server routing（暂不做）
- 复杂度高且会引入更大的配置面；当前 `--server` / `COMFYUI_URL` / `config.local.json` 已能覆盖多数场景。
