# ComfyUI Skill 计划（拆分 + 路线图）

## 目标

将当前较长的 `SKILL.md` 拆分为「短核心指令 + 按需加载 references」结构，让 Claude Code / OpenCode / 其他 Agent 更容易触发、执行和维护 ComfyUI 技能，同时保留现有 CLI 合约、fail-fast 规则和工作流细节。

## 原则

- `SKILL.md` 保留 Agent 首次执行必须知道的内容：触发条件、硬规则、核心命令、输出处理、引用入口。
- 复杂细节移入 `references/`，并由 `SKILL.md` 明确指向，避免一次加载过多 token。
- 拆分后不改变 CLI 行为、不改变 workflow config、不改变测试预期。
- 所有文档仍以「Agent 可执行 SOP」为主，而不是面向人类的散文说明。

## 阶段

| 阶段 | 状态 | 内容 | 验收标准 |
|------|------|------|----------|
| 1 | complete | 创建计划文件 | `task_plan.md`、`findings.md`、`progress.md` 已存在并记录目标 |
| 2 | complete | 拆分工作流说明 | 新增 `references/workflows.md`，覆盖能力矩阵、工作流选择、尺寸规则和示例 |
| 3 | complete | 拆分 CLI 合约 | 新增 `references/cli.md`，覆盖命令、选项、输出路径、JSON schema、错误码 |
| 4 | complete | 拆分扩展维护说明 | 新增 `references/extension.md`，覆盖新增 workflow、analyzer、`node_mapping` schema 和 review checklist |
| 5 | complete | 精简 `SKILL.md` | `SKILL.md` 保留核心执行路径并链接拆分后的 references |
| 6 | complete | 验证 | Markdown 链接/关键命令引用合理，测试通过或记录无法运行原因 |
| 7 | in_progress | 对标优化（v0.2.0 计划） | 完成下述 7.1 / 7.2 / 7.3 的验收标准，并发布新版本 |

## 待验证命令

```powershell
$env:PYTHONPATH="E:\CC\comfyui\scripts"; python -m pytest -q scripts/tests
```

## v0.2.0 计划（对标 OpenClaw 可借鉴点）

范围选择：做 1/3/4，忽略 2（multi-server routing 暂不做）。

### 7.1 工作流导入体验（Import Workflow UX）

目标：把“复制 workflow JSON → 运行 analyzer → 生成模板 → 人工 review 激活”做成一个可复用的一条龙入口。

设计原则：
- 默认不激活：只生成 `*.config.template.json`，避免把未 review 的 mapping 自动投入使用。
- 以 `assets/workflows/` 为唯一落盘位置：导入后确保 workflow JSON 与模板都在该目录内。
- 失败可诊断：清晰报错（路径不存在/JSON 解析失败/命名不合法/目标文件已存在等）。

建议交付（CLI 层）：
- 新增一个显式子命令（名称待定，二选一）：
  - `python -m comfyui import-workflow <path> [--id <workflow_id>] [--force]`
  - 或 `python -m comfyui workflow import <path> ...`
- 行为：
  1. 复制/写入 workflow JSON 到 `assets/workflows/<workflow_id>.json`
  2. 调用现有 analyzer 生成 `assets/workflows/<workflow_id>.config.template.json`
  3. 输出“下一步操作”指引（review → 改名为 `.config.json` → `--preflight`）

验收标准：
- 导入命令能在干净仓库中完成上述 1–3 步。
- 不会创建/覆盖 `.config.json`（除非显式 `--force` / `--activate`）。
- 为该命令补齐单测覆盖（至少：成功路径、重复文件、无效 JSON、非法 id）。

### 7.2 安装/入口命令（Better Entrypoint）

目标：除了 `uv run --no-sync python -m comfyui ...`，给人类用户一个更短、更容易记的入口命令，同时不影响 Agent 推荐路径。

建议交付：
- 在 `pyproject.toml` 增加 console script（例如 `comfyui-skill` 或 `comfyui-agent-skill`）指向现有 CLI 入口。
- README 增加 “pipx 安装与升级” 的指引（可选），同时保留 `uv run` 作为 Agent 推荐方式。

验收标准：
- `pip install -e .` 后可以直接运行新命令完成 `check/generate`。
- 不更改现有 `python -m comfyui ...` 的兼容性。
- 更新 docs，并补齐最小 smoke test（可用 pytest 或一个轻量集成测试）。

### 7.3 文档与上手（Docs: Quickstart + Troubleshooting）

目标：像 OpenClaw 那样把“5 分钟跑通 + 常见错误怎么解”写清楚，但保持 `SKILL.md` 简洁。

建议交付：
- `README.md`：
  - Quick Start（安装 → health check → 第一次 generate）
  - Troubleshooting（按错误码分类：SERVER_UNAVAILABLE / PREFLIGHT_* / NO_OUTPUT / INPUT_IMAGE_NOT_FOUND）
  - 清晰区分：Skill Users vs Maintainers（已做，补充内容即可）
- `references/`：
  - 将“依赖/节点/模型排障参考”的定位写清楚（仅在需要时阅读）

验收标准：
- README 的 Quick Start 能在一台已启动 ComfyUI 的机器上跑通。
- Troubleshooting 能覆盖最常见的 5 类失败并给出下一步。

## 完成定义

- `SKILL.md` 明显短于当前版本，且能作为 Agent 的快速操作手册。
- 所有被移出的重要信息都能在 `references/workflows.md`、`references/cli.md`、`references/extension.md` 找到。
- 测试通过，或若失败则记录具体失败与下一步。

## 验证结果

- Markdown 链接检查通过。
- 关键错误示例检查通过：没有文档让 Agent 调用 `generate --check` 或 `generate --save-server`。
- 测试通过（以当前 `pytest` 输出或 CI 为准）。
