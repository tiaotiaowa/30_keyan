"""
C6: 渐进式数据调度器 (Progressive Data Scheduler)

解决D3-9问题：C6通过数据调度实现，非损失权重。

核心思想:
- 按训练阶段动态调整数据分布，而非调整损失权重
- 从简单到复杂逐步引入不同类型的空间关系
- 3 epoch版本：每个epoch处理不同复杂度的数据

与损失权重调度的区别:
    - 损失权重调度: 所有数据都参与，只是权重不同
    - 数据调度: 不同阶段使用不同的数据子集

优势:
    1. 更符合课程学习的原始思想
    2. 训练效率更高（早期不处理复杂数据）
    3. 避免简单数据被复杂数据淹没
"""

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np


# 默认阶段配置（3 epoch版本）
DEFAULT_PHASES: Dict[int, Dict[str, Any]] = {
    0: {  # epoch 0: 方向关系（最简单）
        'relations': ['directional'],
        'weights': [1.0],
        'description': 'Phase 1: 方向关系（最基础的空间认知）'
    },
    1: {  # epoch 1: 方向 + 拓扑
        'relations': ['directional', 'topological'],
        'weights': [0.3, 1.0],
        'description': 'Phase 2: 方向 + 拓扑关系（空间邻接与连接）'
    },
    2: {  # epoch 2: 全部关系
        'relations': ['directional', 'topological', 'metric', 'composite'],
        'weights': [0.2, 0.3, 0.5, 1.0],
        'description': 'Phase 3: 完整空间关系（包含度量和组合推理）'
    }
}

# 各阶段独立配置（便于引用）
PHASE_1_CONFIG = DEFAULT_PHASES[0]
PHASE_2_CONFIG = DEFAULT_PHASES[1]
PHASE_3_CONFIG = DEFAULT_PHASES[2]

# 空间关系类型定义
RELATION_TYPES = {
    'directional': [
        'north', 'south', 'east', 'west',
        'northeast', 'northwest', 'southeast', 'southwest'
    ],
    'topological': [
        'adjacent', 'disjoint', 'equal', 'inside',
        'contains', 'overlap', 'touches', 'crosses'
    ],
    'metric': [
        'near', 'far', 'very_near', 'very_far',
        'distance_less_than', 'distance_greater_than'
    ],
    'composite': [
        'multi_hop_relation', 'spatial_reasoning',
        'path_finding', 'region_query'
    ]
}


class RelationSampler:
    """
    空间关系采样器

    根据配置的权重从不同关系类型中采样数据。
    """

    def __init__(
        self,
        relation_weights: Dict[str, float],
        seed: Optional[int] = None
    ):
        """
        初始化采样器

        Args:
            relation_weights: 关系类型到权重的映射
            seed: 随机种子
        """
        self.relation_weights = relation_weights
        self.relations = list(relation_weights.keys())
        self.weights = list(relation_weights.values())

        # 归一化权重
        total = sum(self.weights)
        if total > 0:
            self.weights = [w / total for w in self.weights]

        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    def sample_relation(self) -> str:
        """
        采样一个关系类型

        Returns:
            关系类型名称
        """
        return random.choices(self.relations, weights=self.weights, k=1)[0]

    def sample_batch(
        self,
        data_by_relation: Dict[str, List[Dict]],
        batch_size: int,
        replace: bool = True
    ) -> List[Dict]:
        """
        采样一批数据

        Args:
            data_by_relation: 按关系类型分组的数据
            batch_size: 批次大小
            replace: 是否允许重复采样

        Returns:
            采样得到的数据列表
        """
        batch = []

        for _ in range(batch_size):
            relation = self.sample_relation()

            if relation not in data_by_relation or not data_by_relation[relation]:
                continue

            if replace or len(data_by_relation[relation]) >= batch_size:
                sample = random.choice(data_by_relation[relation])
                batch.append(sample)
            else:
                # 不重复采样：用完后跳过
                continue

        return batch

    def get_distribution(self) -> Dict[str, float]:
        """获取当前采样分布"""
        return dict(zip(self.relations, self.weights))


