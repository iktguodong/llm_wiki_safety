"""LLM调用服务
封装OpenAI兼容API的调用，支持多模型切换
"""

import asyncio
import json
import httpx
from typing import AsyncGenerator, Dict, List, Optional, Any
from backend.config import config


class LLMService:
    """LLM服务"""
    
    def __init__(self):
        # 将超时拆分为连接/读取/写入/连接池四类：
        # - connect: 快速发现服务商不可达。
        # - read: 设为 600s，避免长输出（如 HTML 生成）在非流式下被 120s read 超时提前终止；
        #   流式下每个 chunk 都会刷新 read 计时器，该值是“两个 chunk 之间”的最大间隔。
        # - write/pool: 常规值即可。
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=600.0, write=60.0, pool=10.0)
        )

    @staticmethod
    def _format_missing_api_key_message(provider: Dict, model: Dict) -> str:
        provider_name = provider.get("name") or provider.get("id") or "模型服务商"
        model_name = model.get("name") or model.get("id") or "当前模型"
        return (
            f"API Key 未配置，当前使用的是「{provider_name} / {model_name}」。"
            "请前往「设置」页补充 API Key 后再重试。"
        )

    @staticmethod
    def _format_missing_base_url_message(provider: Dict, model: Dict) -> str:
        provider_name = provider.get("name") or provider.get("id") or "模型服务商"
        model_name = model.get("name") or model.get("id") or "当前模型"
        return (
            f"模型服务地址（Base URL）未配置，当前使用的是「{provider_name} / {model_name}」。"
            "请前往「设置」页填写 Base URL 后再重试。"
        )

    @staticmethod
    def _format_request_exception(exc: Exception, provider: Dict, model: Dict) -> str:
        """将底层网络/请求异常转换成对用户更友好的提示。"""
        provider_name = provider.get("name") or provider.get("id") or "模型服务商"
        model_name = model.get("name") or model.get("id") or "当前模型"
        base_url = provider.get("base_url") or "(未配置)"
        raw = str(exc).strip()
        detail = raw or exc.__class__.__name__

        # DNS 解析失败：常见于 base_url 拼写错误或服务商域名不可达
        if (
            isinstance(exc, httpx.ConnectError)
            or "nodename nor servname" in raw
            or "Name or service not known" in raw
            or "getaddrinfo" in raw
            or "Temporary failure in name resolution" in raw
        ):
            return (
                f"无法连接到模型服务「{provider_name} / {model_name}」（{base_url}）。"
                "请检查：1) 是否已在「设置」页选择了正确的模型并填写 API Key；"
                "2) Base URL 是否拼写正确、域名可访问；3) 当前网络是否可以访问该服务。"
                f" 原始错误：{detail}"
            )
        if isinstance(exc, httpx.ConnectTimeout) or isinstance(exc, httpx.ReadTimeout) or isinstance(exc, httpx.TimeoutException):
            return (
                f"连接模型服务「{provider_name} / {model_name}」超时（{base_url}）。"
                "请检查网络或稍后重试。"
                f" 原始错误：{detail}"
            )
        if isinstance(exc, httpx.ProxyError):
            return (
                f"通过代理访问模型服务「{provider_name} / {model_name}」失败。"
                "请检查系统/终端代理配置。"
                f" 原始错误：{detail}"
            )
        if isinstance(exc, httpx.HTTPError):
            return (
                f"调用模型服务「{provider_name} / {model_name}」失败（{base_url}）。"
                f" 原始错误：{detail}"
            )
        return (
            f"调用模型服务「{provider_name} / {model_name}」时发生未知错误。"
            f" 原始错误：{detail}"
        )

    def _get_model_config(self, model_id: str) -> Optional[Dict]:
        """获取模型配置"""
        providers = config.get("models", {}).get("providers", [])
        for provider in providers:
            for model in provider.get("models", []):
                if model["id"] == model_id:
                    return {
                        "provider": provider,
                        "model": model
                    }
        return None

    async def chat_events(
        self,
        messages: List[Dict[str, str]],
        model_id: Optional[str] = None,
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        调用LLM并返回带结束信息的事件流。

        事件类型：
        - {"type": "chunk", "content": "..."}
        - {"type": "done", "finish_reason": "..."}
        - {"type": "error", "message": "..."}
        """
        model_id = model_id or config.get("current_model_id", "deepseek-v4-flash")
        model_config = self._get_model_config(model_id)

        if not model_config:
            yield {"type": "error", "message": "错误：模型配置未找到"}
            return

        provider = model_config["provider"]
        model = model_config["model"]

        api_key = (provider.get("api_key") or "").strip()
        if not api_key:
            yield {"type": "error", "message": self._format_missing_api_key_message(provider, model)}
            return

        base_url = (provider.get("base_url") or "").strip()
        if not base_url:
            yield {"type": "error", "message": self._format_missing_base_url_message(provider, model)}
            return

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model["id"],
            "messages": messages,
            "stream": stream,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        try:
            if not stream:
                response = await self.client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                if response.status_code != 200:
                    yield {"type": "error", "message": f"API错误 ({response.status_code}): {response.text}"}
                    return

                try:
                    data = response.json()
                except json.JSONDecodeError:
                    yield {"type": "error", "message": f"API错误：无法解析返回内容：{response.text[:500]}"}
                    return

                choice = data.get("choices", [{}])[0]
                content = choice.get("message", {}).get("content", "")
                finish_reason = choice.get("finish_reason")
                if content:
                    yield {"type": "chunk", "content": content}
                yield {"type": "done", "finish_reason": finish_reason}
                return

            finish_reason = None
            async with self.client.stream(
                "POST",
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    yield {"type": "error", "message": f"API错误 ({response.status_code}): {error_text.decode()}"}
                    return

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    data = line[6:]
                    if data == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    choice = chunk.get("choices", [{}])[0]
                    delta = choice.get("delta", {})
                    if "content" in delta and delta["content"]:
                        yield {"type": "chunk", "content": delta["content"]}

                    maybe_finish_reason = choice.get("finish_reason")
                    if maybe_finish_reason:
                        finish_reason = maybe_finish_reason

            yield {"type": "done", "finish_reason": finish_reason}
        except asyncio.CancelledError:
            raise
        except Exception as e:
            yield {"type": "error", "message": self._format_request_exception(e, provider, model)}

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model_id: Optional[str] = None,
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """
        调用LLM进行对话
        
        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            model_id: 模型ID，None则使用当前模型
            stream: 是否流式输出
            temperature: 温度参数
        
        Yields:
            流式输出文本片段
        """
        async for event in self.chat_events(
            messages,
            model_id=model_id,
            stream=stream,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            if event.get("type") == "chunk":
                content = event.get("content") or ""
                if content:
                    yield content
            elif event.get("type") == "error":
                yield event.get("message") or "请求错误"
                return
    
    async def chat_sync(
        self,
        messages: List[Dict[str, str]],
        model_id: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """同步调用LLM，返回完整文本"""
        result = []
        async for event in self.chat_events(
            messages,
            model_id=model_id,
            stream=False,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            if event.get("type") == "chunk":
                content = event.get("content") or ""
                if content:
                    result.append(content)
            elif event.get("type") == "error":
                result.append(event.get("message") or "请求错误")
                return "".join(result)
        return "".join(result)
    
    async def validate(self, provider_id: str, api_key: str, base_url: str) -> Dict:
        """
        验证模型服务连接
        
        Returns:
            {"valid": bool, "message": str, "available_models": List[str]}
        """
        if not api_key or not api_key.strip():
            return {
                "valid": False,
                "message": "API Key 为空，请先在「设置」页填写后再测试连接。",
                "available_models": []
            }

        try:
            headers = {
                "Authorization": f"Bearer {api_key.strip()}",
                "Content-Type": "application/json"
            }
            
            response = await self.client.get(
                f"{base_url}/models",
                headers=headers,
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                models = [m.get("id", "") for m in data.get("data", [])]
                return {
                    "valid": True,
                    "message": "连接成功",
                    "available_models": models
                }
            else:
                return {
                    "valid": False,
                    "message": f"API返回错误: {response.status_code}",
                    "available_models": []
                }
        except Exception as e:
            return {
                "valid": False,
                "message": f"连接失败: {str(e)}",
                "available_models": []
            }
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()


# 全局LLM服务实例
llm_service = LLMService()
