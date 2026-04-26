# ComfyUI Skill — 项目实现总结（供 Review）

> 更新日期: 2026-04-26 | 测试: 68 passed, 10 skipped

## 1. 项目定位

`comfyui` 是一个面向 Agent（Claude Code / OpenCode / Hermes）的 ComfyUI 工作流执行技能。Agent 无需理解底层工作流细节，通过统一 CLI `run.py` 调用已注册的 ComfyUI 工作流生成图片。

## 2. 已实现能力

### 2.1 核心工作流能力

| 能力 | 状态 | 说明 |
|------|------|------|
| `text_to_image` | ✅ 已实现 | 文本提示词 → 图片生成，默认使用 `z_image_turbo` 工作流 |
| `image_to_image` | 📋 计划中 | 上传输入图片到 ComfyUI，通过编辑指令进行图像编辑，默认使用 `klein_edit` 工作流。详见 `review/PLAN_IMAGE_TO_IMAGE.md` |

### 2.2 Agent 增强能力

| 能力 | 状态 | 说明 |
|------|------|------|
| `reference_to_image` | ✅ 已实现 | Agent 用视觉理解用户参考图，生成提示词后调用同一 `z_image_turbo` 流程。参考图**不发送到 ComfyUI**。仅保留语义/风格方向，**不是** ComfyUI img2img |

### 2.3 运维能力

- 服务器健康检查（`--check`）
- ComfyUI URL 持久化（`--save-server` → `config.local.json`）
- 工作流分析器（从工作流 JSON 自动生成 config 模板）

### 2.4 能力对比

| 维度 | `text_to_image` | `reference_to_image` | `image_to_image` |
|------|----------------|---------------------|-----------------|
| 输入 | 文本提示词 | 参考图（Agent 视觉） + 文本 | 输入图片（上传到 ComfyUI） + 文本 |
| ComfyUI 收到图片？ | 否 | 否 | **是** |
| 实现 | z_image_turbo 工作流 | 同 z_image_turbo | `klein_edit` 工作流 |
| 结构保真 | N/A | 弱 — 仅语义/风格方向 | 强 — 保持姿态/结构/构图 |
| 使用场景 | "生成一只猫" | "做一张类似风格的照片" | "编辑这张图"、"换衣服" |

## 3. 架构

### 3.1 目录结构

```
comfyui/
├── SKILL.md                          # Agent 面向的技能文档（入口）
├── config.local.json                 # 本地 ComfyUI URL 配置（gitignored）
├── assets/workflows/
│   ├── z_image_turbo.json            # 工作流 JSON
│   └── z_image_turbo.config.json     # 工作流配置（node_mapping）
├── scripts/
│   ├── run.py                        # CLI 入口
│   ├── analyze_workflow.py           # 工作流分析器 CLI
│   ├── comfyui/
│   │   ├── config.py                 # 服务器 URL 解析 + 持久化
│   │   ├── models/result.py          # GenerationResult 数据模型
│   │   ├── services/
│   │   │   ├── workflow_config.py    # WorkflowConfig + ConfigError + 注册表
│   │   │   └── executor.py           # 通用工作流执行器
│   │   └── tools/
│   │       └── analyze_workflow.py   # 工作流分析器逻辑
│   └── tests/                        # 测试（68 passed）
├── references/
│   ├── workflow_nodes.md             # 工作流节点参考
│   └── prompt_enhancement/
│       ├── character.md              # 人物/角色类提示词增强指引
│       └── reference_to_image.md     # 参考图提示词增强指引
└── review/
    ├── PLAN_IMAGE_TO_IMAGE.md        # img2img 实现计划
    └── IMPLEMENTATION_SUMMARY.md     # 本文件
```

### 3.2 核心数据流

```
用户 → Agent（读取 SKILL.md）
     → Agent 增强提示词（references/prompt_enhancement/）
     → CLI: python scripts/run.py "enhanced prompt"
     → run.py 解析参数，查找 WORKFLOW_REGISTRY
     → executor.py: 加载工作流 → 应用 node_mapping → 执行 → 保存图片
     → 返回结构化 JSON 结果
     → Agent 展示结果给用户
```

### 3.3 设计原则

