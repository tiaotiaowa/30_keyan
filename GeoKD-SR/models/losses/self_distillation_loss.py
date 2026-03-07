"""
C4: 自蒸馏损失 (Self-Distillation Loss)

自蒸馏是一种特殊的知识蒸馏方法，学生模型自身的logits作为软目标。
不改变训练数据，只改变损失函数。

核心思想:
- 模型在训练过程中学习自己早期的预测
- 通过数据增强产生两个视角: anchor和augmented
- 公式: L_self = KL(P_student || P_student_aug)

优势:
1. 不需要教师模型
2. 不改变训练数据
3. 可以与任何其他损失函数结合
4. 提升模型对数据增强的鲁棒性
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Tuple, Dict, Callable


class SelfDistillationLoss(nn.Module):
    """
    自蒸馏损失

    将学生模型自身在增强数据上的预测作为软目标。

    L_self = KL(P(x) || P(T(x)))

    其中:
    - x: 原始输入
    - T(x): 增强后的输入
    - P: 模型的概率分布
    """

    def __init__(
        self,
        temperature: float = 4.0,
        lambda_self: float = 0.5,
        reduction: str = 'batchmean',
        epsilon: float = 1e-8
    ):
        """
        初始化自蒸馏损失

        Args:
            temperature: 软标签温度参数
            lambda_self: 自蒸馏损失的权重
            reduction: 'none', 'batchmean', 'sum', 'mean'
            epsilon: 数值稳定性常数
        """
        super().__init__()
        self.temperature = temperature
        self.lambda_self = lambda_self
        self.reduction = reduction
        self.epsilon = epsilon

    def compute_self_kl(
        self,
        p_anchor: torch.Tensor,
        p_augmented: torch.Tensor
    ) -> torch.Tensor:
        """
        计算自蒸馏KL散度

        KL(P_anchor || P_augmented) = Σ P_anchor × log(P_anchor / P_augmented)

        Args:
            p_anchor: 原始输入的概率分布
            p_augmented: 增强输入的概率分布

        Returns:
            自蒸馏KL散度
        """
        # 数值稳定性
        p_anchor = torch.clamp(p_anchor, min=self.epsilon, max=1.0)
        p_augmented = torch.clamp(p_augmented, min=self.epsilon, max=1.0)

        # KL散度
        kl_div = p_anchor * (torch.log(p_anchor) - torch.log(p_augmented))
        kl_div = kl_div.sum(dim=-1)

        # Reduction
        if self.reduction == 'none':
            return kl_div
        elif self.reduction == 'batchmean':
            return kl_div.mean()
        elif self.reduction == 'sum':
            return kl_div.sum()
        elif self.reduction == 'mean':
            return kl_div.mean()
        else:
            raise ValueError(f"Unknown reduction: {self.reduction}")

    def forward(
        self,
        anchor_logits: torch.Tensor,
        augmented_logits: torch.Tensor,
        targets: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        计算自蒸馏损失

        Args:
            anchor_logits: 原始输入的logits
            augmented_logits: 增强输入的logits
            targets: 真实标签 (可选，用于混合损失)

        Returns:
            total_loss: 总损失
            loss_info: 损失详情
        """
        # 转换为概率分布
        p_anchor = F.softmax(anchor_logits / self.temperature, dim=-1)
        p_augmented = F.softmax(augmented_logits / self.temperature, dim=-1)

        # 自蒸馏损失
        self_loss = self.compute_self_kl(p_anchor, p_augmented)
        self_loss = self_loss / (self.temperature ** 2)

        loss_info = {
            'self_distillation_loss': self_loss.item(),
            'lambda_self': self.lambda_self
        }

        # 如果提供了真实标签，计算混合损失
        if targets is not None:
            # 标准交叉熵损失
            ce_loss = F.cross_entropy(anchor_logits, targets)

            # 混合损失
            total_loss = (
                self.lambda_self * self_loss +
                (1 - self.lambda_self) * ce_loss
            )

            loss_info['ce_loss'] = ce_loss.item()
            loss_info['total_loss'] = total_loss.item()
        else:
            total_loss = self_loss
            loss_info['total_loss'] = total_loss.item()

        return total_loss, loss_info


