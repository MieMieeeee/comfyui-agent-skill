"""
ComfyUI 工作流包装模块
提供加载、编辑和保存 ComfyUI 工作流的功能

此模块是 comfy_workflow_wrapper.py 的重命名版本，
提供更简洁的模块名称和改进的类型注解。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterator, List, Optional

from .exceptions import NodeNotFoundError

_log = logging.getLogger(__name__)


class Workflow(dict):
    """
    ComfyUI 工作流包装类

    继承自 dict，可以像字典一样访问工作流数据，
    同时提供便捷的方法来修改节点参数。

    Example:
        >>> workflow = Workflow("workflow.json")
        >>> workflow.list_nodes()
        ['KSampler', 'CLIPTextEncode', ...]
        >>> workflow.set_node_param("KSampler", "seed", 12345)
        >>> workflow.get_node_param("KSampler", "seed")
        12345
    """

    def __init__(self, path: str) -> None:
        """
        从文件加载工作流

        Args:
            path: 工作流 JSON 文件路径

        Raises:
            FileNotFoundError: 文件不存在时抛出
            json.JSONDecodeError: JSON 格式错误时抛出
        """
        # 使用 UTF-8 编码读取工作流文件，避免平台相关编码问题
        with open(path, encoding="utf-8") as f:
            workflow_str = f.read()
        super().__init__(json.loads(workflow_str))

    def list_nodes(self) -> List[str]:
        """
        获取工作流中所有节点的标题列表

        Returns:
            节点标题列表
        """
        return [node["_meta"]["title"] for node in super().values()]

    def set_node_param(self, title: str, param: str, value: Any) -> None:
        """
        设置节点参数值

        注意：此方法会修改所有具有相同标题的节点。

        Args:
            title: 节点标题
            param: 参数名称
            value: 参数值

        Raises:
            NodeNotFoundError: 节点不存在时抛出
        """
        smth_changed = False
        for node in super().values():
            if node["_meta"]["title"] == title:
                _log.info(f"Setting parameter '{param}' of node '{title}' to '{value}'")
                node["inputs"][param] = value
                smth_changed = True

        if not smth_changed:
            raise NodeNotFoundError(f"Node '{title}' not found.")

    def get_node_param(self, title: str, param: str) -> Any:
        """
        获取节点参数值

        注意：如果有多个同名节点，返回第一个匹配节点的参数值。

        Args:
            title: 节点标题
            param: 参数名称

        Returns:
            参数值

        Raises:
            NodeNotFoundError: 节点不存在时抛出
        """
        for node in super().values():
            if node["_meta"]["title"] == title:
                return node["inputs"][param]
        raise NodeNotFoundError(f"Node '{title}' not found.")

    def get_node_id(self, title: str) -> str:
        """
        获取节点 ID

        注意：如果有多个同名节点，返回第一个匹配节点的 ID。

        Args:
            title: 节点标题

        Returns:
            节点 ID（字符串形式的数字）

        Raises:
            NodeNotFoundError: 节点不存在时抛出
        """
        for node_id, node in super().items():
            if node["_meta"]["title"] == title:
                return node_id
        raise NodeNotFoundError(f"Node '{title}' not found.")

    def get_nodes_by_title(self, title: str) -> Iterator[Dict[str, Any]]:
        """
        获取所有具有指定标题的节点

        Args:
            title: 节点标题

        Yields:
            节点数据字典
        """
        for node_id, node in super().items():
            if node["_meta"]["title"] == title:
                yield {"id": node_id, **node}

    def save_to_file(self, path: str) -> None:
        """
        保存工作流到文件

        Args:
            path: 目标文件路径
        """
        workflow_str = json.dumps(self, indent=4, ensure_ascii=False)
        # 使用 UTF-8 编码写入文件
        with open(path, "w+", encoding="utf-8") as f:
            f.write(workflow_str)
        _log.info(f"Workflow saved to {path}")

    def __repr__(self) -> str:
        """返回工作流的简洁表示"""
        node_count = len(self)
        titles = self.list_nodes()[:5]
        if len(self) > 5:
            titles_str = ", ".join(titles) + ", ..."
        else:
            titles_str = ", ".join(titles)
        return f"Workflow(nodes={node_count}, [{titles_str}])"


# 类型别名，保持向后兼容
ComfyWorkflowWrapper = Workflow


__all__ = ["Workflow", "ComfyWorkflowWrapper"]
