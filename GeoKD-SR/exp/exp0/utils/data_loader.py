# -*- coding: utf-8 -*-
"""
数据加载工具模块
"""

import json
from pathlib import Path
from typing import List, Dict, Optional


def load_test_data(test_file: str, max_samples: Optional[int] = None) -> List[Dict]:
    """
    加载测试数据

    Args:
        test_file: 测试文件路径
        max_samples: 最大样本数，None表示加载全部

    Returns:
        数据列表
    """
    data = []
    test_path = Path(test_file)

    if not test_path.exists():
        raise FileNotFoundError(f"测试文件不存在: {test_file}")

    with open(test_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue

            # 支持JSONL格式
            if line.strip().startswith('{'):
                item = json.loads(line.strip())
            else:
                # 支持eval格式（不安全但兼容旧数据）
                try:
                    item = eval(line.strip())
                except:
                    continue

            data.append(item)

            if max_samples and len(data) >= max_samples:
                break

    return data


def load_train_data(train_file: str, max_samples: Optional[int] = None) -> List[Dict]:
    """
    加载训练数据

    Args:
        train_file: 训练文件路径
        max_samples: 最大样本数，None表示加载全部

    Returns:
        数据列表
    """
    return load_test_data(train_file, max_samples)


def load_dev_data(dev_file: str, max_samples: Optional[int] = None) -> List[Dict]:
    """
    加载开发集数据

    Args:
        dev_file: 开发集文件路径
        max_samples: 最大样本数，None表示加载全部

    Returns:
        数据列表
    """
    return load_test_data(dev_file, max_samples)


def validate_data_format(data: List[Dict]) -> bool:
    """
    验证数据格式

    Args:
        data: 数据列表

    Returns:
        是否格式正确
    """
    if not data:
        return False

    required_fields = ['id', 'question', 'answer']

    for item in data[:10]:  # 检查前10条
        for field in required_fields:
            if field not in item:
                return False

    return True


def get_spatial_relation_types(data: List[Dict]) -> List[str]:
    """
    获取数据中的空间关系类型

    Args:
        data: 数据列表

    Returns:
        空间关系类型列表
    """
    types = set()
    for item in data:
        if 'spatial_relation_type' in item:
            types.add(item['spatial_relation_type'])
        elif 'relation_type' in item:
            types.add(item['relation_type'])

    return sorted(list(types))


def get_difficulty_levels(data: List[Dict]) -> List[str]:
    """
    获取数据中的难度等级

    Args:
        data: 数据列表

    Returns:
        难度等级列表
    """
    levels = set()
    for item in data:
        if 'difficulty' in item:
            levels.add(item['difficulty'])

    return sorted(list(levels))
