"""
GeoKD-SR 数据调度模块

本模块实现渐进式数据调度策略，用于C6渐进式蒸馏组件。
与损失权重调度不同，数据调度通过控制训练数据的分布
来实现课程学习效果。

主要组件:
    - ProgressiveDataScheduler: 渐进式数据调度器
    - AdaptiveProgressiveScheduler: 自适应渐进式调度器
    - RelationSampler: 空间关系采样器
    - ProgressiveDataLoader: 渐进式数据加载器
"""

from .progressive_scheduler import (
    ProgressiveDataScheduler,
    AdaptiveProgressiveScheduler,
    RelationSampler,
    DEFAULT_PHASES,
    PHASE_1_CONFIG,
    PHASE_2_CONFIG,
    PHASE_3_CONFIG,
    RELATION_TYPES,
    create_scheduler_from_json,
)

from .data_loader import (
    ProgressiveDataset,
    ProgressiveSampler,
    ProgressiveDataLoader,
    ProgressiveBatchCollator,
)

__all__ = [
    # 调度器
    'ProgressiveDataScheduler',
    'AdaptiveProgressiveScheduler',
    'RelationSampler',
    # 配置
    'DEFAULT_PHASES',
    'PHASE_1_CONFIG',
    'PHASE_2_CONFIG',
    'PHASE_3_CONFIG',
    'RELATION_TYPES',
    # 工厂函数
    'create_scheduler_from_json',
    # 数据加载器
    'ProgressiveDataset',
    'ProgressiveSampler',
    'ProgressiveDataLoader',
    'ProgressiveBatchCollator',
]
