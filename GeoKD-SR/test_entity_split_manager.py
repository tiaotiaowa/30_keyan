# -*- coding: utf-8 -*-
"""
实体分离管理器测试脚本
"""

import sys
import json

# 添加项目路径
sys.path.insert(0, 'D:/30_keyan/GeoKD-SR')

from utils.entity_split_manager import EntitySplitManager


def test_basic_functionality():
    """测试基本功能"""
    print("=" * 60)
    print("测试实体分离管理器基本功能")
    print("=" * 60)

    # 创建测试实体数据
    test_entities = [
        {"name": "北京市", "type": "city"},
        {"name": "上海市", "type": "city"},
        {"name": "广东省", "type": "province"},
        {"name": "浙江省", "type": "province"},
        {"name": "广州市", "type": "city"},
        {"name": "深圳市", "type": "city"},
        {"name": "杭州市", "type": "city"},
        {"name": "南京市", "type": "city"},
        {"name": "江苏省", "type": "province"},
        {"name": "四川省", "type": "province"},
    ]

    # 创建管理器
    manager = EntitySplitManager(test_entities, seed=42)

    # 测试获取实体
    print("\n1. 获取各数据集实体:")
    for split in ["train", "dev", "test"]:
        entities = manager.get_entities(split)
        print(f"   {split}: {[e['name'] for e in entities]}")

    # 测试实体归属检查
    print("\n2. 检查实体归属:")
    test_cases = [
        ("北京市", "train"),
        ("上海市", "dev"),
        ("广东省", "test"),
    ]
    for entity_name, expected_split in test_cases:
        actual_split = manager.get_entity_split(entity_name)
        print(f"   {entity_name}: {actual_split}")

    # 打印统计信息
    print("\n3. 统计信息:")
    manager.print_statistics()

    # 验证无泄露
    print("\n4. 验证数据泄露:")
    manager.validate_no_leakage()

    # 测试导出映射
    print("\n5. 导出实体映射:")
    mapping = manager.export_split_mapping()
    print(f"   {json.dumps(mapping, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    test_basic_functionality()
