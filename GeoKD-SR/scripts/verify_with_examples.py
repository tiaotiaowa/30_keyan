#!/usr/bin/env python3
"""
严格长度验证 - 使用示例引导模型生成符合长度要求的Question
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

# 长度要求和示例
LENGTH_EXAMPLES = {
    'easy': {
        'requirement': (30, 50),
        'examples': [
            "集安市与上海市在行政区划上是否存在包含关系？",  # 24字符 - 太短，需要加长
            "已知集安市是吉林省下辖的县级市，上海市是直辖市，请判断两者是否存在行政区划上的包含关系？",  # 46字符 ✅
            "请从行政区划角度分析，武汉市与湖北省之间是否存在包含关系？",  # 31字符 ✅
        ]
    },
    'medium': {
        'requirement': (50, 100),
        'examples': [
            "已知地理实体大巴山脉（mountain类型）和云冈石窟（landmark类型），请判断这两个实体之间的拓扑关系，并回答云冈石窟是否位于大巴山脉内部？",  # 78字符 ✅
            "北京市是中国的首都，位于华北平原北部；江苏省地处华东沿海地区。请分析这两个省级行政区在地理位置上的拓扑关系类型。",  # 68字符 ✅
            "考虑珠江三角洲的城市分布，佛山市作为广东省的重要制造业城市，与广州市在地理空间上存在怎样的拓扑邻接关系？",  # 62字符 ✅
        ]
    },
    'hard': {
        'requirement': (80, 150),
        'examples': [
            "海河是华北地区的著名水系，最终注入渤海；满洲里是位于中国北边境的口岸城市。从地理空间拓扑的角度来看，海河与满洲里之间存在怎样的空间关系？",  # 82字符 ✅
            "长江是中国第一大河，发源于青藏高原，流经多个省份后注入东海；洞庭湖位于湖南省境内，是中国第二大淡水湖。请结合两者的地理位置和空间范围，分析它们之间的拓扑关系。",  # 96字符 ✅
            "四川省位于中国西南腹地，地形复杂多样，包含川西高原和四川盆地；峨眉山作为佛教名山，位于四川省乐山市境内。请从行政区划和地理空间两个维度，详细分析四川省与峨眉山之间的拓扑包含关系。",  # 107字符 ✅
        ]
    }
}

def verify_with_examples():
    print("=" * 70)
    print("严格长度验证 - 使用示例引导")
    print("=" * 70)

    # 加载提示词
    with open('data/prompts/agent_splits/agent1_prompts.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    prompts = data['prompts']

    # 按难度分组，每组选2条
    easy_prompts = [p for p in prompts if p.get('difficulty') == 'easy'][:2]
    medium_prompts = [p for p in prompts if p.get('difficulty') == 'medium'][:2]
    hard_prompts = [p for p in prompts if p.get('difficulty') == 'hard'][:1]  # 只测试1条hard节省时间

    test_prompts = easy_prompts + medium_prompts + hard_prompts
    print(f"测试提示词: easy={len(easy_prompts)}, medium={len(medium_prompts)}, hard={len(hard_prompts)}")

    # 构建带示例的提示词
    batch_prompt = """你是一位资深的地理空间数据集设计专家。

【最重要要求】Question字段长度必须严格遵守以下要求！

"""

    # 添加各难度的示例
    for diff in ['easy', 'medium', 'hard']:
        ex = LENGTH_EXAMPLES[diff]
        min_len, max_len = ex['requirement']
        batch_prompt += f"""
【{diff.upper()}难度示例】(Question长度必须{min_len}-{max_len}字符)
"""
        for i, example in enumerate(ex['examples'], 1):
            batch_prompt += f"  示例{i}({len(example)}字符): {example}\n"

    batch_prompt += """

请按照以下要求生成5条地理空间推理数据，每条数据之间用"---DATA---"分隔：

"""

    for i, p in enumerate(test_prompts, 1):
        e1 = p.get('entity1', {})
        e2 = p.get('entity2', {})
        diff = p.get('difficulty', 'medium')
        min_len, max_len = LENGTH_EXAMPLES[diff]['requirement']

        batch_prompt += f"""【数据{i}】
- 实体1: {e1.get('name')} ({e1.get('type')})，坐标: {e1.get('coords')}
- 实体2: {e2.get('name')} ({e2.get('type')})，坐标: {e2.get('coords')}
- 拓扑子类型: {p.get('topology_subtype')}
- 难度: {diff}
- ⚠️ Question长度必须在{min_len}-{max_len}字符之间！参考上面同难度的示例！

"""

    batch_prompt += """
【输出格式】JSON格式，包含所有必需字段。Question长度是首要验证标准！
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

    if not response.choices:
        print("API调用失败")
        return False

    content = response.choices[0].message.content
    print(f"响应内容长度: {len(content)} 字符")

    # 保存原始响应
    with open('scripts/verify_examples_response.txt', 'w', encoding='utf-8') as f:
        f.write(content)

    # 解析JSON
    results = []
    parts = content.split("---DATA---")

    for part in parts:
        part = part.strip()
        if not part:
            continue
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

    # 验证
    print("\n" + "=" * 70)
    print("验证报告")
    print("=" * 70)

    length_ok_count = 0
    field_ok_count = 0

    for i, r in enumerate(results, 1):
        if i > len(test_prompts):
            break
        expected_diff = test_prompts[i-1]['difficulty']
        min_len, max_len = LENGTH_EXAMPLES[expected_diff]['requirement']

        print(f"\n--- 数据 {i} ({expected_diff}) ---")

        # 字段验证
        required_fields = ["question", "answer", "reasoning_chain", "entities"]
        missing = [f for f in required_fields if f not in r]
        if not missing:
            print(f"  ✅ 字段完整")
            field_ok_count += 1
        else:
            print(f"  ❌ 缺失: {missing}")

        # 长度验证
        q = r.get('question', '')
        q_len = len(q)
        length_ok = min_len <= q_len <= max_len

        print(f"  Question({q_len}字符): {q[:50]}{'...' if len(q) > 50 else ''}")
        print(f"  要求: {min_len}-{max_len} → {'✅ 符合' if length_ok else '❌ 不符合'}")

        if length_ok:
            length_ok_count += 1

        print(f"  Reasoning Chain: {len(r.get('reasoning_chain', []))}步")

    # 总结
    print("\n" + "=" * 70)
    print(f"总结: 生成{len(results)}条, 字段完整{field_ok_count}/{len(results)}, 长度符合{length_ok_count}/{len(results)}")

    # 按难度统计
    for diff in ['easy', 'medium', 'hard']:
        diff_results = [r for r in results if r.get('difficulty') == diff]
        if diff_results:
            lengths = [len(r.get('question', '')) for r in diff_results]
            min_len, max_len = LENGTH_EXAMPLES[diff]['requirement']
            ok_count = sum(1 for l in lengths if min_len <= l <= max_len)
            print(f"  {diff}: 平均{sum(lengths)/len(lengths):.1f}字符, 符合率{ok_count}/{len(lengths)}")

    return length_ok_count >= 3

if __name__ == "__main__":
    success = verify_with_examples()
    print(f"\n最终结果: {'✅ 通过' if success else '❌ 需进一步优化'}")
