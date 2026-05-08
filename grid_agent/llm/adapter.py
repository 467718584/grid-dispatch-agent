"""
LLM Adapter - OpenAI兼容API适配器
"""
import requests
from typing import List, Dict, Optional
import json
import re


class LLMAdapter:
    """OpenAI兼容API适配器"""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None, model: str = "default"):
        """
        Args:
            base_url: LLM API地址，如 http://192.168.1.100:8000/v1
            api_key: API密钥（可选）
            model: 模型名称
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.model = model
        self._session = requests.Session()
    
    def _get_headers(self) -> Dict:
        """构建请求头"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    async def chat(self, messages: List[Dict], model: Optional[str] = None) -> str:
        """
        发送对话请求
        
        Args:
            messages: [{"role": "user/assistant/system", "content": "..."}]
            model: 可覆盖默认模型
        
        Returns:
            LLM响应文本
        """
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": 0.7
        }
        
        response = self._session.post(
            f"{self.base_url}/chat/completions",
            headers=self._get_headers(),
            json=payload,
            timeout=30
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"LLM API error: {response.status_code} - {response.text}")
        
        result = response.json()
        return result["choices"][0]["message"]["content"]
    
    async def structured_output(self, prompt: str, output_schema: Dict) -> Dict:
        """
        生成结构化JSON输出
        
        Args:
            prompt: 输入提示
            output_schema: 期望输出的JSON Schema
        
        Returns:
            结构化输出字典
        """
        schema_str = json.dumps(output_schema, ensure_ascii=False)
        full_prompt = f"""{prompt}

请根据上述信息，输出符合以下JSON Schema的响应：
{schema_str}

只输出JSON，不要包含其他内容。"""

        messages = [{"role": "user", "content": full_prompt}]
        response_text = await self.chat(messages)
        
        return self._extract_json(response_text)
    
    def _extract_json(self, text: str) -> Dict:
        """从文本中提取JSON"""
        text = text.strip()
        
        if text.startswith('{'):
            try:
                return json.loads(text)
            except:
                pass
        
        match = re.search(r'```json\s*(\{[\s\S]*\})\s*```', text)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass
        
        return {"raw": text}