class ProgressiveDataScheduler:
    """
    渐进式数据调度器 - 按训练阶段调整数据分布

    C6组件的核心实现：通过数据调度而非损失权重来实现课程学习。

    工作原理:
        1. 加载全部数据并按关系类型分组
        2. 根据当前epoch获取对应的阶段配置
        3. 按配置的权重采样数据
        4. 返回当前epoch的训练数据

    与损失权重的关键区别:
        - 损失权重: 所有数据参与训练，只是损失不同
        - 数据调度: 只采样特定类型的数据参与训练

    示例:
        >>> scheduler = ProgressiveDataScheduler('data/train.json')
        >>> # Epoch 0: 只有方向关系
        >>> epoch_0_data = scheduler.get_epoch_data(0)
        >>> # Epoch 1: 方向 + 拓扑
        >>> epoch_1_data = scheduler.get_epoch_data(1)
        >>> # Epoch 2: 全部关系
        >>> epoch_2_data = scheduler.get_epoch_data(2)
    """

    def __init__(
        self,
        data_path: str,
        phases: Optional[Dict[int, Dict]] = None,
        total_epochs: int = 3,
        seed: Optional[int] = 42,
        shuffle: bool = True,
        cache_data: bool = True
    ):
        """
        初始化调度器

        Args:
            data_path: 数据文件路径（JSON格式）
            phases: 自定义阶段配置，默认使用DEFAULT_PHASES
            total_epochs: 总训练轮次
            seed: 随机种子
            shuffle: 是否打乱数据
            cache_data: 是否缓存数据到内存
        """
        self.data_path = Path(data_path)
        self.phases = phases if phases is not None else DEFAULT_PHASES
        self.total_epochs = total_epochs
        self.seed = seed
        self.shuffle = shuffle
        self.cache_data = cache_data

        # 设置随机种子
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        # 数据缓存
        self._all_data: Optional[List[Dict]] = None
        self._data_by_relation: Optional[Dict[str, List[Dict]]] = None

        # 统计信息
        self.stats = {
            'total_samples': 0,
            'relation_distribution': {},
            'phase_stats': {}
        }

    def load_data(self) -> List[Dict]:
        """
        加载数据文件

        Returns:
            数据列表
        """
        if self._all_data is not None and self.cache_data:
            return self._all_data

        if not self.data_path.exists():
            raise FileNotFoundError(f"数据文件不存在: {self.data_path}")

        with open(self.data_path, 'r', encoding='utf-8') as f:
            self._all_data = json.load(f)

        if not isinstance(self._all_data, list):
            raise ValueError(f"数据格式错误: 期望list, 实际{type(self._all_data)}")

        self.stats['total_samples'] = len(self._all_data)

        return self._all_data

    def group_by_relation(
        self,
        data: Optional[List[Dict]] = None
    ) -> Dict[str, List[Dict]]:
        """
        按关系类型分组数据

        Args:
            data: 数据列表，如果为None则调用load_data()

        Returns:
            按关系类型分组的数据字典
        """
        if self._data_by_relation is not None and self.cache_data:
            return self._data_by_relation

        if data is None:
            data = self.load_data()

        grouped = {
            'directional': [],
            'topological': [],
            'metric': [],
            'composite': [],
            'unknown': []
        }

        for item in data:
            relation_type = self._detect_relation_type(item)

            # 添加关系类型标记（如果不存在）
            if 'relation_type' not in item:
                item['relation_type'] = relation_type

            grouped[relation_type].append(item)

        self._data_by_relation = grouped

        # 统计分布
        for rel_type, items in grouped.items():
            self.stats['relation_distribution'][rel_type] = len(items)

        return grouped

    def _detect_relation_type(self, item: Dict) -> str:
        """
        检测数据项的空间关系类型

        Args:
            item: 数据项，应包含question或relation_type字段

        Returns:
            关系类型 ('directional', 'topological', 'metric', 'composite', 'unknown')
        """
        # 首先检查显式标记
        if 'relation_type' in item:
            return item['relation_type']

        # 从问题中推断
        question = item.get('question', '').lower()
        keywords = item.get('keywords', [])

        # 组合关系：多步推理
        if any(word in question for word in ['经过', '路线', '路径', '依次', '顺序']):
            return 'composite'

        # 度量关系：距离相关
        if any(word in question for word in ['距离', '公里', '千米', '米', '多远', '近', '远']):
            return 'metric'

        # 方向关系：方向相关
        if any(word in question for word in ['东', '西', '南', '北', '方向', '方位']):
            return 'directional'

        # 拓扑关系：相邻、包含等
        if any(word in question for word in ['相邻', '接壤', '包含', '在内', '边界']):
            return 'topological'

        # 从关键词推断
        for keyword in keywords:
            keyword_lower = keyword.lower()
            for rel_type, rel_keywords in RELATION_TYPES.items():
                if keyword_lower in rel_keywords:
                    return rel_type

        return 'unknown'

    def get_phase_config(self, current_epoch: int) -> Dict[str, Any]:
        """
        获取当前阶段的配置

        Args:
            current_epoch: 当前训练轮次

        Returns:
            阶段配置字典
        """
        # 超出配置的轮次使用最后一个阶段配置
        epoch_key = min(current_epoch, len(self.phases) - 1)

        if epoch_key not in self.phases:
            # 如果没有配置，使用最后一个
            epoch_key = list(self.phases.keys())[-1]

        return self.phases[epoch_key]

    def get_sampling_weights(self, current_epoch: int) -> Dict[str, float]:
        """
        获取当前epoch的采样权重

        Args:
            current_epoch: 当前训练轮次

        Returns:
            关系类型到权重的映射
        """
        config = self.get_phase_config(current_epoch)
        relations = config['relations']
        weights = config['weights']

        return dict(zip(relations, weights))

    def get_relation_mask(self, current_epoch: int) -> Dict[str, bool]:
        """
        获取当前epoch的关系类型掩码

        Args:
            current_epoch: 当前训练轮次

        Returns:
            关系类型到是否启用的映射
        """
        config = self.get_phase_config(current_epoch)
        relations = config['relations']

        mask = {rel: False for rel in RELATION_TYPES.keys()}
        mask['unknown'] = False

        for rel in relations:
            if rel in mask:
                mask[rel] = True

        return mask

    def get_epoch_data(
        self,
        current_epoch: int,
        num_samples: Optional[int] = None,
        replace: bool = True
    ) -> List[Dict]:
        """
        获取当前epoch的训练数据

        这是核心方法：根据阶段配置采样数据。

        Args:
            current_epoch: 当前训练轮次
            num_samples: 采样数量，None表示使用所有可用数据
            replace: 是否允许重复采样

        Returns:
            当前epoch的训练数据列表
        """
        # 获取阶段配置
        config = self.get_phase_config(current_epoch)
        active_relations = config['relations']

        # 加载并分组数据
        data_by_relation = self.group_by_relation()

        # 筛选激活的关系类型
        active_data = {}
        for rel in active_relations:
            if rel in data_by_relation:
                active_data[rel] = data_by_relation[rel]

        if not active_data:
            raise ValueError(f"Epoch {current_epoch}: 没有可用数据")

        # 创建采样器
        relation_weights = self.get_sampling_weights(current_epoch)
        sampler = RelationSampler(
            relation_weights={k: v for k, v in relation_weights.items() if k in active_data},
            seed=self.seed + current_epoch if self.seed else None
        )

        # 确定采样数量
        if num_samples is None:
            num_samples = sum(len(data) for data in active_data.values())

        # 采样数据
        sampled_data = sampler.sample_batch(
            data_by_relation=active_data,
            batch_size=num_samples,
            replace=replace
        )

        # 打乱顺序
        if self.shuffle:
            random.shuffle(sampled_data)

        # 记录统计
        self.stats['phase_stats'][current_epoch] = {
            'config': config,
            'sampled_count': len(sampled_data),
            'distribution': sampler.get_distribution()
        }

        return sampled_data

    def get_data_loader(
        self,
        current_epoch: int,
        batch_size: int = 8,
        num_samples: Optional[int] = None
    ) -> 'ProgressiveDataLoader':
        """
        获取数据加载器（兼容PyTorch DataLoader接口）

        Args:
            current_epoch: 当前训练轮次
            batch_size: 批次大小
            num_samples: 总采样数量

        Returns:
            ProgressiveDataLoader实例
        """
        from .data_loader import ProgressiveDataLoader

        data = self.get_epoch_data(current_epoch, num_samples)

        return ProgressiveDataLoader(
            data=data,
            batch_size=batch_size,
            shuffle=self.shuffle
        )

    def get_phase_name(self, current_epoch: int) -> str:
        """
        获取当前阶段名称

        Args:
            current_epoch: 当前训练轮次

        Returns:
            阶段名称
        """
        config = self.get_phase_config(current_epoch)
        return config.get('description', f'Epoch {current_epoch}')

    def get_stats(self) -> Dict[str, Any]:
        """
        获取调度器统计信息

        Returns:
            统计信息字典
        """
        return {
            'data_path': str(self.data_path),
            'total_epochs': self.total_epochs,
            'total_samples': self.stats['total_samples'],
            'relation_distribution': self.stats['relation_distribution'],
            'phase_stats': self.stats['phase_stats'],
            'phases_config': {
                k: {
                    'relations': v['relations'],
                    'weights': v['weights'],
                    'description': v.get('description', '')
                }
                for k, v in self.phases.items()
            }
        }

    def save_stats(self, output_path: str):
        """
        保存统计信息到文件

        Args:
            output_path: 输出文件路径
        """
        stats = self.get_stats()

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

    def get_curriculum_schedule(self) -> List[Dict[str, Any]]:
        """
        获取课程学习调度表

        返回每个epoch的关系类型和权重配置，
        便于可视化和调试。

        Returns:
            调度表列表，每个元素包含epoch和配置信息
        """
        schedule = []

        for epoch in range(self.total_epochs):
            config = self.get_phase_config(epoch)
            mask = self.get_relation_mask(epoch)
            weights = self.get_sampling_weights(epoch)

            schedule.append({
                'epoch': epoch,
                'phase_name': self.get_phase_name(epoch),
                'active_relations': config['relations'],
                'relation_mask': mask,
                'sampling_weights': weights
            })

        return schedule

    def visualize_schedule(self, save_path: Optional[str] = None):
        """
        可视化课程学习调度表（需要matplotlib）

        Args:
            save_path: 保存路径，None则显示图表
        """
        try:
            import matplotlib.pyplot as plt
            import pandas as pd
        except ImportError:
            print("可视化需要安装 matplotlib 和 pandas")
            return

        schedule = self.get_curriculum_schedule()

        # 创建DataFrame
        df_data = []
        for item in schedule:
            row = {'epoch': item['epoch']}
            for rel in RELATION_TYPES.keys():
                row[rel] = item['sampling_weights'].get(rel, 0.0)
            df_data.append(row)

        df = pd.DataFrame(df_data)
        df.set_index('epoch', inplace=True)

        # 绘图
        fig, ax = plt.subplots(figsize=(10, 6))
        df.plot(kind='bar', stacked=True, ax=ax)

        ax.set_xlabel('Epoch')
        ax.set_ylabel('采样权重')
        ax.set_title('渐进式数据调度 - 关系类型采样权重')
        ax.legend(title='关系类型', bbox_to_anchor=(1.05, 1), loc='upper left')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        else:
            plt.show()

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'ProgressiveDataScheduler':
        """
        从配置字典创建调度器

        Args:
            config: 配置字典

        Returns:
            ProgressiveDataScheduler实例
        """
        return cls(
            data_path=config['data_path'],
            phases=config.get('phases'),
            total_epochs=config.get('total_epochs', 3),
            seed=config.get('seed', 42),
            shuffle=config.get('shuffle', True),
            cache_data=config.get('cache_data', True)
        )