class TemporalSelfDistillationLoss(nn.Module):
    """
    时序自蒸馏损失

    使用模型历史时刻的预测作为软目标。

    L_temporal = KL(P_current || P_ema)

    其中EMA是指数移动平均的历史模型。
    """

    def __init__(
        self,
        temperature: float = 4.0,
        ema_decay: float = 0.999,
        lambda_temporal: float = 0.5,
        epsilon: float = 1e-8
    ):
        """
        初始化时序自蒸馏损失

        Args:
            temperature: 温度参数
            ema_decay: EMA衰减率
            lambda_temporal: 时序蒸馏权重
            epsilon: 数值稳定性常数
        """
        super().__init__()
        self.temperature = temperature
        self.ema_decay = ema_decay
        self.lambda_temporal = lambda_temporal
        self.epsilon = epsilon
        self.ema_logits = None

    def update_ema(self, current_logits: torch.Tensor):
        """
        更新EMA logits

        Args:
            current_logits: 当前批次的logits
        """
        with torch.no_grad():
            if self.ema_logits is None:
                self.ema_logits = current_logits.detach().clone()
            else:
                self.ema_logits = (
                    self.ema_decay * self.ema_logits +
                    (1 - self.ema_decay) * current_logits.detach()
                )

    def forward(
        self,
        current_logits: torch.Tensor,
        targets: Optional[torch.Tensor] = None,
        update_ema: bool = True
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        计算时序自蒸馏损失

        Args:
            current_logits: 当前模型的logits
            targets: 真实标签 (可选)
            update_ema: 是否更新EMA

        Returns:
            total_loss: 总损失
            loss_info: 损失详情
        """
        if update_ema:
            self.update_ema(current_logits)

        if self.ema_logits is None:
            # 第一次迭代，没有EMA历史
            if targets is not None:
                loss = F.cross_entropy(current_logits, targets)
                return loss, {'ce_loss': loss.item()}
            else:
                return torch.tensor(0.0), {}

        # 计算概率分布
        p_current = F.softmax(current_logits / self.temperature, dim=-1)
        p_ema = F.softmax(self.ema_logits / self.temperature, dim=-1)

        # 时序自蒸馏损失
        p_current = torch.clamp(p_current, min=self.epsilon, max=1.0)
        p_ema = torch.clamp(p_ema, min=self.epsilon, max=1.0)

        kl_div = p_current * (torch.log(p_current) - torch.log(p_ema))
        temporal_loss = kl_div.sum(dim=-1).mean() / (self.temperature ** 2)

        loss_info = {
            'temporal_distillation_loss': temporal_loss.item(),
            'lambda_temporal': self.lambda_temporal
        }

        # 混合损失
        if targets is not None:
            ce_loss = F.cross_entropy(current_logits, targets)
            total_loss = (
                self.lambda_temporal * temporal_loss +
                (1 - self.lambda_temporal) * ce_loss
            )
            loss_info['ce_loss'] = ce_loss.item()
            loss_info['total_loss'] = total_loss.item()
        else:
            total_loss = temporal_loss
            loss_info['total_loss'] = total_loss.item()

        return total_loss, loss_info


class DeepSelfDistillationLoss(nn.Module):
    """
    深层自蒸馏损失

    同时在多层特征上应用自蒸馏。

    L_deep = Σ layer_i KL(P_i(anchor) || P_i(augmented))
    """

    def __init__(
        self,
        temperature: float = 4.0,
        layer_weights: Optional[Dict[str, float]] = None,
        epsilon: float = 1e-8
    ):
        """
        初始化深层自蒸馏损失

        Args:
            temperature: 温度参数
            layer_weights: 各层的权重字典
            epsilon: 数值稳定性常数
        """
        super().__init__()
        self.temperature = temperature
        self.epsilon = epsilon

        # 默认层权重 (越深层权重越大)
        self.layer_weights = layer_weights or {
            'layer1': 0.5,
            'layer2': 0.7,
            'layer3': 1.0,
            'layer4': 1.2
        }

    def forward(
        self,
        anchor_features: Dict[str, torch.Tensor],
        augmented_features: Dict[str, torch.Tensor]
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        计算深层自蒸馏损失

        Args:
            anchor_features: 原始输入的多层特征
            augmented_features: 增强输入的多层特征

        Returns:
            total_loss: 总损失
            loss_info: 损失详情
        """
        total_loss = 0.0
        total_weight = 0.0
        loss_info = {}

        for layer_name, anchor_feat in anchor_features.items():
            if layer_name not in augmented_features:
                continue

            aug_feat = augmented_features[layer_name]
            weight = self.layer_weights.get(layer_name, 1.0)

            # 归一化特征
            p_anchor = F.softmax(anchor_feat / self.temperature, dim=-1)
            p_aug = F.softmax(aug_feat / self.temperature, dim=-1)

            # 数值稳定性
            p_anchor = torch.clamp(p_anchor, min=self.epsilon, max=1.0)
            p_aug = torch.clamp(p_aug, min=self.epsilon, max=1.0)

            # KL散度
            kl_div = p_anchor * (torch.log(p_anchor) - torch.log(p_aug))
            layer_loss = kl_div.sum() / (self.temperature ** 2)

            total_loss += layer_loss * weight
            total_weight += weight

            loss_info[layer_name] = layer_loss.item()

        # 归一化
        if total_weight > 0:
            total_loss = total_loss / total_weight

        loss_info['total_loss'] = total_loss.item() if isinstance(total_loss, torch.Tensor) else total_loss

        return total_loss, loss_info


class SpatialSelfDistillationLoss(SelfDistillationLoss):
    """
    空间自蒸馏损失

    专门针对空间关系任务设计的自蒸馏损失。
    """

    def __init__(
        self,
        temperature: float = 4.0,
        lambda_self: float = 0.5,
        relation_weights: Optional[Dict[str, float]] = None,
        epsilon: float = 1e-8
    ):
        """
        初始化空间自蒸馏损失

        Args:
            temperature: 温度参数
            lambda_self: 自蒸馏权重
            relation_weights: 各空间关系类型的权重
            epsilon: 数值稳定性常数
        """
        super().__init__(
            temperature=temperature,
            lambda_self=lambda_self,
            epsilon=epsilon
        )

        # 空间关系类型权重
        self.relation_weights = relation_weights or {
            'topological': 1.0,
            'directional': 1.2,
            'distance': 0.8,
            'semantic': 1.0
        }

    def forward(
        self,
        anchor_logits: Dict[str, torch.Tensor],
        augmented_logits: Dict[str, torch.Tensor],
        relation_types: Optional[Dict[str, str]] = None,
        targets: Optional[Dict[str, torch.Tensor]] = None
    ) -> Tuple[torch.Tensor, Dict[str, any]]:
        """
        计算空间自蒸馏损失

        Args:
            anchor_logits: 原始输入的各关系logits
            augmented_logits: 增强输入的各关系logits
            relation_types: 各关系的类型
            targets: 各关系的真实标签 (可选)

        Returns:
            total_loss: 总损失
            loss_info: 损失详情
        """
        if relation_types is None:
            relation_types = {
                name: 'topological'
                for name in anchor_logits.keys()
            }

        total_self_loss = 0.0
        total_weight = 0.0
        relation_losses = {}

        for rel_name, anchor_logit in anchor_logits.items():
            if rel_name not in augmented_logits:
                continue

            aug_logit = augmented_logits[rel_name]
            rel_type = relation_types.get(rel_name, 'topological')
            weight = self.relation_weights.get(rel_type, 1.0)

            # 转换为概率分布
            p_anchor = F.softmax(anchor_logit / self.temperature, dim=-1)
            p_aug = F.softmax(aug_logit / self.temperature, dim=-1)

            # 自蒸馏KL
            p_anchor = torch.clamp(p_anchor, min=self.epsilon, max=1.0)
            p_aug = torch.clamp(p_aug, min=self.epsilon, max=1.0)

            kl_div = p_anchor * (torch.log(p_anchor) - torch.log(p_aug))
            rel_loss = kl_div.sum(dim=-1).mean() / (self.temperature ** 2)

            relation_losses[rel_name] = {
                'loss': rel_loss.item(),
                'weight': weight,
                'type': rel_type
            }

            total_self_loss += rel_loss * weight
            total_weight += weight

        # 归一化
        if total_weight > 0:
            total_self_loss = total_self_loss / total_weight

        # 加上CE损失 (如果提供了标签)
        total_loss = self.lambda_self * total_self_loss
        loss_info = {
            'self_distillation_loss': total_self_loss.item() if isinstance(total_self_loss, torch.Tensor) else total_self_loss,
            'relation_losses': relation_losses
        }

        if targets is not None:
            total_ce_loss = 0.0
            ce_count = 0

            for rel_name, rel_target in targets.items():
                if rel_name in anchor_logits:
                    ce_loss = F.cross_entropy(anchor_logits[rel_name], rel_target)
                    total_ce_loss += ce_loss
                    ce_count += 1

            if ce_count > 0:
                total_ce_loss = total_ce_loss / ce_count
                total_loss += (1 - self.lambda_self) * total_ce_loss
                loss_info['ce_loss'] = total_ce_loss.item()

        loss_info['total_loss'] = total_loss.item() if isinstance(total_loss, torch.Tensor) else total_loss
        loss_info['lambda_self'] = self.lambda_self

        return total_loss, loss_info
