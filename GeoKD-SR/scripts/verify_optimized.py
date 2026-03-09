#!/usr/bin/env python3
"""
优化版验证 - 简洁提示词 + 严格长度控制
"""
import sys
import io
import json
import time
from zhipuai import ZhipuAI

API_KEY = "90fec3d49a8c40babbacecc617b34cf3.i4lMb9sTCUQlHKMw"
MODEL_NAME = "glm-4.7"

if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except:
        pass

# 简洁但完整的提示词模板
def build_prompt(entity1, entity2, topology_subtype, difficulty):
    length_req = {
        'easy': (30, 50),
        'medium': (50, 100),
        'hard': (80, 150)
    }[difficulty]
    min_len, max_len = length_req

    return f"""你是地理空间数据专家。生成一条关于{entity1['name']}和{entity2['name']}的拓扑关系数据。

【严格要求】question字段长度必须在{min_len}-{max_len}字符之间！

【输入信息】
- 实体1: {entity1['name']} ({entity1['type']})，坐标: {entity1['coords']}
- 实体2: {entity2['name']} ({entity2.get('type', 'unknown')})，坐标: {entity2.get('coords', [])}
- 拓扑关系: {topology_subtype}
- 难度: {difficulty}

【输出JSON格式】必须完整输出以下所有字段：
{{
  "question": "长度{min_len}-{max_len}字符的问题",
  "answer": "详细答案",
  "reasoning_chain": ["步骤1", "步骤2", "步骤3", "步骤4", "步骤5"],
  "entities": [{{"name": "实体名", "type": "类型", "coords": [经度, 纬度]}}],
  "difficulty": "{difficulty}",
  "topology_subtype": "{topology_subtype}"
}}

现在请生成数据："""


def verify_optimized():
    print("=" * 70)
    print("优化版验证 - 简洁提示词 + 严格长度")
    print("=" * 70)

    with open('data/prompts/agent_splits/agent1_prompts.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    prompts = data['prompts']

    # 测试不同难度
    test_cases = [
        ([p for p in prompts if p.get('difficulty') == 'easy' and p.get('topology_subtype') == 'overlap'][0], 'easy'),
        ([p for p in prompts if p.get('difficulty') == 'medium' and p.get('topology_subtype') == 'overlap'][0], 'medium'),
        ([p for p in prompts if p.get('difficulty') == 'hard' and p.get('topology_subtype') == 'overlap'][0], 'hard'),
    ]

    client = ZhipuAI(api_key=API_KEY)
    results = []

    for i, (prompt, expected_diff) in enumerate(test_cases, 1):
        print(f"\n--- 测试 {i}: {expected_diff} ---")

        entity1 = prompt.get('entity1', {})
        entity2 = prompt.get('entity2', {})
        topology_subtype = prompt.get('topology_subtype', 'overlap')

        # 构建提示词
        full_prompt = f"""你是地理空间数据专家。生成一条关于{entity1['name']}和{entity2['name']}的拓扑关系数据。

【严格要求】question字段长度必须在{{'easy': '30-50', 'medium': '50-100', 'hard': '80-150'}['{expected_diff}']}字符之间！

【输入信息】
- 实体1: {entity1['name']} ({entity1.get('type', 'unknown')})，坐标: {entity1.get('coords', [])}
- 实体2: {entity2['name']} ({entity2.get('type', 'unknown')})，坐标: {entity2.get('coords', [])}
- 拓扑关系: {topology_subtype}
- 难度: {expected_diff}

【输出JSON格式】必须完整输出以下所有字段：
{{
  "question": "长度符合要求的问题文本",
  "answer": "详细答案",
  "reasoning_chain": ["步骤1", "步骤2", "步骤3", "步骤4", "步骤5"],
  "entities": [{{"name": "{entity1['name']}", "type": "{entity1.get('type', '')}", "coords": {entity1.get('coords', [])]}}, {{"name": "{entity2['name']}", "type": "{entity2.get('type', '')}", "coords": {entity2.get('coords', [])]}}],
  "difficulty": "{expected_diff}",
  "topology_subtype": "{topology_subtype}"
}}

现在请生成数据："""

        print(f"  调用API...")
        start_time = time.time()

        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": full_prompt}],
                max_tokens=2048,
                temperature=0.9
            )

            elapsed = time.time() - start_time
            content = response.choices[0].message.content if response.choices else ""

            print(f"  耗时: {elapsed:.1f}s, 响应: {len(content)}字符")

            # 提取JSON
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                try:
                    result = json.loads(json_str)
                    results.append((result, expected_diff))

                    q = result.get('question', '')
                    length_req = {'easy': (30, 50), 'medium': (50, 100), 'hard': (80, 150)}[expected_diff]
                    length_ok = length_req[0] <= len(q) <= length_req[1]

                    print(f"  Question({len(q)}字符): {q[:40]}...")
                    print(f"  长度要求{length_req[0]}-{length_req[1]}: {'✅' if length_ok else '❌'}")
                    print(f"  字段: {list(result.keys())}")

                except json.JSONDecodeError as e:
                    print(f"  JSON解析失败: {e}")
                    results.append((None, expected_diff))
            else:
                print(f"  未找到JSON")
                results.append((None, expected_diff))

        except Exception as e:
            print(f"  错误: {e}")
            results.append((None, expected_diff))

        time.sleep(2)  # 避免限流

    # 总结
    print("\n" + "=" * 70)
    print("验证总结")
    print("=" * 70)

    success_count = 0
    for result, expected_diff in results:
        if result is None:
            print(f"{expected_diff}: ❌ 生成失败")
            continue

        q = result.get('question', '')
        length_req = {'easy': (30, 50), 'medium': (50, 100), 'hard': (80, 150)}[expected_diff]
        length_ok = length_req[0] <= len(q) <= length_req[1]
        has_chain = len(result.get('reasoning_chain', [])) >= 5
        has_entities = len(result.get('entities', [])) >= 2

        status = "✅" if (length_ok and has_chain and has_entities) else "❌"
        print(f"{expected_diff}: {status} (长度{len(q)}, 链{len(result.get('reasoning_chain', []))}步, 实体{len(result.get('entities', []))}个)")

        if length_ok and has_chain and has_entities:
            success_count += 1

    print(f"\n成功率: {success_count}/{len(test_cases)}")
    return success_count >= 2


if __name__ == "__main__":
    success = verify_optimized()
    print(f"\n最终: {'✅ 通过' if success else '❌ 需优化'}")
