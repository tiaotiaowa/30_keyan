#!/usr/bin/env python3
"""测试GLM-5 API"""
import os
import json
import sys
import urllib.request

# API配置
API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
API_KEY = os.getenv("ZHIPUAI_API_KEY", "809fc06b8b744d719d870463211f7dd0.0Lc5qs0W20PMzjfW"

payload = {
    "model": "glm-5",
    "messages": [{"role": "user", "content": "你好，请返回一个简单的JSON格式"}],
    "thinking": {"type": "enabled"},
    "max_tokens": 500,
    "temperature": 0.7
}

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}
req = urllib.request.Request(
    API_URL,
    data=json.dumps(payload).encode('utf-8'),
    headers=headers,
    method='POST'
)
try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        print("API响应成功!")
        print(json.dumps(data, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"API调用失败: {e}")
