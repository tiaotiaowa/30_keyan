"""
C1: 空间关系蒸馏损失 (Spatial Relation Distillation Loss)

使用Forward KL散度进行知识蒸馏。
KL(P_T || P_S) = Σ P_T(x) × log(P_T(x) / P_S(x))

根据空间关系类型进行加权处理。
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Optional, Tuple


class SpatialRelationLoss(nn.Module):
    """
    空间关系蒸馏损失 - 使用Forward KL散度

    支持多种空间关系类型的加权蒸馏:
    - 拓扑关系 (topological): 相邻、包含、相交等
    - 方位关系 (directional): 北、南、东、西等
    - 距离关系 (distance): 近、中、远等
    """

    # 空间关系类型及其默认权重
    RELATION_TYPES = {
        'topological': 1.0,    # 拓扑关系
        'directional': 1.2,    # 方位关系 (通常更难，权重更高)
        'distance': 0.8,       # 距离关系
        'semantic': 1.0,       # 语义关系
    }

    def __init__(
        self,
        temperature: float = 4.0,
        relation_weights: Optional[Dict[str, float]] = None,
        reduction: str = 'batchmean',
        epsilon: float = 1e-8
    ):
        """
        初始化空间关系蒸馏损失

        Args:
            temperature: 软标签的温度参数
            relation_weights: 各关系类型的权重字典
            reduction: 'none', 'batchmean', 'sum', 'mean'
            epsilon: 数值稳定性常数
        """
        super().__init__()
        self.temperature = temperature
        self.reduction = reduction
        self.epsilon = epsilon

        # 合并默认权重和用户自定义权重
        self.relation_weights = self.RELATION_TYPES.copy()
        if relation_weights is not None:
            self.relation_weights.update(relation_weights)

    def forward_kl_divergence(
        self,
        p_teacher: torch.Tensor,
        p_student: torch.Tensor,
        weight: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        计算Forward KL散度: KL(P_T || P_S)

        KL(P_T || P_S) = Σ P_T(x) × log(P_T(x) / P_S(x))

        使用F.kl_div实现，参数说明:
        - input: log概率 (学生模型的log_softmax)
        - target: 概率 (教师模型的softmax)
        - log_target=False: 表示target是概率分布，不是log概率
        - reduction='none': 先不聚合，便于后续处理

        Args:
            p_teacher: 教师模型的概率分布 (batch_size, num_classes)
            p_student: 学生模型的概率分布 (batch_size, num_classes)
            weight: 可选的样本权重 (batch_size,)

        Returns:
            KL散度损失
        """
        # 数值稳定性处理
        p_teacher = torch.clamp(p_teacher, min=self.epsilon, max=1.0)
        p_student = torch.clamp(p_student, min=self.epsilon, max=1.0)

        # 使用F.kl_div计算Forward KL散度
        # F.kl_div(input, target, log_target=False) 计算的是:
        # KL(target || input) = Σ target × log(target / input)
        # 即 KL(P_T || P_S)，因为我们要教师分布覆盖学生分布
        kl_div = F.kl_div(
            p_student.log(),      # input: 学生模型的log概率
            p_teacher,            # target: 教师模型的概率
            reduction='none',     # 不聚合，保持维度
            log_target=False      # target是概率，不是log概率
        )

        # kl_div现在是(batch_size, num_classes)，对类别维度求和
        kl_div = kl_div.sum(dim=-1)

        # 应用样本权重
        if weight is not None:
            kl_div = kl_div * weight

        # 根据reduction模式处理
        if self.reduction == 'none':
            return kl_div
        elif self.reduction == 'batchmean':
            return kl_div.mean() if weight is None else kl_div.sum() / weight.sum()
        elif self.reduction == 'sum':
            return kl_div.sum()
        elif self.reduction == 'mean':
            return kl_div.mean()
        else:
            raise ValueError(f"Unknown reduction: {self.reduction}")

    def forward(
        self,
        student_logits: Dict[str, torch.Tensor],
        teacher_logits: Dict[str, torch.Tensor],
        relation_types: Optional[Dict[str, str]] = None
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        计算空间关系蒸馏损失

        Args:
            student_logits: 学生模型的logits字典
                {relation_name: (batch_size, num_classes)}
            teacher_logits: 教师模型的logits字典
                {relation_name: (batch_size, num_classes)}
            relation_types: 各关系的类型映射
                {relation_name: relation_type}

        Returns:
            total_loss: 总损失
            loss_dict: 各关系的损失详情
        """
        if relation_types is None:
            # 默认所有关系都是topological类型
            relation_types = {
                name: 'topological'
                for name in student_logits.keys()
            }

        total_loss = 0.0
        loss_dict = {}
        total_weight = 0.0

        for relation_name, student_logit in student_logits.items():
            if relation_name not in teacher_logits:
                continue

            teacher_logit = teacher_logits[relation_name]

            # 获取关系类型和对应权重
            rel_type = relation_types.get(relation_name, 'topological')
            weight = self.relation_weights.get(rel_type, 1.0)

            # 计算软标签概率分布
            p_teacher = F.softmax(teacher_logit / self.temperature, dim=-1)
            p_student = F.softmax(student_logit / self.temperature, dim=-1)

            # 计算该关系的KL散度损失
            relation_loss = self.forward_kl_divergence(p_teacher, p_student)

            # 应用关系类型权重
            weighted_loss = relation_loss * weight

            # 记录详细损失
            loss_dict[relation_name] = {
                'loss': relation_loss.item(),
                'weight': weight,
                'weighted_loss': weighted_loss.item()
            }

            total_loss += weighted_loss
            total_weight += weight

        # 温度平方归一化 (标准做法)
        total_loss = total_loss / (self.temperature ** 2)

        # 平均归一化
        if total_weight > 0:
            total_loss = total_loss / total_weight

        return total_loss, loss_dict


def forward_kl_divergence(
    p_teacher: torch.Tensor,
    p_student: torch.Tensor,
    temperature: float = 4.0,
    reduction: str = 'batchmean',
    epsilon: float = 1e-8
) -> torch.Tensor:
    """
    独立函数: 计算Forward KL散度

    KL(P_T || P_S) = Σ P_T(x) × log(P_T(x) / P_S(x))

    使用F.kl_div实现，确保Forward KL语义:
    - F.kl_div(input, target, log_target=False) = KL(target || input)
    - 我们传入学生作为input，教师作为target
    - 得到 KL(P_T || P_S)，即Forward KL

    Args:
        p_teacher: 教师模型的logits (batch_size, num_classes)
        p_student: 学生模型的logits (batch_size, num_classes)
        temperature: 温度参数
        reduction: 'none', 'batchmean', 'sum', 'mean'
        epsilon: 数值稳定性常数

    Returns:
        KL散度损失
    """
    # 转换为概率分布
    if not torch.allclose(p_teacher.exp().sum(dim=-1, keepdim=True), torch.ones(1)):
        p_teacher = F.softmax(p_teacher / temperature, dim=-1)
    if not torch.allclose(p_student.exp().sum(dim=-1, keepdim=True), torch.ones(1)):
        p_student = F.softmax(p_student / temperature, dim=-1)

    # 数值稳定性
    p_teacher = torch.clamp(p_teacher, min=epsilon, max=1.0)
    p_student = torch.clamp(p_student, min=epsilon, max=1.0)

    # 使用F.kl_div计算Forward KL
    # log_target=False 表示target是概率分布，不是log概率
    kl_div = F.kl_div(
        p_student.log(),      # input: 学生模型的log概率
        p_teacher,            # target: 教师模型的概率
        reduction='none',
        log_target=False      # 关键: 确保Forward KL语义
    )
    kl_div = kl_div.sum(dim=-1)

    if reduction == 'none':
        return kl_div / (temperature ** 2)
    elif reduction == 'batchmean':
        return kl_div.mean() / (temperature ** 2)
    elif reduction == 'sum':
        return kl_div.sum() / (temperature ** 2)
    elif reduction == 'mean':
        return kl_div.mean() / (temperature ** 2)
    else:
        raise ValueError(f"Unknown reduction: {reduction}")


class AdaptiveSpatialRelationLoss(SpatialRelationLoss):
    """
    自适应空间关系蒸馏损失

    根据训练进度动态调整温度和权重
    """

    def __init__(
        self,
        initial_temperature: float = 4.0,
        min_temperature: float = 1.0,
        total_epochs: int = 100,
        **kwargs
    ):
        super().__init__(temperature=initial_temperature, **kwargs)
        self.initial_temperature = initial_temperature
        self.min_temperature = min_temperature
        self.total_epochs = total_epochs
        self.current_epoch = 0

    def set_epoch(self, epoch: int):
        """设置当前训练轮次"""
        self.current_epoch = epoch
        # 线性衰减温度
        progress = epoch / self.total_epochs
        self.temperature = (
            self.initial_temperature * (1 - progress) +
            self.min_temperature * progress
        )

    def forward(self, *args, **kwargs):
        """前向传播，返回损失和当前温度"""
        loss, loss_dict = super().forward(*args, **kwargs)
        return loss, loss_dict, self.temperature
