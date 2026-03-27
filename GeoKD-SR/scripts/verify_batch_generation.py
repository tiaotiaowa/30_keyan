#!/usr/bin/env python3
"""
验证批量生成功能 - 一次API调用生成5条数据
"""
import sys
import io
import json
import time
from zhipuai import ZhipuAI

# 配置
API_KEY = "90fec3d49a8c40babbacecc617b34cf3.i4lMb9sTCUQlHKMw"
MODEL_NAME = "glm-4.7"

# 设置UTF-8编码
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except:
        pass

def verify_batch_generation():
    print("=" * 60)
    print("验证批量生成功能 - 一次调用生成5条数据")
    print("=" * 60)

    # 加载提示词
    with open('data/prompts/agent_splits/agent1_prompts.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    prompts = data['prompts'][:5]
    print(f"加载 {len(prompts)} 条提示词")

    # 构建批量提示词 (包含专家角色和多样性要求)
    batch_prompt = """你是一位资深的地理空间数据集设计专家，拥有以下专业能力：
1. 精通中国地理知识，包括省市区划、山川河流、地标建筑等
2. 擅长设计多层次、多维度的地理空间推理问题
3. 能够根据不同难度级别设计相应复杂度的地理问题
4. 熟悉拓扑关系（包含、相邻、重叠、相离等）的空间推理

【问题多样性要求】
1. 问句结构多样性：是否型、判断型、推理型、描述型、应用型
2. 背景信息多样性：Easy(30-50字符)、Medium(50-100字符)、Hard(80-150字符)

请按照以下要求生成5条地理空间推理数据，每条数据之间用"---DATA---"分隔：

"""

    for i, p in enumerate(prompts, 1):
        e1 = p.get('entity1', {})
        e2 = p.get('entity2', {})
        diff = p.get('difficulty', 'medium')
        len_req = {'easy': '30-50字符', 'medium': '50-100字符', 'hard': '80-150字符'}.get(diff, '50-100字符')

        batch_prompt += f"""【数据{i}】
- 实体1: {e1.get('name')} ({e1.get('type')})，坐标: {e1.get('coords')}
- 实体2: {e2.get('name')} ({e2.get('type')})，坐标: {e2.get('coords')}
- 拓扑子类型: {p.get('topology_subtype')}
- 难度: {diff}
- 要求Question长度: {len_req}

"""

    batch_prompt += """
【输出格式要求】
每条数据使用JSON格式，必须包含以下字段：
{
  "id": "geosr_topological_XXXXX_YYYY",
  "spatial_relation_type": "topological",
  "question": "根据难度生成相应复杂度的问题",
  "answer": "详细答案",
  "reasoning_chain": [5步推理链],
  "entities": [实体列表],
  "spatial_tokens": [空间关键词],
  "difficulty": "easy/medium/hard",
  "topology_subtype": "子类型",
  "difficulty_score": 1.0-5.0,
  "entity_to_token": {"实体名": {"char_start": X, "char_end": Y, "token_indices": [...]}}
}
"""

    # 调用API
    print("\n开始API调用...")
    start_time = time.time()

    client = ZhipuAI(api_key=API_KEY)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": batch_prompt}],
        max_tokens=8192,
        temperature=0.95
    )

    elapsed = time.time() - start_time
    print(f"API调用耗时: {elapsed:.2f} 秒")

    # 解析响应
    if response.choices:
        content = response.choices[0].message.content
        print(f"响应内容长度: {len(content)} 字符")

        # 保存原始响应
        with open('scripts/verify_response.txt', 'w', encoding='utf-8') as f:
            f.write(content)
        print("原始响应已保存到 scripts/verify_response.txt")

        # 解析JSON
        results = []
        parts = content.split("---DATA---")

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # 提取JSON对象
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
                        except:
                            pass
                        json_start = -1

        print(f"\n成功解析 {len(results)} 条数据")

        # 验证字段完整性
        print("\n字段验证:")
        required_fields = ["id", "question", "answer", "reasoning_chain", "entities", "spatial_tokens", "difficulty", "topology_subtype", "difficulty_score", "entity_to_token"]

        for i, r in enumerate(results, 1):
            print(f"\n--- 数据 {i} ---")
            missing = [f for f in required_fields if f not in r]
            if missing:
                print(f"  缺失字段: {missing}")
            else:
                print(f"  ✅ 字段完整")

            q = r.get('question', '')
            print(f"  Question: {q[:50]}...")
            print(f"  Question长度: {len(q)} 字符")

            # 验证reasoning_chain
            chain = r.get('reasoning_chain', [])
            print(f"  Reasoning Chain: {len(chain)} 步")

            # 验证entities
            entities = r.get('entities', [])
            print(f"  Entities: {len(entities)} 个")

            # 显示拓扑子类型和难度
            print(f"  Topology: {r.get('topology_subtype')}, Difficulty: {r.get('difficulty')}")

        return len(results) == 5
    else:
        print("API调用失败")
        return False

if __name__ == "__main__":
    success = verify_batch_generation()
    print(f"\n验证结果: {'✅ 成功' if success else '❌ 失败'}")
