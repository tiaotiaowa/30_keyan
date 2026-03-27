#!/usr/bin/env python3
"""
增强版批量生成验证 - 测试多种难度和长度要求
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

# 长度要求
LENGTH_REQUIREMENTS = {
    'easy': (30, 50),
    'medium': (50, 100),
    'hard': (80, 150)
}

SYSTEM_PROMPT = """你是一位资深的地理空间数据集设计专家，拥有以下专业能力：
1. 精通中国地理知识，包括省市区划、山川河流、地标建筑等
2. 擅长设计多层次、多维度的地理空间推理问题
3. 能够根据不同难度级别设计相应复杂度的地理问题
4. 熟悉拓扑关系（包含、相邻、重叠、相离等）的空间推理
"""

STRICT_LENGTH_PROMPT = """
【严格长度要求】
请务必确保Question字段长度符合以下要求，这是最重要的质量指标！
- Easy难度：Question长度必须在30-50字符之间
- Medium难度：Question长度必须在50-100字符之间
- Hard难度：Question长度必须在80-150字符之间

如果Question长度不足，请添加适当的背景描述、实体类型信息或地理上下文来达到要求长度。

【增加长度的方法】
1. 添加实体类型描述："已知地理实体大巴山脉（mountain类型）..."
2. 添加地理背景："海河是华北地区的著名水系，最终注入渤海..."
3. 添加位置描述："满洲里是位于中国北边境的口岸城市..."
4. 使用更完整的问句结构
"""

def verify_enhanced():
    print("=" * 70)
    print("增强版批量生成验证 - 测试多种难度级别")
    print("=" * 70)

    # 加载提示词
    with open('data/prompts/agent_splits/agent1_prompts.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    prompts = data['prompts']

    # 按难度分组，每组选2条
    easy_prompts = [p for p in prompts if p.get('difficulty') == 'easy'][:2]
    medium_prompts = [p for p in prompts if p.get('difficulty') == 'medium'][:2]
    hard_prompts = [p for p in prompts if p.get('difficulty') == 'hard'][:2]

    test_prompts = easy_prompts + medium_prompts + hard_prompts
    print(f"选择测试提示词: easy={len(easy_prompts)}, medium={len(medium_prompts)}, hard={len(hard_prompts)}")

    # 构建增强版提示词
    batch_prompt = f"""{SYSTEM_PROMPT}

{STRICT_LENGTH_PROMPT}

请按照以下要求生成6条地理空间推理数据，每条数据之间用"---DATA---"分隔：

"""

    for i, p in enumerate(test_prompts, 1):
        e1 = p.get('entity1', {})
        e2 = p.get('entity2', {})
        diff = p.get('difficulty', 'medium')
        min_len, max_len = LENGTH_REQUIREMENTS[diff]

        batch_prompt += f"""【数据{i}】
- 实体1: {e1.get('name')} ({e1.get('type')})，坐标: {e1.get('coords')}
- 实体2: {e2.get('name')} ({e2.get('type')})，坐标: {e2.get('coords')}
- 拓扑子类型: {p.get('topology_subtype')}
- 难度: {diff}
- ⚠️ Question长度要求: {min_len}-{max_len}字符 (必须严格遵守!)

"""

    batch_prompt += """
【输出格式】
每条数据使用JSON格式，必须包含以下字段：
{
  "id": "geosr_topological_XXXXX_YYYY",
  "question": "⚠️ 严格按难度要求长度！",
  "answer": "详细答案",
  "reasoning_chain": [5步推理链],
  "entities": [实体列表],
  "spatial_tokens": [空间关键词],
  "difficulty": "easy/medium/hard",
  "topology_subtype": "子类型",
  "difficulty_score": 1.0-5.0,
  "entity_to_token": {...}
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
    if not response.choices:
        print("API调用失败")
        return False

    content = response.choices[0].message.content
    print(f"响应内容长度: {len(content)} 字符")

    # 保存原始响应
    with open('scripts/verify_enhanced_response.txt', 'w', encoding='utf-8') as f:
        f.write(content)

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

    # 详细验证
    print("\n" + "=" * 70)
    print("质量验证报告")
    print("=" * 70)

    required_fields = ["id", "question", "answer", "reasoning_chain", "entities",
                       "spatial_tokens", "difficulty", "topology_subtype",
                       "difficulty_score", "entity_to_token"]

    length_ok_count = 0
    field_ok_count = 0
    chain_ok_count = 0

    for i, r in enumerate(results, 1):
        expected_diff = test_prompts[i-1]['difficulty'] if i <= len(test_prompts) else 'unknown'
        min_len, max_len = LENGTH_REQUIREMENTS.get(expected_diff, (30, 150))

        print(f"\n--- 数据 {i} ({expected_diff}) ---")

        # 字段验证
        missing = [f for f in required_fields if f not in r]
        if missing:
            print(f"  ❌ 缺失字段: {missing}")
        else:
            print(f"  ✅ 字段完整")
            field_ok_count += 1

        # Question长度验证
        q = r.get('question', '')
        q_len = len(q)
        length_ok = min_len <= q_len <= max_len

        print(f"  Question: {q[:60]}{'...' if len(q) > 60 else ''}")
        print(f"  长度: {q_len}字符, 要求: {min_len}-{max_len} → {'✅ 符合' if length_ok else '❌ 不符合'}")

        if length_ok:
            length_ok_count += 1

        # Reasoning Chain验证
        chain = r.get('reasoning_chain', [])
        chain_ok = len(chain) >= 5
        print(f"  Reasoning Chain: {len(chain)}步 → {'✅' if chain_ok else '❌'}")
        if chain_ok:
            chain_ok_count += 1

        # 实体验证
        entities = r.get('entities', [])
        print(f"  Entities: {len(entities)}个")

        # 其他字段
        print(f"  Topology: {r.get('topology_subtype')}, Score: {r.get('difficulty_score')}")

    # 总结
    print("\n" + "=" * 70)
    print("验证总结")
    print("=" * 70)
    print(f"总生成数: {len(results)}/{len(test_prompts)}")
    print(f"字段完整: {field_ok_count}/{len(results)}")
    print(f"长度符合: {length_ok_count}/{len(results)}")
    print(f"推理链完整: {chain_ok_count}/{len(results)}")

    # 按难度统计长度
    print("\n长度分布统计:")
    for diff in ['easy', 'medium', 'hard']:
        diff_results = [r for r in results if r.get('difficulty') == diff]
        if diff_results:
            lengths = [len(r.get('question', '')) for r in diff_results]
            avg_len = sum(lengths) / len(lengths)
            min_len, max_len = LENGTH_REQUIREMENTS[diff]
            ok_count = sum(1 for l in lengths if min_len <= l <= max_len)
            print(f"  {diff}: 平均{avg_len:.1f}字符, 范围{min(lengths)}-{max(lengths)}, 符合率{ok_count}/{len(lengths)}")

    return length_ok_count >= 4 and field_ok_count >= 5

if __name__ == "__main__":
    success = verify_enhanced()
    print(f"\n最终结果: {'✅ 验证通过' if success else '❌ 需要改进提示词'}")
