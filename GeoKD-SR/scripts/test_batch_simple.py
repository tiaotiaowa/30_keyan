#!/usr/bin/env python3
"""
简单测试脚本 - 测试API调用能否一次生成5条数据
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

def test_batch():
    """测试批量生成"""
    print("=" * 60)
    print("测试批量生成功能 - 一次调用生成5条数据")
    print("=" * 60)

    # 加载提示词
    with open('data/prompts/agent_splits/agent1_prompts.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    prompts = data['prompts'][:5]
    print(f"加载 {len(prompts)} 条提示词")
    for i, p in enumerate(prompts, 1):
        e1 = p.get('entity1', {})
        e2 = p.get('entity2', {})
        print(f"  {i}. {e1.get('name')} - {e2.get('name')} ({p.get('topology_subtype')})")

        print(f"     entity1: {e1.get('name')} ({e1.get('type')}), coords: {e1.get('coords')}")
        print(f"     entity2: {e2.get('name')} ({e2.get('type')}), coords: {e2.get('coords')}")
        print()

    print("\n开始API调用...")
    start_time = time.time()

    client = ZhipuAI(api_key=API_KEY)

    # 构建批量提示词
    batch_prompt = f"""你是一位资深的地理空间数据集设计专家，拥有以下专业能力：
1. 精通中国地理知识，包括省市区划、山川河流、地标建筑等
2. 擅长设计多层次、多维度的地理空间推理问题
3. 能够根据不同难度级别设计相应复杂度的地理问题
4. 熟悉拓扑关系（包含、相邻、重叠、相离等)的空间推理

你的任务是设计高质量的地理空间推理数据集，确保：
- 问题表述多样化和自然化
- 不同难度的问题具有明显的复杂度差异
- 推理过程清晰、逻辑严密
- 地理信息准确、坐标数据合理

"""

    # 添加5条数据的具体信息
    for i, p in enumerate(prompts):
        e1 = p.get('entity1', {})
        e2 = p.get('entity2', {})
        batch_prompt += f"""【数据{i}】
- 实体1: {e1.get('name')} ({e1.get('type')})，坐标: {e1.get('coords')}
- 实体2: {e2.get('name')} ({e2.get('type')})，坐标: {e2.get('coords')}
- 拓扑子类型: {p.get('topology_subtype')}
- 难度: {p.get('difficulty')}
- 要求Question长度: {'30-50字符' if p.get('difficulty') == 'easy' else '50-100字符' if p.get('difficulty') == 'medium' else '80-150字符'}

---

"""

    # 调用API
    print("\n开始调用GLM-4.7 API...")
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": batch_prompt}],
        max_tokens=8192,
        temperature=0.95,
        stream=False
    )

    if response.choices:
        content = response.choices[0].message.content
        print(f"\n响应内容长度: {len(content)} 字符")

        # 提取JSON
        results = []
        parts = content.split("---DATA---")

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # 查找JSON对象
            brace_count = 0
            json_start = -1
            for i, char in enumerate(part):
                if char == '{':
                    if brace_count == 0:
                        json_start = i
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and json_start >= 0:
                        json_str = part[json_start:i+1]
                        try:
                            data = json.loads(json_str)
                            if data.get('question'):
                                results.append(data)
                        except json.JSONDecodeError:
                            pass

                        json_start = -1

        print(f"\n解析完成，成功提取 {len(results)} 个JSON")

        elapsed = time.time() - start_time
        print(f"\n成功生成 {len(results)} 条数据!")
        print(f"耗时: {elapsed:.2f} 秒")

        # 显示生成结果
        print("\n生成结果示例:")
        for i, r in enumerate(results[:3], 1):
            print(f"\n--- 数据 {i} ---")
            print(f"  ID: {r.get('id', 'N/A')}")
            print(f"  Question: {r.get('question', 'N/A')}")
            print(f"  Answer: {r.get('answer', 'N/a')[:100]}...")
            print(f"  Topology: {r.get('topology_subtype', 'N/A')}")
            print(f"  Difficulty: {r.get('difficulty', 'N/A')}")
            print(f"  Entities: {len(r.get('entities', []))}")
            print(f"  Reasoning Chain: {len(r.get('reasoning_chain', []))} 步)

    except Exception as e:
        print(f"\n错误: {e}")

    finally:
        print("\n测试完成!")

if __name__ == "__main__":
    test_batch()
