#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
单条数据生成测试脚本
"""

import os
import sys
import json
import re

# 设置API密钥
os.environ['ZHIPUAI_API_KEY'] = '809fc06b8b744d719d870463211f7dd0.0Lc5qs0W20PMzjfW'

# 添加脚本目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'data'))

# 导入生成器模块
from generate_data_glm5 import GLM5Client, EntityDatabase, GeoSRDataGenerator

def test_single_generation():
    """测试生成单条数据"""
    print("=" * 60)
    print("GeoKD-SR 单条数据生成测试")
    print("=" * 60)

    # 1. 初始化组件
    print("\n[1/4] 初始化组件...")

    # 加载实体数据库 (EntityDatabase不接受参数)
    entity_db = EntityDatabase()
    print(f"[OK] 实体数据库: {entity_db.statistics()}")

    # 初始化GLM-5客户端
    client = GLM5Client()
    if not client.api_key:
        print("[错误] API密钥未设置")
        return
    print("[OK] GLM-5客户端初始化成功")

    # 2. 直接测试API调用
    print("\n[2/4] 测试API调用...")

    # 选择两个实体
    entities = entity_db.get_entities_by_type("city")
    if len(entities) < 2:
        print("[错误] 实体数量不足")
        return

    import random
    entity1, entity2 = random.sample(entities, 2)
    print(f"  选择实体: {entity1['name']} 和 {entity2['name']}")

    # 构建简单prompt
    prompt = f"""请生成一个关于"{entity1['name']}"和"{entity2['name']}"之间方向关系的地理问题。

已知信息：
- {entity1['name']}：纬度{entity1['lat']}°N，经度{entity1['lon']}°E
- {entity2['name']}：纬度{entity2['lat']}°N，经度{entity2['lon']}°E

请按照以下JSON格式返回：
{{
  "id": "geosr_001",
  "spatial_relation_type": "directional",
  "question": "问题文本",
  "answer": "答案文本",
  "reasoning_chain": [
    {{"step": 1, "name": "entity_identification", "content": "识别实体..."}},
    {{"step": 2, "name": "spatial_relation", "content": "识别关系..."}},
    {{"step": 3, "name": "coordinate_retrieval", "content": "获取坐标..."}},
    {{"step": 4, "name": "calculation", "content": "计算方向..."}},
    {{"step": 5, "name": "answer_generation", "content": "生成答案..."}}
  ],
  "entities": [
    {{"name": "{entity1['name']}", "type": "city", "coords": [{entity1['lon']}, {entity1['lat']}]}}
  ],
  "difficulty": "easy"
}}

请只返回JSON，不要添加任何其他文本。"""

    # 调用API
    print("  调用GLM-5 API...")
    response = client.generate(prompt)

    if response:
        print("[OK] API调用成功")
        print("\n原始响应:")
        print("-" * 40)
        print(response[:500] + "..." if len(response) > 500 else response)

        # 尝试解析JSON
        print("\n[3/4] 解析JSON...")

        # 提取JSON内容
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 尝试直接提取
            json_start = response.find('{')
            json_end = response.rfind('}')
            if json_start != -1 and json_end != -1:
                json_str = response[json_start:json_end+1]
            else:
                json_str = response

        try:
            record = json.loads(json_str)
            print("[OK] JSON解析成功!")

            print("\n生成结果:")
            print("-" * 40)
            print(f"ID: {record.get('id', 'N/A')}")
            print(f"类型: {record.get('spatial_relation_type', 'N/A')}")
            print(f"问题: {record.get('question', 'N/A')}")
            print(f"答案: {record.get('answer', 'N/A')}")
            print(f"难度: {record.get('difficulty', 'N/A')}")
            print(f"推理链长度: {len(record.get('reasoning_chain', []))}")

            # 保存到文件
            output_path = os.path.join(os.path.dirname(__file__), 'data', 'geosr_chain', 'test_single.json')
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
            print(f"\n[OK] 数据已保存到: {output_path}")

        except json.JSONDecodeError as e:
            print(f"[警告] JSON解析失败: {e}")
            print("尝试修复JSON...")

            # 保存原始响应
            raw_path = os.path.join(os.path.dirname(__file__), 'data', 'geosr_chain', 'test_raw_response.txt')
            with open(raw_path, 'w', encoding='utf-8') as f:
                f.write(response)
            print(f"原始响应已保存到: {raw_path}")
    else:
        print("[错误] API调用失败")

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)

if __name__ == "__main__":
    test_single_generation()
