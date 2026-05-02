# 更新日志

## 0.1.1 - 2026-05-02

### 可靠性
- CLI 的 stdout JSON 改为 ASCII-safe，以提升在混合终端/编码环境（尤其 Windows CI）中的解析稳定性。
- 异步 poll 输出契约收敛，并记录瞬态轮询错误以提升可观测性。

### 打包
- 为 pipx/uv tool install 做准备：工作流/参考文档打包进包内资源，用户可写数据落到用户目录。
- PyPI 包名为 `comfyui-agent-skill-mie`（同时保留短命令别名 `comfyui-skill`）。
- 将 skill 元数据名称与已发布包名统一为 `comfyui-agent-skill-mie`。
- 将 `pipx` 调整为文档中的首选安装方式，并补充主命令/短别名关系与“本地/自托管、非 hosted service”的说明。

## 0.1.0 - 2026-05-01

### 新功能
- 面向 Agent 的 ComfyUI Skill：通过本仓库 CLI 运行已注册的工作流
- 支持：文生图、图像编辑、文生视频、图生视频、音乐/音频生成、文本转语音
- 统一结构化 JSON 输出（产物路径、元数据、标准化错误码）
- 支持 preflight 检查缺失节点/模型；长任务可输出进度事件

### 文档
- 区分使用者与维护者入口（README.md / MAINTAINER.md）
- 补充工作流选择与提示词增强参考文档

## 未发布