1. **健康检查依赖 `/system_stats`**：`check_server()` 依赖目标 ComfyUI 环境提供 `GET /system_stats`。这是当前目标运行时的已知约定，不是所有 ComfyUI 环境的通用假设。如未来适配其他环境，再扩展兼容策略。
2. **输入图片只上传，不预处理**：Skill 只负责校验文件存在、上传到 ComfyUI、绑定到节点参数。不做 resize、crop、pad、尺寸推断。所有尺寸/比例/latent 处理由 workflow 内部节点负责。
3. **尺寸策略由 config 显式声明**：通过 `size_strategy` 字段（如 `"workflow_managed"`）声明，而非依赖 analyzer 推断。

### 3.4 关键设计决策

**统一 node_mapping 映射机制**：所有工作流参数通过 `node_mapping` 字典映射，而非硬编码节点名。新增工作流只需编写 config JSON，无需修改代码。

```json
{
  "prompt": {"node_title": "CLIP Text Encode (Positive Prompt)", "param": "text", "value_type": "string", "required": true},
  "seed": {"node_title": "KSampler", "param": "seed", "value_type": "integer", "auto_random": true},
  "width": {"node_title": "EmptySD3LatentImage", "param": "width", "value_type": "integer", "default": 832},
  "height": {"node_title": "EmptySD3LatentImage", "param": "height", "value_type": "integer", "default": 1280},
  "input_image": {"node_title": "Load Image", "param": "image", "value_type": "image", "input_strategy": "upload", "required": true}
}
```

映射条目字段：`node_title`（必需）、`param`（必需）、`value_type`（string|integer|image）、`input_strategy`（upload|direct）、`required`、`auto_random`、`default`。

- `input_strategy: "upload"` — 先上传文件到 ComfyUI，再设置参数为 `"{subfolder}/{name}"`（图片类型）
- `input_strategy: "direct"` — 直接设置参数值（string/integer 类型的默认行为）

### 3.5 服务器 URL 解析优先级

```
--server flag > config.local.json > COMFYUI_URL 环境变量 > 默认 http://127.0.0.1:8188
```

`config.local.json` 持久化用户指定的远程地址，通过 `--save-server <url>` 写入。含校验：非空、http/https 协议、去除尾斜杠。

### 3.6 错误处理

统一结构化 JSON 错误输出，fail-fast 原则：

| 错误码 | 触发条件 |
|--------|---------|
| `EMPTY_PROMPT` | 提示词为空 |
| `CONFIG_ERROR` | 配置文件格式错误（ConfigError） |
| `MAPPING_NOT_FOUND` | node_mapping 中缺少必需的 prompt 映射 |
| `WORKFLOW_NOT_REGISTERED` | workflow ID 不在注册表中 |
| `WORKFLOW_FILE_NOT_FOUND` | 工作流 JSON 文件不存在 |
| `WORKFLOW_LOAD_FAILED` | 加载工作流 JSON 失败 |
| `EXECUTION_FAILED` | ComfyUI 执行失败 |
| `NO_OUTPUT` | 执行完成但无输出图片 |
| `SAVE_FAILED` | 图片保存失败 |
| `SERVER_UNAVAILABLE` | ComfyUI 服务器不可达 |

计划中的错误码（img2img）：`NO_INPUT_IMAGE`、`INPUT_IMAGE_NOT_FOUND`、`IMAGE_UPLOAD_FAILED`、`NODE_NOT_FOUND`、`PARAM_NOT_FOUND`、`INVALID_PARAM_TYPE`。

## 4. 关键模块说明

### 4.1 `workflow_config.py` — WorkflowConfig + ConfigError + 注册表

- `WorkflowConfig` dataclass：`workflow_id`、`workflow_file`、`output_node_title`、`node_mapping`、`capability`、`description`
- `ConfigError` 异常：配置文件无效时抛出，CLI 捕获后输出 `CONFIG_ERROR` 错误码
- `from_json_file()`：从 JSON 文件加载，校验必需字段，缺少时抛出 ConfigError
- `load_configs_from_dir()`：批量加载 `*.config.json`，任一失败则传播 ConfigError
- `WORKFLOW_REGISTRY`：全局注册表，优先 JSON 配置，内置 `z_image_turbo` 作为 fallback

### 4.2 `executor.py` — 通用工作流执行器

