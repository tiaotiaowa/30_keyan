#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test GLM-5 API connection"""
import json
import urllib.request
import os

# API key from .env file
api_key = "809fc06b8b744d719d870463211f7dd0.0Lc5qs0W20PMzjfW"
api_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

payload = {
    "model": "glm-5",
    "messages": [{"role": "user", "content": "Hello"}],
    "thinking": {"type": "enabled"},
    "max_tokens": 100
}
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}
print("Testing GLM-5 API connection...")
req = urllib.request.Request(
    api_url,
    data=json.dumps(payload).encode('utf-8'),
    headers=headers,
    method='POST'
)
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        print("API call successful!")
        print(json.dumps(data, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"API call failed: {e}")
