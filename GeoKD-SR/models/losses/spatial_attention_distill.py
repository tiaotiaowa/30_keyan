"""
C5: 空间关系注意力蒸馏损失 (Spatial Attention Distillation Loss)

蒸馏空间关系推理中的注意力分布，使学生模型学习教师模型关注的空间模式。

核心思想:
- 注意力图反映了模型在做空间推理时关注哪些区域/实体
- 蒸馏注意力图可以传递空间推理的"关注模式"
- 公式: L_attn = MSE(Attn_T, Attn_S) 或 KL(Attn_T, Attn_S)

应用场景:
- 空间关系分类
- 空间推理链的注意力对齐
- 多模态空间理解
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple, Union


class SpatialAttentionDistillLoss(nn.Module):
    """
    空间注意力蒸馏损失

    蒸馏空间关系推理中的注意力分布。
    """

    def __init__(
        self,
        loss_type: str = 'mse',
        temperature: float = 4.0,
        lambda_attn: float = 0.5,
        epsilon: float = 1e-8
    ):
        """
        初始化空间注意力蒸馏损失

        Args:
            loss_type: 损失类型 ('mse', 'kl', 'cosine')
            temperature: KL散度的温度参数
            lambda_attn: 注意力损失的权重
            epsilon: 数值稳定性常数
        """
        super().__init__()
        self.loss_type = loss_type
        self.temperature = temperature
        self.lambda_attn = lambda_attn
        self.epsilon = epsilon

    def compute_mse_loss(
        self,
        teacher_attn: torch.Tensor,
        student_attn: torch.Tensor
    ) -> torch.Tensor:
        """
        计算MSE损失

        Args:
            teacher_attn: 教师注意力图 (B, H, W) 或 (B, L)
            student_attn: 学生注意力图 (B, H, W) 或 (B, L)

        Returns:
            MSE损失
        """
        return F.mse_loss(student_attn, teacher_attn)

    def compute_kl_loss(
        self,
        teacher_attn: torch.Tensor,
        student_attn: torch.Tensor
    ) -> torch.Tensor:
        """
        计算KL散度损失

        Args:
            teacher_attn: 教师注意力图 (作为概率分布)
            student_attn: 学生注意力图 (作为概率分布)

        Returns:
            KL散度损失
        """
        # 归一化为概率分布
        if teacher_attn.dim() == 3:  # (B, H, W)
            teacher_attn = teacher_attn.flatten(1)
            student_attn = student_attn.flatten(1)

        teacher_attn = F.softmax(teacher_attn / self.temperature, dim=-1)
        student_attn = F.softmax(student_attn / self.temperature, dim=-1)

        # 数值稳定性
        teacher_attn = torch.clamp(teacher_attn, min=self.epsilon, max=1.0)
        student_attn = torch.clamp(student_attn, min=self.epsilon, max=1.0)

        # KL散度
        kl_div = teacher_attn * (torch.log(teacher_attn) - torch.log(student_attn))
        return kl_div.sum(dim=-1).mean() / (self.temperature ** 2)

    def compute_cosine_loss(
        self,
        teacher_attn: torch.Tensor,
        student_attn: torch.Tensor
    ) -> torch.Tensor:
        """
        计算余弦相似度损失 (1 - cosine_similarity)

        Args:
            teacher_attn: 教师注意力图
            student_attn: 学生注意力图

        Returns:
            余弦损失
        """
        # 展平
        if teacher_attn.dim() == 3:
            teacher_attn = teacher_attn.flatten(1)
            student_attn = student_attn.flatten(1)

        # 计算余弦相似度
        cosine_sim = F.cosine_similarity(
            teacher_attn, student_attn, dim=-1
        )

        # 损失 = 1 - 相似度
        return (1 - cosine_sim).mean()

    def forward(
        self,
        teacher_attention: Dict[str, torch.Tensor],
        student_attention: Dict[str, torch.Tensor]
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        计算空间注意力蒸馏损失

        Args:
            teacher_attention: 教师注意力图字典
                {layer_name: attention_map}
            student_attention: 学生注意力图字典
                {layer_name: attention_map}

        Returns:
            total_loss: 总注意力损失
            loss_dict: 各层的损失详情
        """
        total_loss = 0.0
        num_layers = 0
        loss_dict = {}

        for layer_name, t_attn in teacher_attention.items():
            if layer_name not in student_attention:
                continue

            s_attn = student_attention[layer_name]

            # 根据损失类型计算
            if self.loss_type == 'mse':
                layer_loss = self.compute_mse_loss(t_attn, s_attn)
            elif self.loss_type == 'kl':
                layer_loss = self.compute_kl_loss(t_attn, s_attn)
            elif self.loss_type == 'cosine':
                layer_loss = self.compute_cosine_loss(t_attn, s_attn)
            else:
                raise ValueError(f"Unknown loss type: {self.loss_type}")

            loss_dict[layer_name] = layer_loss.item()
            total_loss += layer_loss
            num_layers += 1

        # 平均
        if num_layers > 0:
            total_loss = total_loss / num_layers

        total_loss = self.lambda_attn * total_loss
        loss_dict['total'] = total_loss.item() if isinstance(total_loss, torch.Tensor) else total_loss
        loss_dict['lambda_attn'] = self.lambda_attn

        return total_loss, loss_dict


