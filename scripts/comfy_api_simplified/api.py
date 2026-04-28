"""
ComfyUI API 包装模块
提供与 ComfyUI 服务器交互的核心功能

此模块是 comfy_api_wrapper.py 的重命名版本，
提供更简洁的模块名称和改进的类型注解。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional

import requests
import websockets
from requests.auth import HTTPBasicAuth
from requests.compat import urljoin, urlencode

from .exceptions import ComfyApiError, ConnectionError, ExecutionError

if TYPE_CHECKING:
    from .workflow import Workflow

_log = logging.getLogger(__name__)


class ComfyApi:
    """
    ComfyUI API 包装类

    提供与 ComfyUI 服务器交互的核心功能，包括：
    - 提交工作流
    - 上传图片
    - 获取生成结果
    - WebSocket 实时通信
    """

    def __init__(
        self,
        url: str = "http://127.0.0.1:8188",
        user: str = "",
        password: str = ""
    ) -> None:
        """
        初始化 ComfyApi 实例

        Args:
            url: ComfyUI 服务器地址，默认为 "http://127.0.0.1:8188"
            user: 认证用户名，可选
            password: 认证密码，可选
        """
        self.url = url
        self.auth: Optional[HTTPBasicAuth] = None
        url_without_protocol = url.split("//")[-1]

        # 确定 WebSocket 协议
        if "https" in url:
            ws_protocol = "wss"
        else:
            ws_protocol = "ws"

        # 构造 WebSocket URL
        if user:
            self.auth = HTTPBasicAuth(user, password)
            ws_url_base = f"{ws_protocol}://{user}:{password}@{url_without_protocol}"
        else:
            ws_url_base = f"{ws_protocol}://{url_without_protocol}"

        self.ws_url = urljoin(ws_url_base, "/ws?clientId={}")

    def queue_prompt(self, prompt: Dict[str, Any], client_id: Optional[str] = None) -> Dict[str, Any]:
        """
        将工作流提交到队列

        Args:
            prompt: 工作流 JSON 数据
            client_id: 客户端 ID，用于 WebSocket 通信

        Returns:
            服务器响应数据，包含 prompt_id

        Raises:
            ComfyApiError: 请求失败时抛出
        """
        p = {"prompt": prompt}
        if client_id:
            p["client_id"] = client_id

        data = json.dumps(p).encode("utf-8")
        _log.info(f"Posting prompt to {self.url}/prompt")

        resp = requests.post(urljoin(self.url, "/prompt"), data=data, auth=self.auth)
        _log.info(f"{resp.status_code}: {resp.reason}")

        if resp.status_code == 200:
            return resp.json()
        else:
            raise ComfyApiError(
                f"Request failed with status code {resp.status_code}: {resp.reason}"
            )

    async def queue_prompt_and_wait(self, prompt: Dict[str, Any]) -> str:
        """
        提交工作流并等待执行完成

        Args:
            prompt: 工作流 JSON 数据

        Returns:
            工作流执行 ID (prompt_id)

        Raises:
            ExecutionError: 执行出错时抛出
        """
        client_id = str(uuid.uuid4())
        resp = self.queue_prompt(prompt, client_id)
        _log.debug(resp)

        prompt_id = resp["prompt_id"]
        ws_url = self.ws_url.format(client_id)

        # 隐藏认证信息
        _log.info(f"Connecting to {ws_url.split('@')[-1]}")

        try:
            async with websockets.connect(uri=ws_url) as websocket:
                while True:
                    out = await websocket.recv()
                    if isinstance(out, str):
                        message = json.loads(out)

                        # 跳过监控消息
                        if message.get("type") == "crystools.monitor":
                            continue

                        _log.debug(message)

                        # 处理执行错误
                        if message.get("type") == "execution_error":
                            data = message.get("data", {})
                            if data.get("prompt_id") == prompt_id:
                                raise ExecutionError("Execution error occurred.")

                        # 处理状态更新
                        if message.get("type") == "status":
                            data = message.get("data", {})
                            exec_info = data.get("status", {}).get("exec_info", {})
                            if exec_info.get("queue_remaining") == 0:
                                return prompt_id

                        # 处理执行完成
                        if message.get("type") == "executing":
                            data = message.get("data", {})
                            if data.get("node") is None and data.get("prompt_id") == prompt_id:
                                return prompt_id
        except Exception as e:
            if isinstance(e, ExecutionError):
                raise
            raise ConnectionError(f"WebSocket connection error: {e}") from e

    def queue_and_wait_images(
        self,
        prompt: Workflow,
        output_node_title: str,
        loop: Optional[asyncio.AbstractEventLoop] = None
    ) -> Dict[str, bytes]:
        """
        提交工作流并等待图片生成完成

        Args:
            prompt: Workflow 工作流对象
            output_node_title: 输出节点标题
            loop: 事件循环，默认使用当前事件循环

        Returns:
            字典，键为图片文件名，值为图片二进制数据

        Raises:
            ComfyApiError: 请求失败时抛出
            ExecutionError: 执行出错时抛出
        """
        if loop is None:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

        prompt_id = loop.run_until_complete(self.queue_prompt_and_wait(prompt))
        history = self.get_history(prompt_id)
        image_node_id = prompt.get_node_id(output_node_title)

        try:
            images = history[prompt_id]["outputs"][image_node_id]["images"]
        except KeyError as e:
            raise ComfyApiError(f"Failed to get images from history: {e}") from e

        return {
            image["filename"]: self.get_image(
                image["filename"], image["subfolder"], image["type"]
            )
            for image in images
        }

    def queue_and_wait_videos(
        self,
        prompt: Workflow,
        output_node_title: str,
        loop: Optional[asyncio.AbstractEventLoop] = None
    ) -> Dict[str, bytes]:
        """
        提交工作流并等待视频生成完成

        Args:
            prompt: Workflow 工作流对象
            output_node_title: 输出节点标题
            loop: 事件循环，默认使用当前事件循环

        Returns:
            字典，键为视频文件名，值为视频二进制数据

        Raises:
            ComfyApiError: 请求失败时抛出
            ExecutionError: 执行出错时抛出
        """
        if loop is None:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

        prompt_id = loop.run_until_complete(self.queue_prompt_and_wait(prompt))
        history = self.get_history(prompt_id)
        video_node_id = prompt.get_node_id(output_node_title)

        try:
            videos = history[prompt_id]["outputs"][video_node_id]["videos"]
        except KeyError as e:
            raise ComfyApiError(f"Failed to get videos from history: {e}") from e

        return {
            video["filename"]: self.get_video(
                video["filename"], video["subfolder"], video["type"]
            )
            for video in videos
        }

    def get_video(
        self,
        filename: str,
        subfolder: str,
        folder_type: str
    ) -> bytes:
        """
        获取生成的视频

        Args:
            filename: 视频文件名
            subfolder: 子文件夹路径
            folder_type: 文件夹类型（如 "output"）

        Returns:
            视频二进制数据

        Raises:
            ComfyApiError: 请求失败时抛出
        """
        params = {
            "filename": filename,
            "subfolder": subfolder,
            "type": folder_type
        }
        url = urljoin(self.url, f"/view?{urlencode(params)}")
        _log.info(f"Getting video from {url}")

        resp = requests.get(url, auth=self.auth)
        _log.debug(f"{resp.status_code}: {resp.reason}")

        if resp.status_code == 200:
            return resp.content
        else:
            raise ComfyApiError(
                f"Request failed with status code {resp.status_code}: {resp.reason}"
            )

    def get_queue(self) -> Dict[str, Any]:
        """
        获取当前队列状态

        Returns:
            队列状态数据

        Raises:
            ComfyApiError: 请求失败时抛出
        """
        url = urljoin(self.url, "/queue")
        _log.info(f"Getting queue from {url}")

        resp = requests.get(url, auth=self.auth)

        if resp.status_code == 200:
            return resp.json()
        else:
            raise ComfyApiError(
                f"Request failed with status code {resp.status_code}: {resp.reason}"
            )

    def get_queue_size_before(self, prompt_id: str) -> int:
        """
        获取指定工作流在队列中的位置

        Args:
            prompt_id: 工作流 ID

        Returns:
            队列位置，0 表示正在执行

        Raises:
            ComfyApiError: 请求失败时抛出
            ValueError: prompt_id 不在队列中时抛出
        """
        resp = self.get_queue()

        # 检查是否正在执行
        for elem in resp.get("queue_running", []):
            if elem[1] == prompt_id:
                return 0

        # 检查在等待队列中的位置
        result = 1
        for elem in resp.get("queue_pending", []):
            if elem[1] == prompt_id:
                return result
            result += 1

        raise ValueError(f"prompt_id '{prompt_id}' is not in the queue")

    def get_history(self, prompt_id: str) -> Dict[str, Any]:
        """
        获取工作流执行历史

        Args:
            prompt_id: 工作流 ID

        Returns:
            执行历史数据

        Raises:
            ComfyApiError: 请求失败时抛出
        """
        url = urljoin(self.url, f"/history/{prompt_id}")
        _log.info(f"Getting history from {url}")

        resp = requests.get(url, auth=self.auth)

        if resp.status_code == 200:
            return resp.json()
        else:
            raise ComfyApiError(
                f"Request failed with status code {resp.status_code}: {resp.reason}"
            )

    def get_image(
        self,
        filename: str,
        subfolder: str,
        folder_type: str
    ) -> bytes:
        """
        获取生成的图片

        Args:
            filename: 图片文件名
            subfolder: 子文件夹路径
            folder_type: 文件夹类型（如 "output"）

        Returns:
            图片二进制数据

        Raises:
            ComfyApiError: 请求失败时抛出
        """
        params = {
            "filename": filename,
            "subfolder": subfolder,
            "type": folder_type
        }
        url = urljoin(self.url, f"/view?{urlencode(params)}")
        _log.info(f"Getting image from {url}")

        resp = requests.get(url, auth=self.auth)
        _log.debug(f"{resp.status_code}: {resp.reason}")

        if resp.status_code == 200:
            return resp.content
        else:
            raise ComfyApiError(
                f"Request failed with status code {resp.status_code}: {resp.reason}"
            )

    def upload_image(
        self,
        filename: str,
        subfolder: str = "default_upload_folder"
    ) -> Dict[str, Any]:
        """
        上传图片到 ComfyUI 服务器

        Args:
            filename: 本地图片文件路径
            subfolder: 目标子文件夹

        Returns:
            服务器响应数据，包含服务器上的文件名

        Raises:
            ComfyApiError: 请求失败时抛出
            FileNotFoundError: 文件不存在时抛出
        """
        url = urljoin(self.url, "/upload/image")
        serv_file = os.path.basename(filename)
        data = {"subfolder": subfolder}

        if not os.path.exists(filename):
            raise FileNotFoundError(f"Image file not found: {filename}")

        with open(filename, "rb") as f:
            files = {"image": (serv_file, f)}
            _log.info(f"Posting {filename} to {url} with data {data}")
            resp = requests.post(url, files=files, data=data, auth=self.auth)

        _log.debug(f"{resp.status_code}: {resp.reason}, {resp.text}")

        if resp.status_code == 200:
            return resp.json()
        else:
            raise ComfyApiError(
                f"Request failed with status code {resp.status_code}: {resp.reason}"
            )


# 类型别名，保持向后兼容
ComfyApiWrapper = ComfyApi


__all__ = ["ComfyApi", "ComfyApiWrapper"]
