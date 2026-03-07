"""
GeoKD-SR 损失函数模块

包含7种损失函数:
- C1: 空间关系蒸馏损失 (Forward KL)
- C2: 思维链蒸馏损失 (带1/n归一化)
- C3: 逆向KL蒸馏损失
- C4: 自蒸馏损失
- C5: 空间关系注意力蒸馏
- C6: 渐进式蒸馏 (3 epoch版本)
- C7: 混合KL蒸馏损失 (动态权重调整，解决D3-8问题)
"""

from .spatial_relation_loss import SpatialRelationLoss, forward_kl_divergence
from .spatial_cot_loss import SpatialChainOfThoughtLoss
from .spatial_reverse_kl import SpatialReverseKLLoss
from .self_distillation_loss import SelfDistillationLoss
from .spatial_attention_distill import SpatialAttentionDistillLoss
from .progressive_distill import ProgressiveDistillationLoss
from .hybrid_kl_loss import (
    HybridKLDistillationLoss,
    AdaptiveHybridKLLoss,
    create_hybrid_kl_loss
)

__all__ = [
    'SpatialRelationLoss',
    'SpatialChainOfThoughtLoss',
    'SpatialReverseKLLoss',
    'SelfDistillationLoss',
    'SpatialAttentionDistillLoss',
    'ProgressiveDistillationLoss',
    'HybridKLDistillationLoss',
    'AdaptiveHybridKLLoss',
    'create_hybrid_kl_loss',
    'forward_kl_divergence',
]