class AdaptiveProgressiveScheduler(ProgressiveDataScheduler):
    """
    自适应渐进式数据调度器

    根据模型表现动态调整阶段转换时机。
    当当前阶段的关系类型达到目标性能时，自动进入下一阶段。
    """

    def __init__(
        self,
        data_path: str,
        phases: Optional[Dict[int, Dict]] = None,
        total_epochs: int = 3,
        performance_threshold: float = 0.85,
        min_samples_per_relation: int = 100,
        **kwargs
    ):
        """
        初始化自适应调度器

        Args:
            data_path: 数据文件路径
            phases: 阶段配置
            total_epochs: 总训练轮次
            performance_threshold: 性能阈值，达到后进入下一阶段
            min_samples_per_relation: 每种关系的最小样本数
            **kwargs: 其他参数
        """
        super().__init__(data_path, phases, total_epochs, **kwargs)

        self.performance_threshold = performance_threshold
        self.min_samples_per_relation = min_samples_per_relation

        # 性能跟踪
        self.relation_performance: Dict[str, Dict[str, float]] = {}
        self.current_phase = 0

    def update_performance(
        self,
        relation_type: str,
        accuracy: float,
        sample_count: int
    ):
        """
        更新关系类型性能

        Args:
            relation_type: 关系类型
            accuracy: 准确率
            sample_count: 样本数
        """
        if relation_type not in self.relation_performance:
            self.relation_performance[relation_type] = {
                'accuracy': 0.0,
                'sample_count': 0,
                'updates': 0
            }

        perf = self.relation_performance[relation_type]
        perf['accuracy'] = (
            (perf['accuracy'] * perf['updates'] + accuracy) /
            (perf['updates'] + 1)
        )
        perf['sample_count'] += sample_count
        perf['updates'] += 1

    def should_advance_phase(self) -> bool:
        """
        判断是否应该进入下一阶段

        Returns:
            是否应该进入下一阶段
        """
        config = self.get_phase_config(self.current_phase)
        active_relations = config['relations']

        for rel in active_relations:
            if rel not in self.relation_performance:
                return False

            perf = self.relation_performance[rel]
            if perf['accuracy'] < self.performance_threshold:
                return False
            if perf['sample_count'] < self.min_samples_per_relation:
                return False

        return True

    def advance_phase(self) -> bool:
        """
        尝试进入下一阶段

        Returns:
            是否成功进入下一阶段
        """
        if self.current_phase < len(self.phases) - 1:
            if self.should_advance_phase():
                self.current_phase += 1
                return True
        return False

    def get_epoch_data(
        self,
        current_epoch: int,
        num_samples: Optional[int] = None,
        replace: bool = True
    ) -> List[Dict]:
        """
        获取当前epoch的数据（使用自适应阶段）

        Args:
            current_epoch: 当前训练轮次
            num_samples: 采样数量
            replace: 是否允许重复采样

        Returns:
            当前epoch的训练数据列表
        """
        # 使用自适应阶段而非直接使用epoch
        return super().get_epoch_data(
            current_epoch=self.current_phase,
            num_samples=num_samples,
            replace=replace
        )


def create_scheduler_from_json(config_path: str) -> ProgressiveDataScheduler:
    """
    从JSON配置文件创建调度器

    Args:
        config_path: 配置文件路径

    Returns:
        ProgressiveDataScheduler实例
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    return ProgressiveDataScheduler.from_config(config)
