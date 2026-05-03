# 更新日志

## 0.1.5 - 2026-05-03

### 文档
- 重构 README：安装/命令/升级章节、网络说明、参考文档索引。
- 新增参考生图示例及生成输出。
- 更新文档测试以匹配重构后的 README。

## 0.1.4 - 2026-05-03

### 文档
- README 新增示例章节，展示所有已注册工作流的用户输入与输出。
- 图像编辑和图生视频示例直接展示输入图片。
- 音乐生成和语音合成示例从用户自然语言视角呈现。

## 0.1.2 - 2026-05-02

### 新功能
- 新增 `doctor` 环境自检命令：检查 ComfyUI 可用性，并对所有已注册工作流执行 preflight（缺节点/缺模型）。

### 文档
- 将 `pipx` 调整为首选安装方式，并明确主命令/短别名关系与“本地/自托管、非 hosted service”的说明。

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

## 0.1.3 - 2026-05-03

### 新功能
- 扩展工作流分析器与 preflight 的 loader 节点检测：UNETLoader、DualCLIPLoader、VAELoaderKJ、LoraLoaderModelOnly、LatentUpscaleModelLoader、LTXVAudioVAELoader、LTXAVTextEncoderLoader、CLIPVisionLoader。
- 缺失模型输出结构化 `ModelRef`（模型类型与 ComfyUI 目标子目录）。
- 通过 `/object_info` 的 `python_module` 字段检测第三方自定义插件。
- 分析器处理重复节点标题，使用 `#N` 后缀（如 `Load LoRA#2`）。
- 新增 `ltx-23-t2v` 和 `ltx-23-i2v` 工作流，替换旧版 distilled 变体。
- 新增 `scripts/sync_package_assets.py` 脚本，保持包内资源与仓库根目录同步。

### 修复
- 修复 `ltx-23-i2v` 配置将 prompt 映射到负面提示词节点而非正面提示词节点。
- 增强 `ltx-23-i2v` validate 用例提示词，模拟 agent 视觉分析后的提示词增强。

### 文档
- 明确 `qwen_image_2512_4step` 适合海报和含文字的图片。
- 全局替换 `ltx_23_*_distilled` 引用为 `ltx-23-t2v` / `ltx-23-i2v`。

## 未发布
