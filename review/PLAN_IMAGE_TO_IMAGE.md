# 图生图（Image-to-Image）实现计划

## 目标

支持用户提供一张输入图片 + 编辑指令，通过 ComfyUI img2img 工作流进行图像编辑，返回编辑后的图片。

第一个 img2img 工作流：**Flux2-Klein 图像编辑**（`klein_edit`）

此工作流不仅限于换衣服，而是一个通用的图像编辑工作流：用户上传图片 + 描述编辑意图，Agent 使用 `image_to_image` 提示词增强将编辑意图转化为完整的英文编辑指令，workflow 保持原图的姿态/结构/构图。

## 参考实现分析

基于 `comfy_api_simplified/scripts/klein/klein_chage_cloth.py` + `Flux2-Klein-换衣服.json`：

**调用流程**：
```python
api = ComfyApi("http://127.0.0.1:8188/")
wf = Workflow("Flux2-Klein-换衣服.json")
wf.set_node_param("CLIP Text Encode (Positive Prompt)", "text", prompt)
results = api.queue_and_wait_images(wf, "Save Image")
```

**关键观察**：
- 脚本中 **没有调用 `upload_image`** — 因为 LoadImage 节点的 `image` 参数是硬编码的文件名（`"z-image-720x1280-..."`），图片已经在 ComfyUI 的 input 目录里
- 实际生产中需要 `upload_image` 先把用户图片上传到 ComfyUI
- 工作流用 `GetImageSize` 获取输入图尺寸 → `EmptyFlux2LatentImage` → **尺寸由输入图决定，不需要用户指定**

**Klein 换衣服工作流节点**：

| 节点 | class_type | node_mapping 角色 |
|------|-----------|------------------|
| Load Image (76) | `LoadImage` | `input_image` (value_type: image, required) |
| CLIP Positive (108) | `CLIPTextEncode` | `prompt` (value_type: string, required) |
| CLIP Negative (109) | `CLIPTextEncode` | `negative_prompt` (value_type: string) |
| KSampler (146) | `KSampler` | `seed` (value_type: integer, auto_random) |
| Save Image (9) | `SaveImage` | output_node_title |
| UNETLoader (106) | `UNETLoader` | 固定参数 |
| CLIPLoader (107) | `CLIPLoader` | 固定参数 |
| VAELoader (110) | `VAELoader` | 固定参数 |
| VAE Encode (116) | `VAEEncode` | 管线内部 |
| Get Image Size (114) | `GetImageSize` | 管线内部 |
| ReferenceLatent (115,117) | `ReferenceLatent` | 管线内部 |
| Empty Flux 2 Latent (128) | `EmptyFlux2LatentImage` | 管线内部 |

**注意**：此工作流**没有 width/height 映射**，尺寸跟随输入图片。analyzer 应检测到 `GetImageSize` + `EmptyLatentImage` 组合时不生成独立的 width/height 映射。

## 设计原则

1. **输入图片只上传，不预处理**：Skill 只负责校验文件存在、上传到 ComfyUI、将上传结果绑定到 config 指定的节点参数。Skill **不**做 resize、crop、pad、尺寸推断或任何图像预处理。所有尺寸/比例/latent 处理统一由 workflow 内部节点负责。
2. **尺寸策略由 config 显式声明**：当 workflow 内部自行处理尺寸（如 `GetImageSize` + `EmptyLatentImage`）时，config 应声明 `"size_strategy": "workflow_managed"`，而非依赖 analyzer 推断。Executor 读到此字段时跳过 width/height 参数设置。

## 图片上传格式约定

`comfy_api_simplified` 的 `upload_image(path)` 返回：
```json
{"name": "export-a.png", "subfolder": "default_upload_folder", "type": "input"}
```

`LoadImage` 节点的 `image` 参数期待的值为 `"{subfolder}/{name}"`：
- `subfolder` 为空时：值为 `"export-a.png"`
- `subfolder` 非空时：值为 `"default_upload_folder/export-a.png"`

此约定已通过真实 ComfyUI 测试验证。

## 与现有能力的区别

| 维度 | `text_to_image` | `reference_to_image` | `image_to_image`（本计划） |
|------|----------------|---------------------|--------------------------|
| 输入图片 | 无 | Agent 视觉理解，不发给 ComfyUI | **上传到 ComfyUI**，作为工作流输入 |
| 提示词 | Agent 增强 | Agent 视觉+文本增强 | 用户提供编辑指令，Agent 增强 |
| 保真度 | N/A | 语义/风格方向 | **ComfyUI 真正 img2img**，保留结构/姿态 |
| 工作流 | z_image_turbo | 复用 z_image_turbo | **专用 img2img 工作流** |
| 尺寸控制 | config 默认值 | config 默认值 | **跟随输入图片** |

## 成功标准

以下标准全部通过时，image_to_image 视为实现完成：

1. 能上传一张本地图片到 ComfyUI（`api.upload_image`）
2. 能正确写入 LoadImage 节点的 `image` 参数（`{subfolder}/{name}` 格式）
3. 能生成至少一张输出图片并保存到本地
4. CLI `--image input_image=photo.png --workflow klein_change_cloth --prompt "..."` 能返回结构化 JSON 结果
5. 单图工作流支持简写 `--image photo.png`（自动匹配唯一的 image 角色）
6. 若工作流 `size_strategy` 为 `workflow_managed`，不需要用户手动指定 width/height，executor 不设置尺寸参数
7. 缺少必需图片输入时返回 `NO_INPUT_IMAGE` 错误
8. 图片文件不存在时返回 `INPUT_IMAGE_NOT_FOUND` 错误
9. 上传失败时返回 `IMAGE_UPLOAD_FAILED` 错误
10. 所有新增和既有测试通过

