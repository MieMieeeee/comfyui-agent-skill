# ComfyUI Skill 拆分进度

## 2026-05-01

- 创建拆分任务的持久化计划文件。
- 已确认工作区在开始拆分前为干净状态。
- 已读取 `skill-creator` 与 `planning-with-files-zh` 的关键规则。
- 新增 `references/workflows.md`，承接工作流选择、能力边界、尺寸规则和常用命令。
- 新增 `references/cli.md`，承接 CLI 参数、输出路径、async submit/poll、JSON schema 和错误码。
- 新增 `references/extension.md`，承接新增 workflow、analyzer 安全规则、config schema 和 review checklist。
- 已将 `SKILL.md` 精简为核心 Agent SOP，并链接到三份新 reference。
- 静态验证通过：`SKILL.md` 约 220 行，新增 Markdown 链接均可解析。
- 测试通过：`205 passed in 80.09s`。
- 发布准备：新增 README/MAINTAINER 分流，主分支切换为 `main`，并发布 `v0.1.0`。
- 路线图规划：决定对标 OpenClaw 的 1/3/4（导入体验、入口命令、文档），暂不做 multi-server。

## 错误记录

| 时间 | 错误 | 处理 |
|------|------|------|
| 2026-05-01 | 暂无 | 暂无 |
