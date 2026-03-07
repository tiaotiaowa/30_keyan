"""
C6: 渐进式蒸馏损失 (Progressive Distillation Loss)

将蒸馏过程压缩为3个epoch，每个epoch处理不同复杂度的空间关系。

核心思想:
- 从简单到复杂逐步蒸馏空间关系知识
- Epoch 1: 简单关系 (拓扑关系的基础类型)
- Epoch 2: 中等关系 (方向和距离)
- Epoch 3: 复杂关系 (多层嵌套和推理)

优势:
1. 大幅减少训练时间 (3 epoch vs 传统100+ epoch)
2. 渐进式学习避免灾难性遗忘
3. 每个阶段专注于特定难度
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple, Union


class ProgressiveDistillationLoss(nn.Module):
    """
    渐进式蒸馏损失

    3 epoch渐进式训练策略:
    - Epoch 1: 简单空间关系
    - Epoch 2: 中等空间关系
    - Epoch 3: 复杂空间关系
    """

    # 空间关系复杂度分类
    RELATION_COMPLEXITY = {
        # Epoch 1: 简单关系
        'simple': [
            'adjacent',        # 相邻
            'disjoint',        # 相离
            'equal',           # 相等
            'inside',          # 内部
        ],
        # Epoch 2: 中等关系
        'medium': [
            'north', 'south', 'east', 'west',  # 基本方向
            'near', 'far',                         # 相对距离
            'overlap',                              # 重叠
            'contains',                             # 包含
        ],
        # Epoch 3: 复杂关系
        'complex': [
            'northeast', 'northwest', 'southeast', 'southwest',  # 复合方向
            'very_near', 'very_far',                               # 精细距离
            'partially_overlaps',                                  # 部分重叠
            'touches',                                             # 接触
            'crosses',                                             # 交叉
            'multi_hop_relation',                                  # 多跳推理
        ]
    }

    def __init__(
        self,
        total_epochs: int = 3,
        temperature: float = 4.0,
        lambda_simple: float = 1.0,
        lambda_medium: float = 1.2,
        lambda_complex: float = 1.5,
        use_curriculum: bool = True
    ):
        """
        初始化渐进式蒸馏损失

        Args:
            total_epochs: 总训练轮次 (默认3)
            temperature: 温度参数
            lambda_simple: 简单关系权重
            lambda_medium: 中等关系权重
            lambda_complex: 复杂关系权重
            use_curriculum: 是否使用课程学习策略
        """
        super().__init__()
        self.total_epochs = total_epochs
        self.temperature = temperature
        self.lambda_simple = lambda_simple
        self.lambda_medium = lambda_medium
        self.lambda_complex = lambda_complex
        self.use_curriculum = use_curriculum

        self.current_epoch = 0

        # 构建关系到复杂度的映射
        self.relation_to_complexity = {}
        for complexity, relations in self.RELATION_COMPLEXITY.items():
            for rel in relations:
                self.relation_to_complexity[rel] = complexity

    def set_epoch(self, epoch: int):
        """
        设置当前训练轮次

        Args:
            epoch: 当前轮次 (0-indexed)
        """
        self.current_epoch = epoch

    def get_active_relations(self) -> List[str]:
        """
        获取当前epoch应该训练的关系类型

        Returns:
            当前阶段的关系列表
        """
        if self.current_epoch == 0:
            return self.RELATION_COMPLEXITY['simple']
        elif self.current_epoch == 1:
            # 第二阶段: 简单 + 中等
            return (
                self.RELATION_COMPLEXITY['simple'] +
                self.RELATION_COMPLEXITY['medium']
            )
        else:
            # 第三阶段及以后: 全部
            return (
                self.RELATION_COMPLEXITY['simple'] +
                self.RELATION_COMPLEXITY['medium'] +
                self.RELATION_COMPLEXITY['complex']
            )

    def get_relation_weight(self, relation_name: str) -> float:
        """
        获取关系的权重

        Args:
            relation_name: 关系名称

        Returns:
            权重值
        """
        complexity = self.relation_to_complexity.get(
            relation_name,
            'simple'  # 默认为简单
        )

        if complexity == 'simple':
            return self.lambda_simple
        elif complexity == 'medium':
            return self.lambda_medium
        else:
            return self.lambda_complex

    def compute_kl_loss(
        self,
        p_teacher: torch.Tensor,
        p_student: torch.Tensor,
        weight: float = 1.0
    ) -> torch.Tensor:
        """
        计算加权KL散度损失

        Args:
            p_teacher: 教师概率分布
            p_student: 学生概率分布
            weight: 关系权重

        Returns:
            KL损失
        """
        kl_div = F.kl_div(
            p_student.log(),
            p_teacher,
            reduction='batchmean'
        )

        return kl_div * weight / (self.temperature ** 2)

    def forward(
        self,
        student_logits: Dict[str, torch.Tensor],
        teacher_logits: Dict[str, torch.Tensor],
        relation_types: Optional[Dict[str, str]] = None
    ) -> Tuple[torch.Tensor, Dict[str, any]]:
        """
        计算渐进式蒸馏损失

        Args:
            student_logits: 学生模型logits {relation_name: logits}
            teacher_logits: 教师模型logits {relation_name: logits}
            relation_types: 可选的关系类型映射

        Returns:
            total_loss: 总损失
            loss_info: 损失详情
        """
        # 获取当前阶段应该训练的关系
        active_relations = self.get_active_relations()

        total_loss = 0.0
        relation_losses = {}
        total_weight = 0.0
        active_count = 0

        for rel_name, student_logit in student_logits.items():
            if rel_name not in teacher_logits:
                continue

            teacher_logit = teacher_logits[rel_name]

            # 检查是否在当前阶段的关系列表中
            is_active = any(
                rel_name.startswith(active_rel) or
                active_rel in rel_name.lower()
                for active_rel in active_relations
            )

            if not is_active and self.use_curriculum:
                # 不在当前阶段，跳过
                continue

            active_count += 1

            # 计算软标签概率
            p_teacher = F.softmax(teacher_logit / self.temperature, dim=-1)
            p_student = F.softmax(student_logit / self.temperature, dim=-1)

            # 获取权重
            weight = self.get_relation_weight(rel_name)

            # 计算KL损失
            rel_loss = self.compute_kl_loss(p_teacher, p_student, weight)

            # 记录损失
            relation_losses[rel_name] = {
                'loss': rel_loss.item(),
                'weight': weight,
                'complexity': self.relation_to_complexity.get(rel_name, 'unknown')
            }

            total_loss += rel_loss
            total_weight += weight

        # 归一化
        if total_weight > 0:
            total_loss = total_loss / total_weight

        loss_info = {
            'epoch': self.current_epoch,
            'total_loss': total_loss.item() if isinstance(total_loss, torch.Tensor) else total_loss,
            'active_relations': active_relations,
            'active_count': active_count,
            'relation_losses': relation_losses,
            'phase': self.get_phase_name()
        }

        return total_loss, loss_info

    def get_phase_name(self) -> str:
        """获取当前阶段名称"""
        if self.current_epoch == 0:
            return "Phase 1: Simple Relations"
        elif self.current_epoch == 1:
            return "Phase 2: Medium Relations"
        else:
            return "Phase 3: Complex Relations"


class DynamicProgressiveLoss(ProgressiveDistillationLoss):
    """
    动态渐进式损失

    根据模型表现动态调整关系训练顺序。
    """

    def __init__(
        self,
        performance_threshold: float = 0.8,
        min_samples_per_relation: int = 100,
        **kwargs
    ):
        """
        初始化动态渐进式损失

        Args:
            performance_threshold: 性能阈值，超过则进入下一阶段
            min_samples_per_relation: 每种关系的最小样本数
            **kwargs: 其他参数
        """
        super().__init__(**kwargs)
        self.performance_threshold = performance_threshold
        self.min_samples_per_relation = min_samples_per_relation
        self.relation_performance = {}

        # 初始化性能记录
        for complexity, relations in self.RELATION_COMPLEXITY.items():
            for rel in relations:
                self.relation_performance[rel] = {
                    'correct': 0,
                    'total': 0,
                    'performance': 0.0
                }

    def update_performance(
        self,
        relation_name: str,
        predictions: torch.Tensor,
        targets: torch.Tensor
    ):
        """
        更新关系性能统计

        Args:
            relation_name: 关系名称
            predictions: 预测结果
            targets: 真实标签
        """
        if relation_name not in self.relation_performance:
            self.relation_performance[relation_name] = {
                'correct': 0,
                'total': 0,
                'performance': 0.0
            }

        # 计算准确率
        correct = (predictions == targets).sum().item()
        total = targets.size(0)

        stats = self.relation_performance[relation_name]
        stats['correct'] += correct
        stats['total'] += total
        stats['performance'] = stats['correct'] / stats['total']

    def should_advance_phase(self) -> bool:
        """
        判断是否应该进入下一阶段

        Returns:
            是否应该进入下一阶段
        """
        # 获取当前阶段的关系
        current_relations = self.get_active_relations()

        # 检查每种关系的性能
        for rel in current_relations:
            stats = self.relation_performance.get(rel, {})
            perf = stats.get('performance', 0.0)
            total = stats.get('total', 0)

            # 如果性能不够或样本不足，不进入下一阶段
            if perf < self.performance_threshold or total < self.min_samples_per_relation:
                return False

        return True

    def forward(self, *args, **kwargs):
        """
        带动态阶段调整的前向传播
        """
        # 检查是否应该进入下一阶段
        if self.should_advance_phase() and self.current_epoch < self.total_epochs - 1:
            self.current_epoch += 1

        return super().forward(*args, **kwargs)


class AdaptiveTemperatureProgressiveLoss(ProgressiveDistillationLoss):
    """
    自适应温度的渐进式损失

    根据训练阶段动态调整温度参数。
    """

    def __init__(
        self,
        initial_temperature: float = 8.0,
        final_temperature: float = 2.0,
        **kwargs
    ):
        """
        初始化自适应温度渐进式损失

        Args:
            initial_temperature: 初始温度
            final_temperature: 最终温度
            **kwargs: 其他参数
        """
        # 暂时设置温度，后面会动态更新
        super().__init__(temperature=initial_temperature, **kwargs)
        self.initial_temperature = initial_temperature
        self.final_temperature = final_temperature

    def update_temperature(self):
        """根据当前epoch更新温度"""
        progress = self.current_epoch / max(self.total_epochs - 1, 1)

        # 线性衰减
        self.temperature = (
            self.initial_temperature * (1 - progress) +
            self.final_temperature * progress
        )

    def set_epoch(self, epoch: int):
        """设置epoch并更新温度"""
        super().set_epoch(epoch)
        self.update_temperature()


class ProgressiveDistillationScheduler:
    """
    渐进式蒸馏调度器

    管理训练过程中的阶段转换和参数调整。
    """

    def __init__(
        self,
        loss_fn: ProgressiveDistillationLoss,
        optimizer: torch.optim.Optimizer,
        total_epochs: int = 3
    ):
        """
        初始化调度器

        Args:
            loss_fn: 渐进式损失函数
            optimizer: 优化器
            total_epochs: 总训练轮次
        """
        self.loss_fn = loss_fn
        self.optimizer = optimizer
        self.total_epochs = total_epochs

    def step_epoch(self, epoch: int):
        """
        执行一个epoch的步骤

        Args:
            epoch: 当前轮次
        """
        # 更新损失函数的epoch
        self.loss_fn.set_epoch(epoch)

        # 根据阶段调整学习率
        if epoch == 1:
            # 第二阶段: 降低学习率
            for param_group in self.optimizer.param_groups:
                param_group['lr'] *= 0.5
        elif epoch == 2:
            # 第三阶段: 再次降低
            for param_group in self.optimizer.param_groups:
                param_group['lr'] *= 0.5

    def get_training_info(self) -> Dict[str, any]:
        """
        获取当前训练信息

        Returns:
            训练信息字典
        """
        return {
            'epoch': self.loss_fn.current_epoch,
            'phase': self.loss_fn.get_phase_name(),
            'active_relations': self.loss_fn.get_active_relations(),
            'temperature': getattr(self.loss_fn, 'temperature', 4.0)
        }


class MultiTaskProgressiveLoss(ProgressiveDistillationLoss):
    """
    多任务渐进式损失

    在处理空间关系的同时处理其他任务。
    """

    def __init__(
        self,
        task_weights: Dict[str, float] = None,
        **kwargs
    ):
        """
        初始化多任务渐进式损失

        Args:
            task_weights: 各任务权重
            **kwargs: 其他参数
        """
        super().__init__(**kwargs)

        # 默认任务权重
        self.task_weights = task_weights or {
            'relation_extraction': 1.0,
            'entity_recognition': 0.5,
            'spatial_reasoning': 1.2,
            'answer_generation': 0.8
        }

    def forward(
        self,
        student_outputs: Dict[str, Dict[str, torch.Tensor]],
        teacher_outputs: Dict[str, Dict[str, torch.Tensor]]
    ) -> Tuple[torch.Tensor, Dict[str, any]]:
        """
        计算多任务渐进式损失

        Args:
            student_outputs: 学生模型输出 {task_name: {relation_name: logits}}
            teacher_outputs: 教师模型输出 {task_name: {relation_name: logits}}

        Returns:
            total_loss: 总损失
            loss_info: 损失详情
        """
        total_loss = 0.0
        task_losses = {}

        for task_name, student_task_out in student_outputs.items():
            if task_name not in teacher_outputs:
                continue

            teacher_task_out = teacher_outputs[task_name]
            task_weight = self.task_weights.get(task_name, 1.0)

            # 计算该任务的损失
            task_loss, task_loss_info = super().forward(
                student_task_out,
                teacher_task_out
            )

            task_losses[task_name] = {
                'loss': task_loss.item() if isinstance(task_loss, torch.Tensor) else task_loss,
                'weight': task_weight,
                'weighted_loss': (task_loss * task_weight).item() if isinstance(task_loss, torch.Tensor) else task_loss * task_weight,
                'details': task_loss_info
            }

            total_loss += task_loss * task_weight

        # 归一化
        total_weight = sum(
            self.task_weights.get(t, 1.0)
            for t in student_outputs.keys()
        )
        if total_weight > 0:
            total_loss = total_loss / total_weight

        loss_info = {
            'total_loss': total_loss.item() if isinstance(total_loss, torch.Tensor) else total_loss,
            'task_losses': task_losses,
            'epoch': self.current_epoch,
            'phase': self.get_phase_name()
        }

        return total_loss, loss_info