## 实现步骤

### Phase 1: 工作流配置 + 节点确认 ✅ 已完成

**改动文件**: `assets/workflows/`

1. ~~将 `Flux2-Klein-换衣服.json` 复制到 `assets/workflows/`~~ → 已重命名为 `klein_edit.json`
2. ~~手工编写 config JSON~~ → 已创建 `klein_edit.config.json`，确认以下节点：
   - LoadImage → `input_image` (value_type: image, input_strategy: upload)
   - CLIP Positive → `prompt`
   - CLIP Negative → `negative_prompt`
   - KSampler → `seed`
   - Save Image → output_node_title
3. 手工验证 `upload_image()` 返回结构 ✅ → 已确认返回 `{"name": "...", "subfolder": "default_upload_folder", "type": "input"}`
4. 确认此工作流**没有独立 width/height** ✅ → config 声明 `"size_strategy": "workflow_managed"`
5. 明确图片输入角色命名 ✅ → `input_image`，为未来多图工作流预留可扩展命名

### Phase 2: Executor 扩展 ✅ 已完成

**改动文件**: `executor.py`

1. `execute_workflow` 新增 `input_images: dict[str, Path] | None` 参数 ✅
2. 遍历 `value_type == "image"` 条目：校验存在 → upload → 绑定参数 ✅
3. `size_strategy == "workflow_managed"` 时跳过尺寸注入 ✅
4. API 实例前移到 workflow load 之后（upload 需要） ✅
5. 严格遵守：只上传，不 resize，不 crop，不推断尺寸 ✅

### Phase 3: 集成测试 ✅ 已完成

**改动文件**: `test_executor.py`, 手工验证

1. mock 验证 `upload_image` 被正确调用且参数拼接正确 ✅
2. ~~用真实 ComfyUI + Klein 工作流做一次手工验证~~ ✅ → 已用真实 export-a.png 验证端到端流程
3. 确认 `input_strategy: "upload"` 链路跑通 ✅

### Phase 4: CLI `--image` 参数 ✅ 已完成

**改动文件**: `run.py`

1. 新增 `--image` 参数，正式语法为 `--image key=path` ✅
2. 单图工作流支持简写 `--image photo.png`（自动匹配唯一的 image 角色） ✅
3. 校验文件存在性 ✅
4. 传给 executor 的 `input_images` 参数 ✅
5. 支持多次 `--image` 传入多图 ✅

### Phase 5: Analyzer 扩展

**注意**：此阶段在手工 config + executor 已验证正确之后再做。Analyzer 只做**提示**，不做策略决定。

**改动文件**: `analyze_workflow.py`

1. 识别 `LoadImage` / `LoadImageMask` 等 class_type → 生成 `value_type: "image"`, `input_strategy: "upload"` 映射
2. 检测到 `GetImageSize` + `EmptyLatentImage` 组合时，在 `_discovered_nodes` 中添加提示信息，**不生成** width/height 映射，建议 reviewer 设置 `"size_strategy": "workflow_managed"`
3. 用 Klein 工作流验证 analyzer 输出与手工 config 一致
4. Analyzer 的输出始终需要人工 review 确认，不自动注册到 WORKFLOW_REGISTRY

### Phase 6: SKILL.md 文档更新 + 完整测试

**改动文件**: `SKILL.md`, `test_cli.py`, `test_executor.py`, `test_analyze_workflow.py`

1. SKILL.md 更新：
   - 新增 `image_to_image` 能力文档（从 planned → implemented）
   - 新增 `--image` 参数说明
   - 更新错误码文档（`NO_INPUT_IMAGE`, `INPUT_IMAGE_NOT_FOUND`, `IMAGE_UPLOAD_FAILED`）
2. CLI 测试：
   - `--image input_image=photo.png` 显式角色名
   - `--image photo.png` 单图简写自动匹配
   - 图片不存在时的错误输出
3. Executor 测试：
   - upload_image 被正确调用且参数拼接正确
   - upload 失败时返回 `IMAGE_UPLOAD_FAILED`
   - 缺少必需图片时返回 `NO_INPUT_IMAGE`
   - 图片文件不存在时返回 `INPUT_IMAGE_NOT_FOUND`
   - `size_strategy: "workflow_managed"` 时不注入 width/height
4. Analyzer 测试：
   - 识别 LoadImage → `value_type: "image"`
   - 有 GetImageSize + EmptyLatent 时不生成 width/height，仅添加提示

## 文件影响范围

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `executor.py` | 修改 | 新增 input_images + upload 逻辑，api 创建时机前移 |
| `run.py` | 修改 | 新增 --image 参数 |
| `analyze_workflow.py` | 修改 | 识别 LoadImage，检测尺寸跟随模式 |
| `SKILL.md` | 修改 | 新增 image_to_image 能力文档 |
| `assets/workflows/klein_edit.json` | 新增 | 工作流 JSON |
| `assets/workflows/klein_edit.config.json` | 新增 | 工作流配置 |

## 不在范围内

- 视频输入/输出（工作流中有 VHS_LoadVideo 节点，但不在本计划范围）
- Mask/区域编辑（node_mapping 加 `value_type: "mask"` 即可扩展）
- GGUF 模型切换（工作流中有 UnetLoaderGGUF 节点，是 Klein 的特殊需求，不影响通用架构）
