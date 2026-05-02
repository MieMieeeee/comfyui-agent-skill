"""Convenience wrapper: 使用 z_image_turbo 工作流从文本出图.

封装 `execute_workflow` + 内置 `Z_IMAGE_TURBO` 配置。需要已注册的 ComfyUI；HTTP/WebSocket 客户端在仓库内
`scripts/comfy_api_simplified/`（vendored，见项目根 `VENDORING.md`），无需从 git 单独安装。
"""
from __future__ import annotations

from pathlib import Path

from comfyui.config import get_user_data_root, get_workflows_dir
from comfyui.models.result import GenerationResult
from comfyui.services.executor import execute_workflow
from comfyui.services.workflow_config import Z_IMAGE_TURBO


def execute(
    prompt: str,
    server_url: str | None = None,
    results_dir: str | Path | None = None,
    skill_root: Path | None = None,
    width: int | None = None,
    height: int | None = None,
) -> GenerationResult:
    """执行 z_image_turbo 文生图工作流.

    Args:
        prompt: 英文/自然语言提示词（正面）。
        server_url: ComfyUI 服务根 URL；省略时从 `COMFYUI_URL` / `config.local.json` / `http://127.0.0.1:8188` 解析。
        results_dir: 输出目录；省略时使用技能根下 ``results/%Y%m%d/%H%M%S_{job_id}/``（与 CLI 默认一致）。
        width, height: 可选像素尺寸；须同时传入或同时省略，对应 CLI ``--width`` / ``--height``。
        skill_root: 技能根目录（含 `assets/`）；默认从包内 `config` 自动解析（无需改 PYTHONPATH 若已 `pip install -e .`）。

    Returns:
        ``GenerationResult``：成功时含 `outputs` 中本地保存路径，失败时含 `error.code` / `message`。

    Examples:
        在仓库根或已安装包环境下::

            from comfyui.services.z_image_turbo import execute
            r = execute(prompt="a red apple on a white table, photorealistic")
            if r.success:
                print(r.outputs[0]["path"])
            else:
                print(r.error)

        命令行（推荐，无需手写 PYTHONPATH 若已可编辑安装）::

            python -m comfyui generate -p "a cat" --output ./out
    """
    root = skill_root or get_user_data_root()
    out = Path(results_dir) if results_dir else None

    return execute_workflow(
        config=Z_IMAGE_TURBO,
        prompt=prompt,
        skill_root=root,
        server_url=server_url,
        results_dir=out,
        width=width,
        height=height,
        workflows_dir=get_workflows_dir(),
    )
