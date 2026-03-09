#!/usr/bin/env python3
"""
测试批量生成功能 - 验证脚本可执行性
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

def test_batch_generation():
    print("=" * 60)
    print("测试批量生成功能 - 5条数据")
    print("=" * 60)

    # 加载提示词
    with open('data/prompts/agent_splits/agent1_prompts.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    prompts = data['prompts'][:5]
    print(f"加载 {len(prompts)} 条提示词")

    # 构建提示词
    batch_prompt = """你是一位地理空间数据专家，请生成5条拓扑关系推理数据。

"""

    for i, p in enumerate(prompts, 1):
        e1 = p.get('entity1', {})
        e2 = p.get('entity2', {})
        batch_prompt += f"""【数据{i}】
- 实体1: {e1.get('name')} ({e1.get('type')})
- 实体2: {e2.get('name')} ({e2.get('type')})
- 拓扑类型: {p.get('topology_subtype')}
- 难度: {p.get('difficulty')}

"""

    batch_prompt += """
请用JSON格式输出5条数据，每条用---DATA---分隔，包含字段：question, answer, reasoning_chain(5步), entities, difficulty, topology_subtype
"""

    # 调用API
    print("调用API...")
    start = time.time()

    client = ZhipuAI(api_key=API_KEY)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": batch_prompt}],
        max_tokens=8192,
        temperature=0.95
    )

    elapsed = time.time() - start
    print(f"耗时: {elapsed:.1f}秒")

    content = response.choices[0].message.content if response.choices else ""
    print(f"响应: {len(content)}字符")

    # 解析JSON
    results = []
    for part in content.split("---DATA---"):
        part = part.strip()
        if not part:
            continue
        json_start = part.find('{')
        json_end = part.rfind('}') + 1
        if json_start >= 0:
            try:
                results.append(json.loads(part[json_start:json_end]))
            except:
                pass

    print(f"\n解析成功: {len(results)}条")

    # 验证
    for i, r in enumerate(results, 1):
        q = r.get('question', '')[:40]
        chain = len(r.get('reasoning_chain', []))
        entities = len(r.get('entities', []))
        print(f"  {i}. {q}... (链:{chain}步, 实体:{entities}个)")

    return len(results) >= 4

if __name__ == "__main__":
    success = test_batch_generation()
    print(f"\n结果: {'✅ 可执行' if success else '❌ 需检查'}")
