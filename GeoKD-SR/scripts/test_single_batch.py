#!/usr/bin/env python3
"""
单批次测试 - 騡拟一次生成5条数据
"""

import sys
import io
import json
import time
from zhipuai import ZhipuAI

# 配置
API_KEY = "90fec3d49a8c40babbacecc617b34cf3.i4lMb9sTCUQlHKMw"
MODEL_NAME = "glm-4.7"
BATCH_SIZE = 5

def test_single_batch():
    print("=" * 60)
    print("单批次测试 - 模拟一次生成5条数据")
    print("=" * 60)
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except:
        pass

    # 加载1条提示词
    with open('data/prompts/agent_splits/agent1_prompts.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        p = data['prompts'][0]
        print(f"加载1条提示词")

        # 构建批量提示词
        batch_prompt = """你是一位资深的地理空间数据集设计专家。拥有以下专业能力：
1. 精通中国地理知识，包括省市区划、山川河流、地标建筑等
2. 擅长设计多层次、多维度的地理空间推理问题
3. 能够根据不同难度级别设计相应复杂度的地理问题
4. 熟悉拓扑关系（包含、相邻、重叠、相离等)的空间推理

你的任务是设计高质量的地理空间推理数据集，确保：
- 问题表述多样化和自然化
- 不同难度的问题具有明显的复杂度差异
- 推理过程清晰、逻辑严密
- 地理信息准确、坐标数据合理

请按照以下格式生成1条地理空间推理数据
每条数据之间用"---DATA---" 分隔
JSON格式如下:
{
  "id": "geosr_topological_00001_00001",
  "question": "问题内容",
  "answer": "答案内容",
  "reasoning_chain": [5步推理链]
  "entities": [实体1, 实体2]
  "difficulty": "easy/medium/hard"
  "topology_subtype": "子类型"
}
"""
        e1 = p.get('entity1', {})
        e2 = p.get('entity2', {})
        batch_prompt += f"""
【数据1】
- 实体1: {e1.get('name')} ({e1.get('type')})，坐标: {e1.get('coords')}
- 实体2: {e2.get('name')} ({e2.get('type')})，坐标: {e2.get('coords')}
- 拓扑子类型: {p.get('topology_subtype')}
- 难度: {p.get('difficulty')}
- 要求Question长度: {'30-50字符' if p.get('difficulty') == 'easy' else '50-100字符' if p.get('difficulty') == 'medium' else '80-150字符'}
"""
        print(f"\n开始API调用...")
        start_time = time.time()
        response = client.chat.completions.create(
            model=MODEL_name,
            messages=[{"role": "user", "content": batch_prompt}],
            max_tokens=8192,
            temperature=0.95
        )
        elapsed = time.time() - start_time
        print(f"API调用耗时: {elapsed:.2f} 秒")
        print(f"成功生成响应")

        # 解析响应
        content = response.choices[0].message.content
        print(f"响应内容长度: {len(content)} 字符")

        # 解析JSON
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
                            results.append(data)
                            print(f"  解析成功: {data.get('id')}")
                        except json.JSONDecodeError:
                            print(f"  JSON解析失败: 跳过")
                        except Exception as e:
                            print(f"  解析错误: {e}")

        print(f"\n成功解析 {len(results)} 条数据")
        print(f"  总耗时: {time.time() - start_time:.2f} 秒")

        # 显示结果
        print("\n生成结果:")
        for i, r in enumerate(results, 1):
            print(f"\n--- 数据 {i} ---")
            print(f"ID: {r.get('id')}")
            q = r.get('question', '')
            print(f"Question: {q}")
            print(f"Length: {len(q)} 字符")
            print(f"Answer: {r.get('answer')}")
            print(f"  Entities: {len(r.get('entities', []))}
            steps = r.get('reasoning_chain', [])
            print(f"  Reasoning Chain: {len(steps)} 步")
            print(f"  Topology: {r.get('topology_subtype')}")
            print(f"  Difficulty: {r.get('difficulty')}")
    else:
        print("\n未生成有效数据")
    else:
        print("API调用失败")
    finally:
        print("\n测试完成!")

if __name__ == "__main__":
    test_single_batch()
