# -*- coding: utf-8 -*-
"""
实体分离管理器
管理训练/验证/测试集的实体分离，防止数据泄露

主要功能:
- 按固定比例分割实体（70%/15%/15%）
- 按实体类型（省份、城市等）分层分配
- 使用固定随机种子确保可复现
- 提供实体归属查询和统计功能
"""

import random
from typing import Dict, List, Optional, Set
from collections import defaultdict


class EntitySplitManager:
    """
    管理训练/验证/测试集的实体分离，防止数据泄露

    使用分层抽样确保各类型实体在各数据集中均匀分布。
    使用固定随机种子确保分割结果可复现。
    """

    # 数据集分割比例 (调整以支持3000条测试数据无重复)
    # test需要约120+实体，C(120,2)=7140对，确保3000条完全不重复
    SPLIT_RATIOS = {
        "train": 0.60,
        "dev": 0.15,
        "test": 0.25
    }

    # 实体类型字段名
    ENTITY_TYPE_FIELD = "type"

    def __init__(self, entities: List[Dict], seed: int = 42):
        """
        初始化实体分离管理器

        Args:
            entities: 实体列表，每个实体是包含 'name' 和 'type' 等字段的字典
            seed: 随机种子，确保结果可复现
        """
        self.seed = seed
        self._original_entities = entities

        # 按类型分组实体
        entities_by_type = self._group_entities_by_type(entities)

        # 对每个类型进行分层分割
        self._train_entities: List[Dict] = []
        self._dev_entities: List[Dict] = []
        self._test_entities: List[Dict] = []

        self._train_entity_names: Set[str] = set()
        self._dev_entity_names: Set[str] = set()
        self._test_entity_names: Set[str] = set()

        self._split_entities_by_type(entities_by_type)

        # 构建实体名称索引，加速查询
        self._build_name_index()

        # 计算统计信息
        self._statistics = self._calculate_statistics()

    def _group_entities_by_type(self, entities: List[Dict]) -> Dict[str, List[Dict]]:
        """
        按类型分组实体

        Args:
            entities: 实体列表

        Returns:
            按类型分组的实体字典
        """
        grouped = defaultdict(list)
        for entity in entities:
            entity_type = entity.get(self.ENTITY_TYPE_FIELD, "unknown")
            grouped[entity_type].append(entity)
        return dict(grouped)

    def _split_entities_by_type(self, entities_by_type: Dict[str, List[Dict]]) -> None:
        """
        对每个类型的实体按比例分割到各数据集

        Args:
            entities_by_type: 按类型分组的实体字典
        """
        random.seed(self.seed)

        for entity_type, type_entities in entities_by_type.items():
            # 随机打乱同类型实体
            shuffled = type_entities.copy()
            random.shuffle(shuffled)

            # 计算分割点
            total = len(shuffled)
            train_end = int(total * self.SPLIT_RATIOS["train"])
            dev_end = train_end + int(total * self.SPLIT_RATIOS["dev"])

            # 分割实体
            train_list = shuffled[:train_end]
            dev_list = shuffled[train_end:dev_end]
            test_list = shuffled[dev_end:]

            # 添加到对应数据集
            self._train_entities.extend(train_list)
            self._dev_entities.extend(dev_list)
            self._test_entities.extend(test_list)

    def _build_name_index(self) -> None:
        """
        构建实体名称到数据集的映射索引，加速查询
        """
        self._train_entity_names = {e.get("name", "") for e in self._train_entities}
        self._dev_entity_names = {e.get("name", "") for e in self._dev_entities}
        self._test_entity_names = {e.get("name", "") for e in self._test_entities}

    def _calculate_statistics(self) -> Dict:
        """
        计算各数据集的统计信息

        Returns:
            包含详细统计信息的字典
        """
        stats = {
            "total_entities": len(self._original_entities),
            "train": {
                "count": len(self._train_entities),
                "ratio": len(self._train_entities) / len(self._original_entities) if self._original_entities else 0
            },
            "dev": {
                "count": len(self._dev_entities),
                "ratio": len(self._dev_entities) / len(self._original_entities) if self._original_entities else 0
            },
            "test": {
                "count": len(self._test_entities),
                "ratio": len(self._test_entities) / len(self._original_entities) if self._original_entities else 0
            },
            "by_type": self._calculate_type_statistics()
        }
        return stats

    def _calculate_type_statistics(self) -> Dict[str, Dict[str, int]]:
        """
        计算各类型在各数据集中的分布

        Returns:
            按类型分组的统计信息
        """
        type_stats = defaultdict(lambda: {"train": 0, "dev": 0, "test": 0})

        for entity in self._train_entities:
            entity_type = entity.get(self.ENTITY_TYPE_FIELD, "unknown")
            type_stats[entity_type]["train"] += 1

        for entity in self._dev_entities:
            entity_type = entity.get(self.ENTITY_TYPE_FIELD, "unknown")
            type_stats[entity_type]["dev"] += 1

        for entity in self._test_entities:
            entity_type = entity.get(self.ENTITY_TYPE_FIELD, "unknown")
            type_stats[entity_type]["test"] += 1

        return dict(type_stats)

    def get_entities(self, split: str) -> List[Dict]:
        """
        获取特定数据集的实体列表

        Args:
            split: 数据集名称，可选值为 "train", "dev", "test"

        Returns:
            该数据集包含的实体列表

        Raises:
            ValueError: 当 split 参数无效时
        """
        if split == "train":
            return self._train_entities.copy()
        elif split == "dev":
            return self._dev_entities.copy()
        elif split == "test":
            return self._test_entities.copy()
        else:
            raise ValueError(f"Invalid split: {split}. Must be 'train', 'dev', or 'test'.")

    def is_entity_in_split(self, entity_name: str, split: str) -> bool:
        """
        检查实体是否属于指定数据集

        Args:
            entity_name: 实体名称
            split: 数据集名称，可选值为 "train", "dev", "test"

        Returns:
            如果实体属于该数据集返回 True，否则返回 False

        Raises:
            ValueError: 当 split 参数无效时
        """
        if split == "train":
            return entity_name in self._train_entity_names
        elif split == "dev":
            return entity_name in self._dev_entity_names
        elif split == "test":
            return entity_name in self._test_entity_names
        else:
            raise ValueError(f"Invalid split: {split}. Must be 'train', 'dev', or 'test'.")

    def get_entity_split(self, entity_name: str) -> Optional[str]:
        """
        查询实体所属的数据集

        Args:
            entity_name: 实体名称

        Returns:
            数据集名称（"train", "dev", "test"），如果实体不存在返回 None
        """
        if entity_name in self._train_entity_names:
            return "train"
        elif entity_name in self._dev_entity_names:
            return "dev"
        elif entity_name in self._test_entity_names:
            return "test"
        return None

    def statistics(self) -> Dict:
        """
        返回各数据集的实体统计信息

        Returns:
            包含统计信息的字典，包括:
            - total_entities: 总实体数
            - train/dev/test: 各数据集的实体数和比例
            - by_type: 各类型在各数据集中的分布
        """
        return self._statistics.copy()

    def print_statistics(self) -> None:
        """打印格式化的统计信息"""
        stats = self.statistics()

        print("=" * 60)
        print("实体分离统计信息")
        print("=" * 60)
        print(f"总实体数: {stats['total_entities']}")
        print()

        for split_name in ["train", "dev", "test"]:
            split_stats = stats[split_name]
            print(f"{split_name.upper()}集:")
            print(f"  实体数: {split_stats['count']}")
            print(f"  比例: {split_stats['ratio']:.2%}")
        print()

        print("按类型分布:")
        for entity_type, type_counts in stats["by_type"].items():
            total = sum(type_counts.values())
            print(f"  {entity_type}:")
            print(f"    总计: {total}")
            print(f"    train={type_counts['train']}, "
                  f"dev={type_counts['dev']}, "
                  f"test={type_counts['test']}")
        print("=" * 60)

    def validate_no_leakage(self) -> bool:
        """
        验证各数据集之间没有实体泄露

        Returns:
            如果没有实体泄露返回 True，否则返回 False
        """
        # 检查各数据集之间是否有重叠
        train_dev = self._train_entity_names & self._dev_entity_names
        train_test = self._train_entity_names & self._test_entity_names
        dev_test = self._dev_entity_names & self._test_entity_names

        if train_dev or train_test or dev_test:
            print("警告：检测到实体泄露！")
            if train_dev:
                print(f"  train/dev 重叠实体: {train_dev}")
            if train_test:
                print(f"  train/test 重叠实体: {train_test}")
            if dev_test:
                print(f"  dev/test 重叠实体: {dev_test}")
            return False

        print("验证通过：各数据集之间无实体泄露")
        return True

    def export_split_mapping(self) -> Dict[str, str]:
        """
        导出实体到数据集的映射

        Returns:
            实体名称到数据集名称的映射字典
        """
        mapping = {}
        for entity in self._original_entities:
            entity_name = entity.get("name", "")
            split = self.get_entity_split(entity_name)
            if split:
                mapping[entity_name] = split
        return mapping
