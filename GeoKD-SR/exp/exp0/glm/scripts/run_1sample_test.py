# -*- coding: utf-8 -*-
"""
GLM-4.7 单样本评测测试
验证完整评测流程
"""

import os
import sys
import io
import json
from pathlib import Path

# 修复控制台编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 设置 API Key
os.environ['ZHIPUAI_API_KEY'] = '809fc06b8b744d719d870463211f7dd0.0Lc5qs0W20PMzjfW'

# 添加项目路径
# 脚本在 exp/exp0/glm/scripts/，项目根目录是往上4级
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from zai import ZhipuAiClient


def format_inference_prompt(question: str):
    """格式化推理Prompt"""
    return [
        {"role": "user", "content": f"""你是一个地理空间推理专家。请根据问题给出准确、简洁的答案。

问题: {question}

请直接给出答案，不需要解释过程。答案格式要求：
- 方向问题：直接说明方向，如"东南方向"
- 距离问题：给出具体数值，如"约1200公里"
- 拓扑问题：明确说明关系，如"是的，XX位于YY内部"
- 复合问题：同时给出方向和距离

答案:"""}
    ]


def test_1sample():
    """测试1条样本"""
    print("=" * 60)
    print("GLM-4.7 单样本评测测试")
    print("=" * 60)

    # 加载测试数据
    test_file = PROJECT_ROOT / "data" / "splits" / "test.jsonl"
    print(f"\n项目根目录: {PROJECT_ROOT}")
    print(f"脚本目录: {SCRIPT_DIR}")
    print(f"加载测试数据: {test_file}")
    print(f"文件存在: {test_file.exists()}")

    with open(test_file, 'r', encoding='utf-8') as f:
        first_line = f.readline()
        item = json.loads(first_line)

    print(f"\n样本数据:")
    print(f"  ID: {item.get('id', 'N/A')}")
    print(f"  类型: {item.get('spatial_relation_type', 'N/A')}")
    print(f"  问题: {item['question']}")
    print(f"  标准答案: {item.get('answer', 'N/A')}")

    # 初始化客户端
    api_key = os.environ['ZHIPUAI_API_KEY']
    client = ZhipuAiClient(api_key=api_key)
    print("\n客户端初始化成功")

    # 格式化 Prompt
    messages = format_inference_prompt(item['question'])
    print(f"\n发送请求到 GLM-4.7...")

    try:
        response = client.chat.completions.create(
            model="glm-4.7",
            messages=messages,
            max_tokens=512,
            temperature=0.1,
        )

        # 打印响应结构（调试用）
        # print(f"\n响应对象: {response}")

        prediction = response.choices[0].message.content

        # 检查是否有 reasoning_content
        reasoning_preview = ""
        if hasattr(response.choices[0].message, 'reasoning_content'):
            reasoning = response.choices[0].message.reasoning_content
            if reasoning:
                reasoning_preview = reasoning[:200] + "..."

        print("\n" + "=" * 60)
        print("评测结果")
        print("=" * 60)
        print(f"ID: {item.get('id', 'N/A')}")
        print(f"类型: {item.get('spatial_relation_type', 'N/A')}")
        print(f"问题: {item['question']}")
        print(f"标准答案: {item.get('answer', 'N/A')}")
        print(f"模型预测: {prediction}")

        if reasoning_preview:
            print(f"\n推理过程预览: {reasoning_preview}")

        # Token 使用
        if hasattr(response, 'usage'):
            print(f"\nToken 使用:")
            print(f"  Prompt: {response.usage.prompt_tokens}")
            print(f"  Completion: {response.usage.completion_tokens}")
            print(f"  Total: {response.usage.total_tokens}")

        print("\n" + "=" * 60)
        print("测试成功!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_1sample()
    sys.exit(0 if success else 1)
