"""
ComfyUI API Simplified 自定义异常模块
(Vendored subset for comfyui-skill — see VENDORING.md)
"""

class ComfyApiError(Exception):
    """ComfyUI API 基础异常"""
    pass


class ConnectionError(ComfyApiError):
    """连接错误"""
    pass


class ExecutionError(ComfyApiError):
    """工作流执行错误"""
    pass


class NodeNotFoundError(ComfyApiError):
    """节点未找到错误"""
    pass


class PromptCategoryError(ComfyApiError):
    """提示词类别错误"""
    pass
