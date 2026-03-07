"""
渐进式数据加载器 (Progressive Data Loader)

与PyTorch DataLoader兼容的数据加载器，支持渐进式数据调度。
"""

from typing import Any, Dict, Iterator, List, Optional

import torch
from torch.utils.data import Dataset, Sampler


class ProgressiveDataset(Dataset):
    """
    渐进式数据集

    包装数据列表，提供Dataset接口。
    """

    def __init__(self, data: List[Dict]):
        """
        初始化数据集

        Args:
            data: 数据列表
        """
        self.data = data

    def __len__(self) -> int:
        """返回数据集大小"""
        return len(self.data)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        """
        获取单个数据项

        Args:
            idx: 索引

        Returns:
            数据项字典
        """
        return self.data[idx]


class ProgressiveSampler(Sampler):
    """
    渐进式采样器

    支持按关系类型权重进行采样。
    """

    def __init__(
        self,
        data: List[Dict],
        relation_weights: Optional[Dict[str, float]] = None,
        shuffle: bool = True
    ):
        """
        初始化采样器

        Args:
            data: 数据列表
            relation_weights: 关系类型权重
            shuffle: 是否打乱顺序
        """
        self.data = data
        self.relation_weights = relation_weights or {}
        self.shuffle = shuffle

        # 按关系类型分组索引
        self.indices_by_relation = self._group_indices()

    def _group_indices(self) -> Dict[str, List[int]]:
        """按关系类型分组索引"""
        grouped = {}

        for idx, item in enumerate(self.data):
            rel_type = item.get('relation_type', 'unknown')
            if rel_type not in grouped:
                grouped[rel_type] = []
            grouped[rel_type].append(idx)

        return grouped

    def __iter__(self) -> Iterator[int]:
        """生成采样索引"""
        if not self.relation_weights:
            # 无权重时简单顺序或打乱
            indices = list(range(len(self.data)))
            if self.shuffle:
                import random
                random.shuffle(indices)
            yield from indices
        else:
            # 按权重采样
            import random

            active_relations = [
                rel for rel in self.relation_weights.keys()
                if rel in self.indices_by_relation
            ]

            if not active_relations:
                yield from range(len(self.data))
                return

            # 计算每个关系类型应该采样的数量
            weights = [self.relation_weights[rel] for rel in active_relations]
            total_weight = sum(weights)
            if total_weight == 0:
                yield from range(len(self.data))
                return

            # 归一化
            weights = [w / total_weight for w in weights]

            # 计算每个关系类型的采样数
            total_samples = len(self.data)
            relation_samples = {
                rel: max(1, int(total_samples * weight))
                for rel, weight in zip(active_relations, weights)
            }

            # 采样
            for rel, count in relation_samples.items():
                indices = self.indices_by_relation.get(rel, [])
                if indices:
                    sampled = random.choices(indices, k=min(count, len(indices)))
                    yield from sampled

    def __len__(self) -> int:
        """返回采样器长度"""
        return len(self.data)


class ProgressiveDataLoader:
    """
    渐进式数据加载器

    与PyTorch DataLoader兼容的接口，支持批量数据加载。
    """

    def __init__(
        self,
        data: List[Dict],
        batch_size: int = 8,
        shuffle: bool = True,
        drop_last: bool = False,
        relation_weights: Optional[Dict[str, float]] = None
    ):
        """
        初始化数据加载器

        Args:
            data: 数据列表
            batch_size: 批次大小
            shuffle: 是否打乱数据
            drop_last: 是否丢弃最后不完整的批次
            relation_weights: 关系类型权重（用于采样）
        """
        self.data = data
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.drop_last = drop_last
        self.relation_weights = relation_weights

        self.dataset = ProgressiveDataset(data)
        self.sampler = ProgressiveSampler(
            data,
            relation_weights=relation_weights,
            shuffle=shuffle
        )

        # 计算批次数
        self.num_batches = len(data) // batch_size
        if not drop_last and len(data) % batch_size != 0:
            self.num_batches += 1

        # 预计算索引
        self.indices = list(self.sampler)

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """
        迭代批次数据

        Yields:
            批次数据字典
        """
        if self.shuffle:
            import random
            random.shuffle(self.indices)

        for i in range(0, len(self.indices), self.batch_size):
            batch_indices = self.indices[i:i + self.batch_size]

            if len(batch_indices) < self.batch_size and self.drop_last:
                continue

            batch = [self.data[idx] for idx in batch_indices]

            yield {
                'batch': batch,
                'size': len(batch),
                'indices': batch_indices
            }

    def __len__(self) -> int:
        """返回批次数"""
        return self.num_batches

    def collate_fn(self, batch: List[Dict]) -> Dict[str, Any]:
        """
        整理批次数据（供PyTorch使用）

        Args:
            batch: 批次数据列表

        Returns:
            整理后的批次字典
        """
        # 这里可以根据实际需求定制
        return {
            'questions': [item.get('question', '') for item in batch],
            'answers': [item.get('answer', '') for item in batch],
            'relation_types': [item.get('relation_type', 'unknown') for item in batch],
            'raw_batch': batch
        }


class ProgressiveBatchCollator:
    """
    渐进式批次整理器

    用于将数据批次转换为模型输入格式。
    """

    def __init__(
        self,
        tokenizer=None,
        max_length: int = 512,
        padding: str = 'longest'
    ):
        """
        初始化整理器

        Args:
            tokenizer: 分词器
            max_length: 最大序列长度
            padding: 填充策略
        """
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.padding = padding

    def __call__(self, batch: List[Dict]) -> Dict[str, Any]:
        """
        整理批次

        Args:
            batch: 批次数据列表

        Returns:
            整理后的批次字典
        """
        if self.tokenizer is None:
            return {
                'questions': [item.get('question', '') for item in batch],
                'answers': [item.get('answer', '') for item in batch],
                'relation_types': [item.get('relation_type', 'unknown') for item in batch],
                'raw_batch': batch
            }

        # 使用tokenizer处理
        questions = [item.get('question', '') for item in batch]
        answers = [item.get('answer', '') for item in batch]

        encoded = self.tokenizer(
            questions,
            max_length=self.max_length,
            padding=self.padding,
            truncation=True,
            return_tensors='pt'
        )

        return {
            'input_ids': encoded['input_ids'],
            'attention_mask': encoded['attention_mask'],
            'labels': self.tokenizer(
                answers,
                max_length=self.max_length,
                padding=self.padding,
                truncation=True,
                return_tensors='pt'
            )['input_ids'],
            'relation_types': [item.get('relation_type', 'unknown') for item in batch],
            'raw_batch': batch
        }