执行流程：校验 node_mapping → 加载工作流 → 应用参数（prompt/seed/dimensions）→ 异步执行 → 获取输出 → 保存图片 → 返回 `GenerationResult`。

核心特点：
- 通过 `node_mapping` 泛化参数设置，不硬编码节点名
- `asyncio.new_event_loop()` 处理 `comfy_api_simplified` 的异步 API
- 每个 `GenerationResult` 包含 `success`、`outputs`、`error`、`metadata`

### 4.3 `config.py` — 服务器配置

- `get_comfyui_url()`：多级优先级 URL 解析
- `save_comfyui_url()`：持久化到 `config.local.json`（含校验）
- `check_server()`：通过 GET `/system_stats` 检查可用性

### 4.4 `run.py` — CLI 入口

```
python scripts/run.py "prompt text"
python scripts/run.py --workflow z_image_turbo --count 2 --prompt "..."
python scripts/run.py --check
python scripts/run.py --save-server http://192.168.1.100:8188
```

参数：`--workflow`、`--prompt`、`--count`、`--server`、`--save-server`、`--output`、`--check`

### 4.5 `analyze_workflow.py` — 工作流分析器

从工作流 JSON 自动生成 config 模板：
- 通过 class_type 启发式识别节点类型（CLIPTextEncode → prompt、KSampler → seed 等）
- 输出 `node_mapping` 和 `_discovered_nodes`（供人工 review）
- 生成的 config 需人工确认后使用（review-only，不自动注册）

### 4.6 `models/result.py` — GenerationResult

```python
@dataclass
class GenerationResult:
    success: bool
    workflow_id: str
    status: str          # "completed" | "failed" | "server_unavailable"
    outputs: list[dict]  # [{"path": ..., "filename": ..., "size_bytes": ...}]
    error: dict | None   # {"code": "ERROR_CODE", "message": "..."}
    job_id: str | None
    metadata: dict       # {"prompt": ..., "seed": ..., "width": ..., "height": ...}
```

## 5. 外部依赖

- `comfy_api_simplified` — ComfyUI API 封装（`ComfyApiWrapper`、`ComfyWorkflowWrapper`）
  - 安装：`pip install git+https://github.com/MieMieeeee/run_comfyui_workflow.git`
  - 关键 API：`upload_image(path)` → `{name, subfolder}`、`queue_prompt_and_wait(wf)`、`get_image(filename, subfolder, type)`

## 6. 测试覆盖

68 个测试，覆盖：
- `test_config.py` — URL 解析优先级、save 校验（非空、协议、尾斜杠）
- `test_workflow_config.py` — JSON 加载、ConfigError、node_mapping 校验、value_type 字段、8 个 bad config 用例
- `test_executor.py` — node_mapping 参数设置、seed 随机化、错误码
- `test_cli.py` — 参数解析、--save-server、错误码输出
- `test_analyze_workflow.py` — 节点发现、value_type 推断
- `test_result.py` — GenerationResult 构造和序列化
- `test_integration.py` — 需真实 ComfyUI，默认 skip

## 7. 下一步：image_to_image 实现

计划详见 `review/PLAN_IMAGE_TO_IMAGE.md`，6 个阶段：

1. **Phase 1**: 工作流配置 — 复制 Klein 工作流 JSON + 手工编写 config（含 `value_type: "image"`, `input_strategy: "upload"`）
2. **Phase 2**: Executor 扩展 — 新增 `input_images` 参数，upload + 参数拼接逻辑
3. **Phase 3**: 集成测试 — mock 验证 upload 调用，手工验证 Klein 工作流
4. **Phase 4**: CLI `--image` 参数 — 支持 `--image photo.png` 和 `--image input_image=photo.png`
5. **Phase 5**: Analyzer 扩展 — 识别 LoadImage，检测尺寸跟随模式
6. **Phase 6**: SKILL.md 更新 + 完整测试

成功标准（8 条）已定义在计划文档中。

## 8. Review 关注点建议

- `reference_to_image` vs `image_to_image` 的命名和边界是否清晰
- `node_mapping` 映射机制的扩展性（特别是 img2img 的 `value_type: "image"` + `input_strategy: "upload"`）
- 错误码体系是否完整
- 分析器启发式规则的准确性和局限性
- img2img 实现计划的阶段划分和执行顺序是否合理
