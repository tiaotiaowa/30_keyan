#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
直接调用generate_data_glm5.py生成1条测试数据
"""

import os
import sys
import json

# 设置API密钥
os.environ['ZHIPUAI_API_KEY'] = '809fc06b8b744d719d870463211f7dd0.0Lc5qs0W20PMzjfW'

# 设置工作目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 添加脚本目录到路径
sys.path.insert(0, 'scripts')
sys.path.insert(0, 'data')

print("=" * 60)
print("GeoKD-SR 单条数据生成测试")
print("=" * 60)

try:
    from generate_data_glm5 import GLM5Client, EntityDatabase, GeoSRDataGenerator

    print("\n[1/4] 初始化组件...")

    # 初始化实体数据库
    entity_db = EntityDatabase()
    stats = entity_db.statistics()
    print(f"[OK] 实体数据库: {stats}")

    # 初始化GLM-5客户端
    client = GLM5Client()
    print(f"[OK] GLM-5客户端初始化成功")

    # 初始化生成器
    generator = GeoSRDataGenerator(client, entity_db)
    print(f"[OK] 数据生成器初始化成功")

    print("\n[2/4] 生成单条测试数据...")

    # 生成一条方向关系数据（最简单的类型）
    print("  尝试生成方向关系数据...")
    record = generator.generate_single_record(relation_type="directional", difficulty="easy")

    if record:
        print("[OK] 数据生成成功!")
        print("\n生成结果:")
        print("-" * 40)
        print(f"ID: {record.get('id', 'N/A')}")
        print(f"类型: {record.get('spatial_relation_type', 'N/A')}")
        if 'question' in record:
            print(f"问题: {record['question'][:100]}...")
        if 'answer' in record:
            print(f"答案: {record['answer'][:100]}...")
        print(f"难度: {record.get('difficulty', 'N/A')}")
        if 'reasoning_chain' in record:
            print(f"推理链长度: {len(record['reasoning_chain'])}")

        # 保存到文件
        output_path = os.path.join('data', 'geosr_chain', 'test_single.json')
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        print(f"\n[OK] 数据已保存到: {output_path}")
    else:
        print("[错误] 数据生成失败")
        print("可能原因：API调用失败或数据验证未通过")

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)

except Exception as e:
    print(f"\n[错误] {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
