"""
C7: 混合KL蒸馏损失 (Hybrid KL Distillation Loss)

结合Forward KL和Reverse KL的混合损失函数，根据训练进度动态调整权重。

理论基础:
- Forward KL (KL(P_T || P_S)): 教师分布覆盖学生分布，确保学生不产生教师没有的预测
  - 训练早期使用更多Forward KL，帮助学生快速学习教师的知识分布

- Reverse KL (KL(P_S || P_T)): 学生分布覆盖教师分布，专注于教师的高置信度预测
  - 训练后期使用更多Reverse KL，让学生专注于核心空间模式，提升精确性

动态权重调整策略:
- 训练早期 (epoch 0): α = 0.7，侧重Forward KL，快速覆盖教师知识
- 训练后期 (final epoch): α = 0.3，侧重Reverse KL，精确匹配核心模式
- 权重线性衰减: α(epoch) = α_start + (α_end - α_start) × (epoch / total_epochs)

适用场景:
- 空间关系分类蒸馏 (解决D3-8问题)
- 长尾分布问题
- 需要兼顾覆盖性和精确性的知识蒸馏任务
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Optional, Tuple, Union
import math


class HybridKLDistillationLoss(nn.Module):
    """
    混合KL蒸馏损失 - 结合Forward KL和Reverse KL

    L_hybrid = α(epoch) × KL(P_T || P_S) + (1-α) × KL(P_S || P_T)

    其中 α 随训练进度线性衰减:
    - α_start: 训练初始时的α值 (默认0.7，侧重Forward KL)
    - α_end: 训练结束时的α值 (默认0.3，侧重Reverse KL)

    特点:
    1. 训练早期: Forward KL主导，快速覆盖教师的知识分布
    2. 训练后期: Reverse KL主导，精确匹配教师的核心预测模式
    3. 平滑过渡: 权重线性衰减，避免训练不稳定
    """

    def __init__(
        self,
        temperature: float = 2.0,
        alpha_start: float = 0.7,
        alpha_end: float = 0.3,
        total_epochs: int = 3,
        reduction: str = 'batchmean',
        epsilon: float = 1e-8,
        use_cosine_schedule: bool = False
    ):
        """
        初始化混合KL蒸馏损失

        Args:
            temperature: 软标签的温度参数 (默认2.0)
            alpha_start: 训练初始时的α值 (默认0.7，侧重Forward KL)
            alpha_end: 训练结束时的α值 (默认0.3，侧重Reverse KL)
            total_epochs: 总训练轮次 (默认3)
            reduction: 聚合方式: 'none', 'batchmean', 'sum', 'mean'
            epsilon: 数值稳定性常数
            use_cosine_schedule: 是否使用余弦衰减调度 (默认False，使用线性衰减)
        """
        super().__init__()
        self.temperature = temperature
        self.alpha_start = alpha_start
        self.alpha_end = alpha_end
        self.total_epochs = total_epochs
        self.reduction = reduction
        self.epsilon = epsilon
        self.use_cosine_schedule = use_cosine_schedule

        # 参数校验
        if not 0 <= alpha_start <= 1:
            raise ValueError(f"alpha_start必须在[0,1]范围内，当前为{alpha_start}")
        if not 0 <= alpha_end <= 1:
            raise ValueError(f"alpha_end必须在[0,1]范围内，当前为{alpha_end}")
        if total_epochs <= 0:
            raise ValueError(f"total_epochs必须大于0，当前为{total_epochs}")
        if temperature <= 0:
            raise ValueError(f"temperature必须大于0，当前为{temperature}")

    def get_alpha(self, current_epoch: Union[int, float]) -> float:
        """
        根据当前epoch获取α值

        默认使用线性衰减: α(epoch) = α_start + (α_end - α_start) × (epoch / total_epochs)

        如果启用余弦调度:
            α(epoch) = α_end + (α_start - α_end) × 0.5 × (1 + cos(π × epoch / total_epochs))

        Args:
            current_epoch: 当前训练轮次 (可以是浮点数，支持子epoch更新)

        Returns:
            当前epoch的α值
        """
        # 限制epoch范围
        epoch_clamped = max(0, min(current_epoch, self.total_epochs))
        progress = epoch_clamped / self.total_epochs

        if self.use_cosine_schedule:
            # 余弦衰减调度 (更平滑的过渡)
            alpha = self.alpha_end + (self.alpha_start - self.alpha_end) * 0.5 * (
                1 + math.cos(math.pi * progress)
            )
        else:
            # 线性衰减调度
            alpha = self.alpha_start + (self.alpha_end - self.alpha_start) * progress

        return float(alpha)

    def compute_forward_kl(
        self,
        p_teacher: torch.Tensor,
        p_student: torch.Tensor
    ) -> torch.Tensor:
        """
        计算Forward KL散度: KL(P_T || P_S)

        KL(P_T || P_S) = Σ P_T(x) × log(P_T(x) / P_S(x))

        Forward KL特点:
        - 教师分布覆盖学生分布
        - 惩罚学生产生教师没有的预测
        - 适合训练初期，帮助学生快速学习教师的知识分布

        Args:
            p_teacher: 教师模型的概率分布 (batch_size, num_classes)
            p_student: 学生模型的概率分布 (batch_size, num_classes)

        Returns:
            Forward KL散度损失
        """
        # 数值稳定性处理
        p_teacher = torch.clamp(p_teacher, min=self.epsilon, max=1.0)
        p_student = torch.clamp(p_student, min=self.epsilon, max=1.0)

        # Forward KL: KL(P_T || P_S) = P_T × log(P_T / P_T)
        kl_div = p_teacher * (torch.log(p_teacher) - torch.log(p_student))

        # 对类别维度求和
        kl_div = kl_div.sum(dim=-1)

        # 根据reduction模式处理
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

    def compute_reverse_kl(
        self,
        p_teacher: torch.Tensor,
        p_student: torch.Tensor
    ) -> torch.Tensor:
        """
        计算Reverse KL散度: KL(P_S || P_T)

        KL(P_S || P_T) = Σ P_S(x) × log(P_S(x) / P_T(x))

        Reverse KL特点:
        - 学生分布覆盖教师分布
        - 专注于教师的高置信度区域
        - 适合训练后期，提升学生对核心空间模式的精确性

        Args:
            p_teacher: 教师模型的概率分布 (batch_size, num_classes)
            p_student: 学生模型的概率分布 (batch_size, num_classes)

        Returns:
            Reverse KL散度损失
        """
        # 数值稳定性处理
        p_teacher = torch.clamp(p_teacher, min=self.epsilon, max=1.0)
        p_student = torch.clamp(p_student, min=self.epsilon, max=1.0)

        # Reverse KL: KL(P_S || P_T) = P_S × log(P_S / P_T)
        kl_div = p_student * (torch.log(p_student) - torch.log(p_teacher))

        # 对类别维度求和
        kl_div = kl_div.sum(dim=-1)

        # 根据reduction模式处理
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
        student_logits: Union[torch.Tensor, Dict[str, torch.Tensor]],
        teacher_logits: Union[torch.Tensor, Dict[str, torch.Tensor]],
        current_epoch: Union[int, float] = 0
    ) -> Tuple[torch.Tensor, Dict[str, any]]:
        """
        计算混合KL蒸馏损失

        L_hybrid = α × KL(P_T || P_S) + (1-α) × KL(P_S || P_T)

        Args:
            student_logits: 学生模型的logits
                - 单个logits: (batch_size, num_classes)
                - 多个logits: {relation_name: (batch_size, num_classes)}
            teacher_logits: 教师模型的logits (格式同student_logits)
            current_epoch: 当前训练轮次

        Returns:
            total_loss: 混合KL损失
            info_dict: 包含损失详情的字典
                {
                    'forward_kl': Forward KL损失值,
                    'reverse_kl': Reverse KL损失值,
                    'alpha': 当前α值,
                    'epoch': 当前epoch,
                    'losses_per_relation': 各关系的损失详情 (如果输入是字典)
                }
        """
        # 获取当前α值
        alpha = self.get_alpha(current_epoch)

        # 处理字典输入 (多个空间关系)
        if isinstance(student_logits, dict) and isinstance(teacher_logits, dict):
            return self._forward_dict(student_logits, teacher_logits, current_epoch, alpha)

        # 处理张量输入 (单个logits)
        return self._forward_tensor(student_logits, teacher_logits, current_epoch, alpha)

    def _forward_tensor(
        self,
        student_logits: torch.Tensor,
        teacher_logits: torch.Tensor,
        current_epoch: Union[int, float],
        alpha: float
    ) -> Tuple[torch.Tensor, Dict[str, any]]:
        """处理张量输入的forward方法"""
        # 计算软标签概率分布
        p_teacher = F.softmax(teacher_logits / self.temperature, dim=-1)
        p_student = F.softmax(student_logits / self.temperature, dim=-1)

        # 计算Forward KL和Reverse KL
        forward_kl = self.compute_forward_kl(p_teacher, p_student)
        reverse_kl = self.compute_reverse_kl(p_teacher, p_student)

        # 混合损失
        total_loss = (alpha * forward_kl + (1 - alpha) * reverse_kl) / (self.temperature ** 2)

        # 返回损失和信息字典
        info_dict = {
            'forward_kl': forward_kl.item() if torch.is_tensor(forward_kl) else forward_kl,
            'reverse_kl': reverse_kl.item() if torch.is_tensor(reverse_kl) else reverse_kl,
            'alpha': alpha,
            'epoch': current_epoch,
            'temperature': self.temperature
        }

        return total_loss, info_dict

    def _forward_dict(
        self,
        student_logits: Dict[str, torch.Tensor],
        teacher_logits: Dict[str, torch.Tensor],
        current_epoch: Union[int, float],
        alpha: float
    ) -> Tuple[torch.Tensor, Dict[str, any]]:
        """处理字典输入的forward方法 (多个空间关系)"""
        total_loss = 0.0
        losses_per_relation = {}
        num_relations = 0

        for relation_name, student_logit in student_logits.items():
            if relation_name not in teacher_logits:
                continue

            teacher_logit = teacher_logits[relation_name]

            # 计算软标签概率分布
            p_teacher = F.softmax(teacher_logit / self.temperature, dim=-1)
            p_student = F.softmax(student_logit / self.temperature, dim=-1)

            # 计算该关系的Forward KL和Reverse KL
            forward_kl = self.compute_forward_kl(p_teacher, p_student)
            reverse_kl = self.compute_reverse_kl(p_teacher, p_student)

            # 混合损失
            relation_loss = (alpha * forward_kl + (1 - alpha) * reverse_kl)

            # 记录每个关系的损失详情
            losses_per_relation[relation_name] = {
                'forward_kl': forward_kl.item() if torch.is_tensor(forward_kl) else forward_kl,
                'reverse_kl': reverse_kl.item() if torch.is_tensor(reverse_kl) else reverse_kl,
                'loss': relation_loss.item() if torch.is_tensor(relation_loss) else relation_loss,
                'alpha': alpha
            }

            total_loss += relation_loss
            num_relations += 1

        # 温度平方归一化
        total_loss = total_loss / (self.temperature ** 2)

        # 平均归一化
        if num_relations > 0:
            total_loss = total_loss / num_relations

        # 返回损失和信息字典
        info_dict = {
            'forward_kl': sum(v['forward_kl'] for v in losses_per_relation.values()) / num_relations,
            'reverse_kl': sum(v['reverse_kl'] for v in losses_per_relation.values()) / num_relations,
            'alpha': alpha,
            'epoch': current_epoch,
            'temperature': self.temperature,
            'num_relations': num_relations,
            'losses_per_relation': losses_per_relation
        }

        return total_loss, info_dict

    def get_training_schedule(self) -> Dict[int, float]:
        """
        获取完整的训练调度表

        Returns:
            字典: {epoch: alpha_value}
        """
        schedule = {}
        for epoch in range(self.total_epochs + 1):
            schedule[epoch] = self.get_alpha(epoch)
        return schedule


class AdaptiveHybridKLLoss(HybridKLDistillationLoss):
    """
    自适应混合KL损失

    在HybridKLDistillationLoss基础上，支持根据训练指标自动调整参数。
    """

    def __init__(
        self,
        temperature: float = 2.0,
        alpha_start: float = 0.7,
        alpha_end: float = 0.3,
        total_epochs: int = 3,
        use_cosine_schedule: bool = False,
        enable_temperature_decay: bool = True,
        min_temperature: float = 1.0
    ):
        """
        初始化自适应混合KL损失

        Args:
            temperature: 初始温度参数
            alpha_start: 训练初始时的α值
            alpha_end: 训练结束时的α值
            total_epochs: 总训练轮次
            use_cosine_schedule: 是否使用余弦衰减调度
            enable_temperature_decay: 是否启用温度衰减
            min_temperature: 最小温度值
        """
        super().__init__(
            temperature=temperature,
            alpha_start=alpha_start,
            alpha_end=alpha_end,
            total_epochs=total_epochs,
            use_cosine_schedule=use_cosine_schedule
        )
        self.enable_temperature_decay = enable_temperature_decay
        self.min_temperature = min_temperature
        self.initial_temperature = temperature

    def get_temperature(self, current_epoch: Union[int, float]) -> float:
        """
        根据当前epoch获取温度值

        温度线性衰减: T(epoch) = T_start + (T_end - T_start) × (epoch / total_epochs)

        Args:
            current_epoch: 当前训练轮次

        Returns:
            当前epoch的温度值
        """
        if not self.enable_temperature_decay:
            return self.temperature

        epoch_clamped = max(0, min(current_epoch, self.total_epochs))
        progress = epoch_clamped / self.total_epochs
        temp = self.initial_temperature + (self.min_temperature - self.initial_temperature) * progress
        return float(temp)

    def forward(
        self,
        student_logits: Union[torch.Tensor, Dict[str, torch.Tensor]],
        teacher_logits: Union[torch.Tensor, Dict[str, torch.Tensor]],
        current_epoch: Union[int, float] = 0
    ) -> Tuple[torch.Tensor, Dict[str, any]]:
        """
        计算自适应混合KL损失

        与父类相比，同时支持α和温度的动态调整
        """
        # 更新温度
        if self.enable_temperature_decay:
            self.temperature = self.get_temperature(current_epoch)

        # 调用父类的forward方法
        return super().forward(student_logits, teacher_logits, current_epoch)


# 便捷函数
def create_hybrid_kl_loss(
    strategy: str = 'linear',
    temperature: float = 2.0,
    total_epochs: int = 3
) -> HybridKLDistillationLoss:
    """
    创建混合KL损失函数的便捷工厂函数

    Args:
        strategy: 调度策略
            - 'linear': 线性衰减 (默认)
            - 'cosine': 余弦衰减
            - 'adaptive': 自适应 (支持温度衰减)
        temperature: 初始温度参数
        total_epochs: 总训练轮次

    Returns:
        混合KL损失实例
    """
    if strategy == 'linear':
        return HybridKLDistillationLoss(
            temperature=temperature,
            total_epochs=total_epochs,
            use_cosine_schedule=False
        )
    elif strategy == 'cosine':
        return HybridKLDistillationLoss(
            temperature=temperature,
            total_epochs=total_epochs,
            use_cosine_schedule=True
        )
    elif strategy == 'adaptive':
        return AdaptiveHybridKLLoss(
            temperature=temperature,
            total_epochs=total_epochs,
            enable_temperature_decay=True
        )
    else:
        raise ValueError(f"Unknown strategy: {strategy}. "
                        f"Choose from: 'linear', 'cosine', 'adaptive'")
