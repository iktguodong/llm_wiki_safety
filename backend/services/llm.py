"""
LLM调用服务
封装OpenAI兼容API的调用，支持多模型切换
"""

import json
import httpx
from typing import AsyncGenerator, Dict, List, Optional
from backend.config import config


class LLMService:
    """LLM服务"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=120.0)
    
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
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model_id: Optional[str] = None,
        stream: bool = False,
        temperature: float = 0.7
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
        model_id = model_id or config.get("current_model_id", "deepseek-chat")
        model_config = self._get_model_config(model_id)
        
        if not model_config:
            yield "错误：模型配置未找到"
            return
        
        provider = model_config["provider"]
        model = model_config["model"]
        
        headers = {
            "Authorization": f"Bearer {provider.get('api_key', '')}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model["id"],
            "messages": messages,
            "stream": stream,
            "temperature": temperature
        }
        
        try:
            async with self.client.stream(
                "POST",
                f"{provider['base_url']}/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    yield f"API错误 ({response.status_code}): {error_text.decode()}"
                    return
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            yield f"请求错误: {str(e)}"
    
    async def chat_sync(
        self,
        messages: List[Dict[str, str]],
        model_id: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """同步调用LLM，返回完整文本"""
        result = []
        async for chunk in self.chat(messages, model_id, stream=False, temperature=temperature):
            result.append(chunk)
        return "".join(result)
    
    async def validate(self, provider_id: str, api_key: str, base_url: str) -> Dict:
        """
        验证模型服务连接
        
        Returns:
            {"valid": bool, "message": str, "available_models": List[str]}
        """
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
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
