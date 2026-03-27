"""
地理特异性评测指标模块

该模块提供用于评估地理空间推理模型性能的专门指标，包括：
- 方向错误率
- 拓扑混淆矩阵
- 距离误差MAPE
- 空间关系提取F1
- 推理链准确率
"""

from .geo_metrics import (
    # 方向相关指标
    direction_error_rate,
    direction_accuracy,
    direction_confusion_matrix,

    # 拓扑关系指标
    topology_confusion_matrix,
    topology_classification_report,

    # 距离相关指标
    distance_mape,
    distance_mae,
    distance_rmse,

    # 空间关系提取指标
    spatial_relation_f1,
    spatial_relation_precision,
    spatial_relation_recall,

    # 推理链指标
    reasoning_accuracy,
    reasoning_step_accuracy,
    reasoning_chain_completeness,

    # 综合指标
    GeoMetricsCalculator
)

__all__ = [
    # 方向相关指标
    'direction_error_rate',
    'direction_accuracy',
    'direction_confusion_matrix',

    # 拓扑关系指标
    'topology_confusion_matrix',
    'topology_classification_report',

    # 距离相关指标
    'distance_mape',
    'distance_mae',
    'distance_rmse',

    # 空间关系提取指标
    'spatial_relation_f1',
    'spatial_relation_precision',
    'spatial_relation_recall',

    # 推理链指标
    'reasoning_accuracy',
    'reasoning_step_accuracy',
    'reasoning_chain_completeness',

    # 综合计算器
    'GeoMetricsCalculator'
]

__version__ = '1.0.0'
