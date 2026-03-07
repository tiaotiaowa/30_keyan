#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""简单的GLM-5 API测试"""
import os
import json
import urllib.request

# 从.env加载API密钥
def load_api_key():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('ZHIPUAI_API_KEY='):
                    return line.split('=', 1)[1].strip()
    return os.getenv('ZHIPUAI_API_KEY', '')

# 加载配置
api_key = load_api_key()
print(f"API密钥: {api_key[:20]}...")

api_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}
payload = {
    "model": "glm-5",
    "messages": [{"role": "user", "content": "你好，请返回一个简单的JSON格式"}],
    "thinking": {"type": "enabled"},
    "max_tokens": 500,
    "temperature": 0.7
}
# 发送请求
req_data = json.dumps(payload).encode('utf-8')
request = urllib.request.Request(api_url, data=req_data, headers=headers)
try:
    with urllib.request.urlopen(request, timeout=120) as resp:
        response_data = resp.read().decode('utf-8')
        print("API响应:")
        print(response_data[:500])
        data = json.loads(response_data)
        print("解析后的数据:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
except urllib.error.URLError as e:
    print(f"URL错误: {e}")
except Exception as e:
    print(f"其他错误: {e}")
