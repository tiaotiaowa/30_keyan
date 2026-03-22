# -*- coding: utf-8 -*-
"""调试 GLM-4.7 响应结构"""

import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

os.environ['ZHIPUAI_API_KEY'] = '809fc06b8b744d719d870463211f7dd0.0Lc5qs0W20PMzjfW'

from zai import ZhipuAiClient

client = ZhipuAiClient(api_key=os.environ['ZHIPUAI_API_KEY'])

# 测试问题
test_questions = [
    "昆明和海口分别是云南省和海南省的省会城市，请问这两座城市之间的直线距离大约是多少公里？",
    "请问舟山市位于海伦市的什么方向？"
]

for i, q in enumerate(test_questions):
    print(f"\n{'='*60}")
    print(f"问题 {i+1}: {q[:50]}...")
    print('='*60)

    response = client.chat.completions.create(
        model="glm-4.7",
        messages=[{"role": "user", "content": f"请直接回答，不要解释：{q}"}],
        max_tokens=256,
        temperature=0.1,
    )

    msg = response.choices[0].message
    print(f"content: {repr(msg.content)}")
    print(f"reasoning_content: {repr(msg.reasoning_content[:500] if msg.reasoning_content else None)}...")
