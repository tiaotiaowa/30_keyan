#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GLM-5 API 简单测试脚本
"""

import os
import json
import re

# 设置API密钥
os.environ['ZHIPUAI_API_KEY'] = '809fc06b8b744d719d870463211f7dd0.0Lc5qs0W20PMzjfW'

def test_glm5_api():
    """测试GLM-5 API调用"""
    print("=" * 60)
    print("GLM-5 API 调用测试")
    print("=" * 60)

    try:
        from zhipuai import ZhipuAI
        client = ZhipuAI(api_key=os.environ['ZHIPUAI_API_KEY'])

        print("\n[1/3] 测试简单对话...")
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[
                {"role": "user", "content": "你好，请简单介绍一下你自己"}
            ],
        )
        print("[OK] API调用成功!")
        print(f"回复: {response.choices[0].message.content[:200]}...")

        print("\n[2/3] 测试JSON格式输出...")
        json_prompt = """请生成一个关于北京和上海的地理问题，返回严格的JSON格式，包含question和answer两个字段。

示例:
{"question": "北京在上海的什么方向?", "answer": "西北方向"}"""

        response2 = client.chat.completions.create(
            model="glm-4-flash",
            messages=[
                {"role": "user", "content": json_prompt}
            ],
        )

        content = response2.choices[0].message.content
        print(f"原始响应:\n{content}")

        # 尝试提取JSON
        json_match = re.search(r'\{[^{}]*\}', content)
        if json_match:
            try:
                result = json.loads(json_match.group())
                print(f"\n[OK] JSON解析成功!")
                print(f"问题: {result.get('question', 'N/A')}")
                print(f"答案: {result.get('answer', 'N/A')}")

                # 保存结果
                output_path = "data/geosr_chain/test_glm5.json"
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"\n[OK] 已保存到: {output_path}")

            except json.JSONDecodeError as e:
                print(f"[警告] JSON解析失败: {e}")
        else:
            print("[警告] 未找到JSON格式")

        print("\n" + "=" * 60)
        print("测试完成!")
        print("=" * 60)

    except Exception as e:
        print(f"[错误] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_glm5_api()
