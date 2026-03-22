# -*- coding: utf-8 -*-
"""
GLM-4.7 API 简单测试
验证 API 调用是否正常工作
"""

import os
import sys
import io

# 修复控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from zai import ZhipuAiClient

def test_glm47():
    """测试 GLM-4.7 API"""
    api_key = "809fc06b8b744d719d870463211f7dd0.0Lc5qs0W20PMzjfW"

    print("=" * 60)
    print("测试 GLM-4.7 API 连接")
    print("=" * 60)

    # 初始化客户端
    client = ZhipuAiClient(api_key=api_key)
    print("客户端初始化成功")

    # 测试请求
    test_messages = [
        {"role": "user", "content": "请用一句话回答：北京位于中国的哪个方向？"}
    ]

    print("\n发送测试请求...")
    print(f"问题: {test_messages[0]['content']}")

    try:
        response = client.chat.completions.create(
            model="glm-4.7",
            messages=test_messages,
            max_tokens=512,
            temperature=0.7,
        )

        # 获取回复
        content = response.choices[0].message.content
        print(f"\n回复: {content}")

        # 检查是否有推理内容
        if hasattr(response.choices[0].message, 'reasoning_content'):
            reasoning = response.choices[0].message.reasoning_content
            if reasoning:
                print(f"\n推理过程: {reasoning[:200]}...")

        # Token 使用
        if hasattr(response, 'usage'):
            print(f"\nToken 使用: prompt={response.usage.prompt_tokens}, completion={response.usage.completion_tokens}, total={response.usage.total_tokens}")

        return True

    except Exception as e:
        print(f"\n错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_glm47()
    print("\n" + "=" * 60)
    print("测试结果:", "成功 ✓" if success else "失败 ✗")
    print("=" * 60)