class MultiHeadSpatialAttentionLoss(nn.Module):
    """
    多头空间注意力蒸馏损失

    处理Transformer多头注意力的蒸馏。
    """

    def __init__(
        self,
        loss_type: str = 'mse',
        temperature: float = 4.0,
        aggregate_heads: str = 'mean'
    ):
        """
        初始化多头注意力蒸馏损失

        Args:
            loss_type: 损失类型 ('mse', 'kl')
            temperature: 温度参数
            aggregate_heads: 头聚合方式 ('mean', 'max', 'sum')
        """
        super().__init__()
        self.loss_type = loss_type
        self.temperature = temperature
        self.aggregate_heads = aggregate_heads

    def forward(
        self,
        teacher_attn: torch.Tensor,
        student_attn: torch.Tensor
    ) -> torch.Tensor:
        """
        计算多头注意力蒸馏损失

        Args:
            teacher_attn: 教师多头注意力 (B, num_heads, H, W) 或 (B, num_heads, L, L)
            student_attn: 学生多头注意力 (B, num_heads, H, W) 或 (B, num_heads, L, L)

        Returns:
            蒸馏损失
        """
        # 头数量可能不同，取最小值
        min_heads = min(teacher_attn.size(1), student_attn.size(1))
        teacher_attn = teacher_attn[:, :min_heads]
        student_attn = student_attn[:, :min_heads]

        # 计算每个头的损失
        head_losses = []

        for i in range(min_heads):
            t_head = teacher_attn[:, i]
            s_head = student_attn[:, i]

            if self.loss_type == 'mse':
                loss = F.mse_loss(s_head, t_head)
            elif self.loss_type == 'kl':
                # 展平并归一化
                t_flat = t_head.flatten(1)
                s_flat = s_head.flatten(1)

                t_prob = F.softmax(t_flat / self.temperature, dim=-1)
                s_prob = F.softmax(s_flat / self.temperature, dim=-1)

                kl_div = t_prob * (torch.log(t_prob + 1e-8) - torch.log(s_prob + 1e-8))
                loss = kl_div.sum(dim=-1).mean() / (self.temperature ** 2)
            else:
                raise ValueError(f"Unknown loss type: {self.loss_type}")

            head_losses.append(loss)

        # 聚合头的损失
        head_losses = torch.stack(head_losses)

        if self.aggregate_heads == 'mean':
            return head_losses.mean()
        elif self.aggregate_heads == 'max':
            return head_losses.max()
        elif self.aggregate_heads == 'sum':
            return head_losses.sum()
        else:
            raise ValueError(f"Unknown aggregate method: {self.aggregate_heads}")


