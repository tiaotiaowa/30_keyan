"""
C3: 空间逆向KL蒸馏损失 (Spatial Reverse KL Distillation Loss)

使用逆向KL散度进行知识蒸馏。
KL(P_S || P_T) = Σ P_S(x) × log(P_S(x) / P_T(x))

与Forward KL的区别:
- Forward KL (KL(P_T || P_S)): 教师分布覆盖学生分布，避免学生产生教师没有的预测
- Reverse KL (KL(P_S || P_T)): 学生分布覆盖教师分布，专注于教师的高概率区域

适用场景:
- 空间关系分类中的长尾问题
- 教师模型非常自信的预测
- 需要学生模型更专注于核心空间模式
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Optional, Tuple


class SpatialReverseKLLoss(nn.Module):
    """
    空间逆向KL蒸馏损失

    使用Reverse KL散度，使学生对教师模型的高置信度预测更加敏感。
    """

    def __init__(
        self,
        temperature: float = 4.0,
        reduction: str = 'batchmean',
        epsilon: float = 1e-8,
        confidence_threshold: float = 0.8
    ):
        """
        初始化逆向KL蒸馏损失

        Args:
            temperature: 软标签温度参数
            reduction: 'none', 'batchmean', 'sum', 'mean'
            epsilon: 数值稳定性常数
            confidence_threshold: 置信度阈值，只蒸馏高置信度样本
        """
        super().__init__()
        self.temperature = temperature
        self.reduction = reduction
        self.epsilon = epsilon
        self.confidence_threshold = confidence_threshold

    def reverse_kl_divergence(
        self,
        p_teacher: torch.Tensor,
        p_student: torch.Tensor,
        weight: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        计算逆向KL散度: KL(P_S || P_T)

        KL(P_S || P_T) = Σ P_S(x) × log(P_S(x) / P_T(x))
                      = Σ P_S(x) × (log(P_S(x)) - log(P_T(x)))

        Args:
            p_teacher: 教师模型的概率分布 (batch_size, num_classes)
            p_student: 学生模型的概率分布 (batch_size, num_classes)
            weight: 可选的样本权重 (batch_size,)

        Returns:
            逆向KL散度损失
        """
        # 数值稳定性处理
        p_teacher = torch.clamp(p_teacher, min=self.epsilon, max=1.0)
        p_student = torch.clamp(p_student, min=self.epsilon, max=1.0)

        # Reverse KL: KL(P_S || P_T)
        # = P_S * log(P_S / P_T)
        # = P_S * (log(P_S) - log(P_T))
        kl_div = p_student * (torch.log(p_student) - torch.log(p_teacher))

        # 对类别维度求和
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

    def filter_by_confidence(
        self,
        teacher_logits: torch.Tensor,
        student_logits: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        根据教师模型的置信度过滤样本

        Args:
            teacher_logits: 教师模型的logits
            student_logits: 学生模型的logits

        Returns:
            filtered_teacher: 过滤后的教师logits
            filtered_student: 过滤后的学生logits
            mask: 过滤掩码
        """
        # 计算教师模型的预测置信度
        p_teacher = F.softmax(teacher_logits / self.temperature, dim=-1)
        max_prob, _ = p_teacher.max(dim=-1)

        # 创建高置信度掩码
        mask = (max_prob >= self.confidence_threshold).float()

        # 返回过滤后的结果
        return teacher_logits, student_logits, mask

    def forward(
        self,
        student_logits: Dict[str, torch.Tensor],
        teacher_logits: Dict[str, torch.Tensor],
        use_confidence_filter: bool = True
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        计算空间逆向KL蒸馏损失

        Args:
            student_logits: 学生模型的logits字典
                {relation_name: (batch_size, num_classes)}
            teacher_logits: 教师模型的logits字典
                {relation_name: (batch_size, num_classes)}
            use_confidence_filter: 是否使用置信度过滤

        Returns:
            total_loss: 总损失
            loss_dict: 各关系的损失详情
        """
        total_loss = 0.0
        loss_dict = {}
        num_relations = 0

        for relation_name, student_logit in student_logits.items():
            if relation_name not in teacher_logits:
                continue

            teacher_logit = teacher_logits[relation_name]

            # 可选: 根据置信度过滤
            if use_confidence_filter:
                teacher_logit, student_logit, weight = self.filter_by_confidence(
                    teacher_logit, student_logit
                )
            else:
                weight = None

            # 计算软标签概率分布
            p_teacher = F.softmax(teacher_logit / self.temperature, dim=-1)
            p_student = F.softmax(student_logit / self.temperature, dim=-1)

            # 计算逆向KL散度
            relation_loss = self.reverse_kl_divergence(
                p_teacher, p_student, weight
            )

            loss_dict[relation_name] = {
                'loss': relation_loss.item(),
                'num_samples': weight.sum().int().item() if weight is not None else student_logit.size(0)
            }

            total_loss += relation_loss
            num_relations += 1

        # 温度平方归一化
        total_loss = total_loss / (self.temperature ** 2)

        # 平均归一化
        if num_relations > 0:
            total_loss = total_loss / num_relations

        return total_loss, loss_dict


class HybridKLLoss(nn.Module):
    """
    混合KL损失: 结合Forward KL和Reverse KL

    L = alpha * KL(P_T || P_S) + (1 - alpha) * KL(P_S || P_T)

    这种组合可以:
    - Forward KL确保学生不产生教师没有的预测
    - Reverse KL确保学生对教师的高置信度预测敏感
    """

    def __init__(
        self,
        temperature: float = 4.0,
        alpha: float = 0.5,
        epsilon: float = 1e-8
    ):
        """
        初始化混合KL损失

        Args:
            temperature: 温度参数
            alpha: Forward KL的权重 (0-1)
            epsilon: 数值稳定性常数
        """
        super().__init__()
        self.temperature = temperature
        self.alpha = alpha
        self.epsilon = epsilon

    def forward_kl(
        self,
        p_teacher: torch.Tensor,
        p_student: torch.Tensor
    ) -> torch.Tensor:
        """Forward KL: KL(P_T || P_S)"""
        p_teacher = torch.clamp(p_teacher, min=self.epsilon, max=1.0)
        p_student = torch.clamp(p_student, min=self.epsilon, max=1.0)
        kl_div = p_teacher * (torch.log(p_teacher) - torch.log(p_student))
        return kl_div.sum(dim=-1).mean()

    def reverse_kl(
        self,
        p_teacher: torch.Tensor,
        p_student: torch.Tensor
    ) -> torch.Tensor:
        """Reverse KL: KL(P_S || P_T)"""
        p_teacher = torch.clamp(p_teacher, min=self.epsilon, max=1.0)
        p_student = torch.clamp(p_student, min=self.epsilon, max=1.0)
        kl_div = p_student * (torch.log(p_student) - torch.log(p_teacher))
        return kl_div.sum(dim=-1).mean()

    def forward(
        self,
        student_logits: torch.Tensor,
        teacher_logits: torch.Tensor
    ) -> torch.Tensor:
        """
        计算混合KL损失

        Args:
            student_logits: 学生模型的logits
            teacher_logits: 教师模型的logits

        Returns:
            混合KL损失
        """
        p_teacher = F.softmax(teacher_logits / self.temperature, dim=-1)
        p_student = F.softmax(student_logits / self.temperature, dim=-1)

        f_kl = self.forward_kl(p_teacher, p_student)
        r_kl = self.reverse_kl(p_teacher, p_student)

        total_loss = (
            self.alpha * f_kl +
            (1 - self.alpha) * r_kl
        ) / (self.temperature ** 2)

        return total_loss


class SymmetricKLLoss(nn.Module):
    """
    对称KL损失 (Jeffreys Divergence)

    JSD(P_T, P_S) = 0.5 * KL(P_T || P_S) + 0.5 * KL(P_S || P_T)

    对称KL散度是真正的距离度量，具有对称性。
    """

    def __init__(
        self,
        temperature: float = 4.0,
        epsilon: float = 1e-8
    ):
        """
        初始化对称KL损失

        Args:
            temperature: 温度参数
            epsilon: 数值稳定性常数
        """
        super().__init__()
        self.temperature = temperature
        self.epsilon = epsilon

    def forward(
        self,
        student_logits: torch.Tensor,
        teacher_logits: torch.Tensor
    ) -> torch.Tensor:
        """
        计算对称KL损失

        Args:
            student_logits: 学生模型的logits
            teacher_logits: 教师模型的logits

        Returns:
            对称KL损失
        """
        p_teacher = F.softmax(teacher_logits / self.temperature, dim=-1)
        p_student = F.softmax(student_logits / self.temperature, dim=-1)

        p_teacher = torch.clamp(p_teacher, min=self.epsilon, max=1.0)
        p_student = torch.clamp(p_student, min=self.epsilon, max=1.0)

        # Forward KL
        f_kl = p_teacher * (torch.log(p_teacher) - torch.log(p_student))
        f_kl = f_kl.sum(dim=-1).mean()

        # Reverse KL
        r_kl = p_student * (torch.log(p_student) - torch.log(p_teacher))
        r_kl = r_kl.sum(dim=-1).mean()

        # 对称组合
        total_loss = 0.5 * (f_kl + r_kl) / (self.temperature ** 2)

        return total_loss
