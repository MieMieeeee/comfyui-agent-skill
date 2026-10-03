# 更新日志

## 0.1.10 - 2026-08-02

### 新功能
- 支持视频/音频上传。新增 `--video` / `--audio` CLI 参数（与 `--image` 对称），以及 `--text-input "role=value"`，用于额外的字符串角色。分析器现在会检测 `VHS_LoadVideo` / `LoadAudio` 节点。图片路径行为不变；图片相关错误码保持不变。
- 新增三个工作流，均已用真实素材在运行中的 ComfyUI 上端到端验证：`liveportrait`（面部/表情迁移，视频上传）、`sam3_mat_image`（文字驱动抠图）、`qwen3_tts_clone`（声音克隆，音频上传）。

### 修复
- 允许纯上传工作流（没有文本提示词，例如 liveportrait）运行：放宽执行器的字符串输入门禁、CLI 的 `EMPTY_PROMPT` 门禁，以及空提示词循环。`is_tts_workflow` 现在要求存在 `speech_text` 角色，因此声音克隆工作流走标准提示词路径。

## 0.1.9 - 2026-08-02

### 修复
- Preflight 不再因非 ASCII 模型目录名崩溃（例如 `models/新建文件夹`）。`http_get_json` 现在会对路径段做百分号编码，并捕获 `UnicodeEncodeError`；此前该错误会逃逸成误导性的 `WORKFLOW_LOAD_FAILED`。
- 将 `validate_workflow_resources` 里的 `/object_info` 超时提高到 30 秒。节点较多的安装中，响应可达数 MB，会超过默认的 8 秒。

## 0.1.8 - 2026-08-02

### 新功能
- 新增 `anima_turbo`（动漫/漫画文生图）和 `krea2_turbo`（艺术/绘画风文生图）工作流，与 `z_image_turbo`（写实）和 `qwen_image_2512_4step`（海报/文字）一起扩展文生图的风格范围。选择逻辑会自动路由动漫/艺术类意图。
- 导入时暴露缺失的提示词节点。当分析器检测不到提示词（例如它位于非 CLIP 的字符串节点中）时，`import-workflow` 现在会通过 `--prompt-node`、交互式选择（列出候选及其当前值），或非交互式的候选提示来确定它，而不是静默交出一份会在运行时丢掉用户提示词的配置。
- 导入时检测有歧义的节点标题（`AMBIGUOUS_NODE_TITLE`）：两个 node_mapping 角色指向同一个重复标题时，会经由 `set_node_param` 交叉写入；现在会拦住并给出重命名提示。

## 0.1.7 - 2026-08-02

### 新功能
- 新增 `convert-ui` 子命令：通过 Playwright 驱动正在运行的 ComfyUI 前端，把 ComfyUI UI/Save 格式工作流（`{nodes, links}`）批量转换成 API 格式（延迟导入，按需启用）。对齐权威的 `loadGraphData` + `graphToPrompt` 路径；不会触发推理。
- 防止 `import-workflow` 接受非 API 输入。UI/Save 与未知格式现在会预先拒绝，并给出可操作的指引（`WORKFLOW_NOT_API_FORMAT`），而不是在分析器内部崩溃。
- 在生成的配置模板中暴露带 `SKILL` 前缀的节点标量输入（分析器启发式）。

## 0.1.6 - 2026-05-04

### 新功能
- 增加面向 agent 驱动的工作流路由选择 MVP。
- 增加 ClawHub bundle 构建器。

### 文档
- 增加 agent-first 的工作流选择指引。
- 增加端到端的工作流选择示例。
- 增加工作流扩展示例。
- 增加项目架构决策树流程图（SVG/PNG/HTML）。

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

### 新特性
- 增加 agent-first 的工作流选择策略说明与工作流选择指导卡片。
- 增加轻量的 CLI fallback selector：在高置信度“海报/带字”场景优先选择 `qwen_image_2512_4step`。

### 兼容性
- 统一 LTX 工作流 id 为 `ltx_23_t2v_distill` 与 `ltx_23_i2v_distilled`（文档与配置对齐）。