class SpatialRelationAttentionLoss(nn.Module):
    """
    空间关系注意力损失

    专门针对空间关系任务的注意力蒸馏。
    """

    RELATION_PATTERNS = {
        'adjacency': [1, 0, 0, 0],      # 关注相邻关系
        'containment': [0, 1, 0, 0],    # 关注包含关系
        'direction': [0, 0, 1, 0],      # 关注方向关系
        'distance': [0, 0, 0, 1],       # 关注距离关系
    }

    def __init__(
        self,
        temperature: float = 4.0,
        relation_specific: bool = True
    ):
        """
        初始化空间关系注意力损失

        Args:
            temperature: 温度参数
            relation_specific: 是否为每种关系类型使用特定权重
        """
        super().__init__()
        self.temperature = temperature
        self.relation_specific = relation_specific

        # 为不同关系类型定义目标注意力模式
        self.register_buffer(
            'relation_patterns',
            torch.tensor(list(self.RELATION_PATTERNS.values())).float()
        )

    def forward(
        self,
        student_attention: torch.Tensor,
        relation_types: List[str]
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        计算空间关系注意力损失

        Args:
            student_attention: 学生注意力 (B, num_relations, num_attention_units)
            relation_types: 关系类型列表

        Returns:
            total_loss: 总损失
            pattern_losses: 各模式的损失
        """
        batch_size = student_attention.size(0)
        num_relations = len(relation_types)

        if num_relations == 0:
            return torch.tensor(0.0), {}

        total_loss = 0.0
        pattern_losses = {}

        for i, rel_type in enumerate(relation_types):
            if rel_type not in self.RELATION_PATTERNS:
                continue

            # 获取目标模式
            target_idx = list(self.RELATION_PATTERNS.keys()).index(rel_type)
            target_pattern = self.relation_patterns[target_idx]

            # 学生注意力 (归一化)
            student_attn = F.softmax(
                student_attention[:, i] / self.temperature,
                dim=-1
            )

            # 计算与目标模式的KL散度
            target_pattern = target_pattern.to(student_attention.device)
            target_pattern = target_pattern.unsqueeze(0).expand(batch_size, -1)

            kl_div = target_pattern * (
                torch.log(target_pattern + 1e-8) -
                torch.log(student_attn + 1e-8)
            )

            rel_loss = kl_div.sum(dim=-1).mean() / (self.temperature ** 2)
            pattern_losses[rel_type] = rel_loss
            total_loss += rel_loss

        if num_relations > 0:
            total_loss = total_loss / num_relations

        return total_loss, pattern_losses


class CrossModalSpatialAttentionLoss(nn.Module):
    """
    跨模态空间注意力损失

    蒸馏文本和图像/地图之间的空间注意力对齐。
    """

    def __init__(
        self,
        temperature: float = 4.0,
        lambda_cross: float = 0.5
    ):
        """
        初始化跨模态注意力损失

        Args:
            temperature: 温度参数
            lambda_cross: 跨模态损失的权重
        """
        super().__init__()
        self.temperature = temperature
        self.lambda_cross = lambda_cross

    def compute_alignment_loss(
        self,
        text_attn: torch.Tensor,
        visual_attn: torch.Tensor
    ) -> torch.Tensor:
        """
        计算文本和视觉注意力的对齐损失

        Args:
            text_attn: 文本注意力 (B, L_text)
            visual_attn: 视觉注意力 (B, L_visual)

        Returns:
            对齐损失
        """
        # 归一化
        text_attn = F.softmax(text_attn / self.temperature, dim=-1)
        visual_attn = F.softmax(visual_attn / self.temperature, dim=-1)

        # 计算KL散度 (对称)
        kl_tv = text_attn * (torch.log(text_attn + 1e-8) - torch.log(visual_attn + 1e-8))
        kl_vt = visual_attn * (torch.log(visual_attn + 1e-8) - torch.log(text_attn + 1e-8))

        # 对称KL散度
        sym_kl = 0.5 * (kl_tv.sum(dim=-1).mean() + kl_vt.sum(dim=-1).mean())
        sym_kl = sym_kl / (self.temperature ** 2)

        return sym_kl

    def forward(
        self,
        teacher_text_attn: torch.Tensor,
        teacher_visual_attn: torch.Tensor,
        student_text_attn: torch.Tensor,
        student_visual_attn: torch.Tensor
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        计算跨模态空间注意力蒸馏损失

        Args:
            teacher_text_attn: 教师文本注意力
            teacher_visual_attn: 教师视觉注意力
            student_text_attn: 学生文本注意力
            student_visual_attn: 学生视觉注意力

        Returns:
            total_loss: 总损失
            loss_info: 损失详情
        """
        # 教师跨模态对齐
        teacher_alignment = self.compute_alignment_loss(
            teacher_text_attn, teacher_visual_attn
        )

        # 学生跨模态对齐
        student_alignment = self.compute_alignment_loss(
            student_text_attn, student_visual_attn
        )

        # 蒸馏损失: 让学生对齐接近教师对齐
        distill_loss = F.mse_loss(
            student_text_attn, teacher_text_attn
        ) + F.mse_loss(
            student_visual_attn, teacher_visual_attn
        )

        # 总损失
        total_loss = self.lambda_cross * (
            teacher_alignment + distill_loss + student_alignment
        )

        loss_info = {
            'teacher_alignment': teacher_alignment.item(),
            'student_alignment': student_alignment.item(),
            'distill_loss': distill_loss.item(),
            'total_loss': total_loss.item()
        }

        return total_loss, loss_info


class HierarchicalAttentionLoss(nn.Module):
    """
    层次化注意力损失

    在不同尺度上蒸馏空间注意力。
    """

    def __init__(
        self,
        scales: List[int] = [1, 2, 4, 8],
        temperature: float = 4.0
    ):
        """
        初始化层次化注意力损失

        Args:
            scales: 不同尺度的列表
            temperature: 温度参数
        """
        super().__init__()
        self.scales = scales
        self.temperature = temperature

    def forward(
        self,
        teacher_attn: torch.Tensor,
        student_attn: torch.Tensor
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        计算层次化注意力蒸馏损失

        Args:
            teacher_attn: 教师注意力 (B, C, H, W)
            student_attn: 学生注意力 (B, C, H, W)

        Returns:
            total_loss: 总损失
            scale_losses: 各尺度的损失
        """
        B, C, H, W = teacher_attn.shape
        total_loss = 0.0
        scale_losses = {}

        for scale in self.scales:
            # 下采样到当前尺度
            if scale > 1:
                new_h, new_w = H // scale, W // scale
                t_scaled = F.adaptive_avg_pool2d(teacher_attn, (new_h, new_w))
                s_scaled = F.adaptive_avg_pool2d(student_attn, (new_h, new_w))
            else:
                t_scaled = teacher_attn
                s_scaled = student_attn

            # 归一化
            t_prob = F.softmax(t_scaled.flatten(1) / self.temperature, dim=-1)
            s_prob = F.softmax(s_scaled.flatten(1) / self.temperature, dim=-1)

            # KL散度
            kl_div = t_prob * (torch.log(t_prob + 1e-8) - torch.log(s_prob + 1e-8))
            scale_loss = kl_div.sum(dim=-1).mean() / (self.temperature ** 2)

            scale_losses[f'scale_{scale}'] = scale_loss
            total_loss += scale_loss

        # 平均
        total_loss = total_loss / len(self.scales)

        return total_loss, scale_losses
