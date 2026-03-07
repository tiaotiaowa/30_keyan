"""
C2: 空间思维链蒸馏损失 (Spatial Chain-of-Thought Distillation Loss)

通过蒸馏推理过程中的中间步骤来提升学生模型的空间推理能力。

关键特性:
- 1/n归一化: chain_loss = (1/n) × Σ kl_loss(step_i)
- 支持多步骤推理链的蒸馏
- 每个步骤独立计算KL散度
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple


class SpatialChainOfThoughtLoss(nn.Module):
    """
    空间思维链蒸馏损失

    蒸馏空间推理的多步骤链式过程:
    1. 实体识别
    2. 关系抽取
    3. 推理链构建
    4. 最终答案生成

    使用1/n归一化确保不同长度的推理链可以公平比较。
    """

    def __init__(
        self,
        temperature: float = 4.0,
        step_weights: Optional[List[float]] = None,
        use_1n_normalization: bool = True,
        lambda_cot: float = 0.5,
        lambda_final: float = 0.5
    ):
        """
        初始化空间思维链蒸馏损失

        Args:
            temperature: 软标签温度参数
            step_weights: 各推理步骤的权重列表
            use_1n_normalization: 是否使用1/n归一化
            lambda_cot: 推理链损失权重
            lambda_final: 最终答案损失权重
        """
        super().__init__()
        self.temperature = temperature
        self.use_1n_normalization = use_1n_normalization
        self.lambda_cot = lambda_cot
        self.lambda_final = lambda_final

        if step_weights is not None:
            self.step_weights = torch.tensor(step_weights)
        else:
            self.step_weights = None

    def compute_step_kl_loss(
        self,
        student_step: torch.Tensor,
        teacher_step: torch.Tensor
    ) -> torch.Tensor:
        """
        计算单个推理步骤的KL散度损失

        Args:
            student_step: 学生模型在某步骤的输出 (batch_size, num_classes)
            teacher_step: 教师模型在某步骤的输出 (batch_size, num_classes)

        Returns:
            该步骤的KL散度损失
        """
        # 计算软标签概率分布
        p_teacher = F.softmax(teacher_step / self.temperature, dim=-1)
        p_student = F.softmax(student_step / self.temperature, dim=-1)

        # KL散度: KL(P_T || P_S)
        kl_loss = F.kl_div(
            p_student.log(),
            p_teacher,
            reduction='batchmean'
        )

        return kl_loss

    def compute_chain_loss(
        self,
        student_steps: List[torch.Tensor],
        teacher_steps: List[torch.Tensor]
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        计算推理链损失 (带1/n归一化)

        公式: L_chain = (1/n) × Σ_{i=1}^{n} w_i × KL(P_T^i || P_S^i)

        其中:
        - n: 推理链步骤数
        - w_i: 第i步的权重 (可选)
        - KL: KL散度

        Args:
            student_steps: 学生模型的推理步骤输出列表
            teacher_steps: 教师模型的推理步骤输出列表

        Returns:
            chain_loss: 推理链损失
            step_losses: 各步骤的损失详情
        """
        n = len(student_steps)

        if n != len(teacher_steps):
            raise ValueError(
                f"Number of steps mismatch: "
                f"student has {n}, teacher has {len(teacher_steps)}"
            )

        if n == 0:
            return torch.tensor(0.0), {}

        step_losses = {}
        total_weighted_loss = 0.0
        total_weight = 0.0

        for i, (student_step, teacher_step) in enumerate(
            zip(student_steps, teacher_steps)
        ):
            step_loss = self.compute_step_kl_loss(student_step, teacher_step)

            # 获取步骤权重
            if self.step_weights is not None and i < len(self.step_weights):
                weight = self.step_weights[i]
            else:
                weight = 1.0

            step_losses[f'step_{i}'] = {
                'loss': step_loss.item(),
                'weight': weight.item() if isinstance(weight, torch.Tensor) else weight
            }

            total_weighted_loss += step_loss * weight
            total_weight += weight

        # 计算加权平均损失
        if total_weight > 0:
            chain_loss = total_weighted_loss / total_weight
        else:
            chain_loss = total_weighted_loss / n

        # 温度平方归一化
        chain_loss = chain_loss / (self.temperature ** 2)

        # 关键: 1/n归一化
        # 这确保了不同长度的推理链可以公平比较
        if self.use_1n_normalization:
            chain_loss = chain_loss / n

        return chain_loss, step_losses

    def compute_final_loss(
        self,
        student_final: torch.Tensor,
        teacher_final: torch.Tensor,
        targets: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        计算最终答案的蒸馏损失

        Args:
            student_final: 学生模型的最终输出
            teacher_final: 教师模型的最终输出
            targets: 真实标签 (可选，用于混合损失)

        Returns:
            final_loss: 最终答案损失
            loss_details: 损失详情
        """
        # 软标签蒸馏损失
        p_teacher = F.softmax(teacher_final / self.temperature, dim=-1)
        p_student = F.softmax(student_final / self.temperature, dim=-1)

        distill_loss = F.kl_div(
            p_student.log(),
            p_teacher,
            reduction='batchmean'
        ) / (self.temperature ** 2)

        loss_details = {'distill_loss': distill_loss.item()}

        # 如果提供了真实标签，计算混合损失
        if targets is not None:
            # 硬标签交叉熵损失
            ce_loss = F.cross_entropy(student_final, targets)

            # Alpha蒸馏: 混合软标签和硬标签损失
            alpha = 0.5
            final_loss = alpha * distill_loss + (1 - alpha) * ce_loss
            loss_details['ce_loss'] = ce_loss.item()
            loss_details['alpha'] = alpha
        else:
            final_loss = distill_loss

        return final_loss, loss_details

    def forward(
        self,
        student_output: Dict[str, torch.Tensor],
        teacher_output: Dict[str, torch.Tensor],
        targets: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, Dict[str, any]]:
        """
        计算空间思维链蒸馏总损失

        Args:
            student_output: 学生模型输出字典
                {
                    'chain_steps': [step1, step2, ...],  # 推理链步骤
                    'final': final_output                 # 最终输出
                }
            teacher_output: 教师模型输出字典 (格式同上)
            targets: 真实标签 (可选)

        Returns:
            total_loss: 总损失
            loss_info: 损失详情
        """
        student_chain = student_output.get('chain_steps', [])
        teacher_chain = teacher_output.get('chain_steps', [])

        # 计算推理链损失
        if len(student_chain) > 0 and len(teacher_chain) > 0:
            chain_loss, step_losses = self.compute_chain_loss(
                student_chain, teacher_chain
            )
        else:
            chain_loss = torch.tensor(0.0, device=student_output['final'].device)
            step_losses = {}

        # 计算最终答案损失
        final_loss, final_details = self.compute_final_loss(
            student_output['final'],
            teacher_output['final'],
            targets
        )

        # 组合总损失
        total_loss = (
            self.lambda_cot * chain_loss +
            self.lambda_final * final_loss
        )

        loss_info = {
            'total_loss': total_loss.item(),
            'chain_loss': chain_loss.item() if isinstance(chain_loss, torch.Tensor) else chain_loss,
            'final_loss': final_loss.item(),
            'lambda_cot': self.lambda_cot,
            'lambda_final': self.lambda_final,
            'num_steps': len(student_chain),
            '1n_normalization': self.use_1n_normalization,
            'step_losses': step_losses,
            'final_details': final_details
        }

        return total_loss, loss_info


class SpatialReasoningChainLoss(nn.Module):
    """
    空间推理链损失 (简化版)

    专注于空间关系推理的核心步骤
    """

    # 标准空间推理步骤
    REASONING_STEPS = [
        'entity_identification',    # 实体识别
        'spatial_relation',          # 空间关系抽取
        'relation_classification',   # 关系分类
        'spatial_inference',         # 空间推理
        'answer_generation'          # 答案生成
    ]

    def __init__(
        self,
        temperature: float = 4.0,
        use_1n_normalization: bool = True,
        step_weights: Optional[Dict[str, float]] = None
    ):
        """
        初始化空间推理链损失

        Args:
            temperature: 温度参数
            use_1n_normalization: 是否使用1/n归一化
            step_weights: 各步骤的权重字典
        """
        super().__init__()
        self.temperature = temperature
        self.use_1n_normalization = use_1n_normalization

        # 默认步骤权重
        self.step_weights = {
            'entity_identification': 1.0,
            'spatial_relation': 1.5,    # 空间关系更重要
            'relation_classification': 1.2,
            'spatial_inference': 2.0,   # 推理最重要
            'answer_generation': 1.0
        }

        if step_weights is not None:
            self.step_weights.update(step_weights)

    def forward(
        self,
        student_logits: Dict[str, torch.Tensor],
        teacher_logits: Dict[str, torch.Tensor]
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        计算空间推理链损失

        Args:
            student_logits: {step_name: logits}
            teacher_logits: {step_name: logits}

        Returns:
            total_loss: 总损失 (带1/n归一化)
            step_losses: 各步骤损失
        """
        n = len(self.REASONING_STEPS)
        total_loss = 0.0
        step_losses = {}
        total_weight = 0.0

        for step in self.REASONING_STEPS:
            if step not in student_logits or step not in teacher_logits:
                continue

            # 计算该步骤的KL散度
            p_teacher = F.softmax(
                teacher_logits[step] / self.temperature, dim=-1
            )
            p_student = F.softmax(
                student_logits[step] / self.temperature, dim=-1
            )

            step_loss = F.kl_div(
                p_student.log(),
                p_teacher,
                reduction='batchmean'
            )

            weight = self.step_weights.get(step, 1.0)
            total_loss += step_loss * weight
            total_weight += weight

            step_losses[step] = {
                'loss': step_loss.item(),
                'weight': weight
            }

        # 温度归一化
        total_loss = total_loss / (self.temperature ** 2)

        # 权重归一化
        if total_weight > 0:
            total_loss = total_loss / total_weight

        # 关键: 1/n归一化
        if self.use_1n_normalization and n > 0:
            total_loss = total_loss / n

        return total_loss, step_losses


class AdaptiveChainLengthLoss(SpatialChainOfThoughtLoss):
    """
    自适应推理链长度损失

    根据模型能力动态调整推理链长度
    """

    def __init__(
        self,
        initial_steps: int = 5,
        max_steps: int = 10,
        min_steps: int = 2,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.initial_steps = initial_steps
        self.max_steps = max_steps
        self.min_steps = min_steps
        self.current_steps = initial_steps

    def adjust_chain_length(self, performance: float):
        """
        根据模型表现调整推理链长度

        Args:
            performance: 模型表现指标 (0-1)
        """
        if performance > 0.9 and self.current_steps < self.max_steps:
            self.current_steps += 1
        elif performance < 0.7 and self.current_steps > self.min_steps:
            self.current_steps -= 1

    def truncate_chain(
        self,
        chain: List[torch.Tensor]
    ) -> List[torch.Tensor]:
        """
        截断或填充推理链到当前长度

        Args:
            chain: 原始推理链

        Returns:
            调整后的推理链
        """
        if len(chain) <= self.current_steps:
            return chain

        return chain[:self.current_steps]
