#!/usr/bin/env python3
"""
最小化测试脚本 - 仅测试API连接
验证一次生成5条数据
"""

import sys
import io
import json
import time
from pathlib import Path
from zhipuai import ZhipuAI

# 配置
API_KEY = "90fec3d49a8c40babbacecc617b34cf3.i4lMb9sTCUQlHKMw"
MODEL_NAME = "glm-4.7"

print("=" * 60)
print("最小化测试 - 騡拟一次生成5条数据")
print("=" * 60)

sys.stdout.reconfigure(encoding='utf-8')
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
except:
    pass

# 加载提示词
    with open('data/prompts/agent_splits/agent1_prompts.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    prompts = data['prompts'][:5]
    print(f"加载 {len(prompts)} 条提示词")

    # 构建批量提示词
    batch_prompt = """请按照以下格式生成5条地理空间推理数据：
每条数据之间用"---DATA---" 分隔
JSON格式如下:
{
  "id": "geosr_topological_XXXXx_YYYYY",
  "question": "问题内容",
  "answer": "答案",
  "reasoning_chain": [5步推理链]
  "entities": [实体1, 实体2]
  "difficulty": "easy/medium/hard"
  "topology_subtype": "子类型"
}

"""

    # 调用API
    print("\n开始API调用...")
    start_time = time.time()

    response = client.chat.completions.create(
        model=MODEL_name,
        messages=[{"role": "user", "content": batch_prompt}],
        max_tokens=8192,
        temperature=0.95,
    )

    elapsed = time.time() - start_time
    print(f"API调用耗时: {elapsed:.2f} 秒")

    # 解析响应
    if response.choices:
        content = response.choices[0].message.content
        print(f"\n响应内容长度: {len(content)} 字符")

        # 解析JSON
        results = []
        parts = content.split("---DATA---")

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # 解析JSON
            try:
                data = json.loads(part)
                if self._validate_data(data):
                    results.append(data)
                    print(f"  解析成功: ID: {data.get('id')}")
                except:
                    print(f"  JSON解析失败: 尝试下一个")
                    pass

        print(f"\n成功解析 {len(results)} 条数据")

        # 显示结果
        print("\n生成结果:")
        for i, r in enumerate(results, 1):
            print(f"\n--- 数据 {i} ---")
            print(f"ID: {r.get('id', 'N/A')}")
            q = r.get('question', '')
            print(f"Question: {r.get('question')}")
            print(f"Length: {len(r.get('question'))} 字符")
            print(f"Answer: {r.get('answer')}")
            print(f"  Entities: {len(r.get('entities', []))} step_count = len(r.get('reasoning_chain', []))
            print(f"  Reasoning Chain: {len(step_count)} 步")

        # 风险
        print("\n数据质量分析:")
        for r in results:
            q = q.get('question', '')
            if len(q) < 30:
                print(f"  WARNING: 问题过短: {len(q)} 字符 (期望>=30)")
            if len(q) >= 80:
                print(f"  WARNING: 问题过长: {len(q)} 字符 (期望<80)")
            if len(q) >= 100:
                print(f"  WARNING: 问题过长: {len(q)} 字符 (期望<80-150)")
            print()

        # 清理测试文件
        import os
        test_output_file = 'data/geosr_chain/supplement/test_api_output.jsonl'
        if os.path.exists(test_output_file):
            os.remove(test_output_file)
            print("\n测试输出文件已清理")
        else:
            print("\n未生成有效数据，    else:
        print("API调用失败")

 finally:
    print("\n测试完成!")
