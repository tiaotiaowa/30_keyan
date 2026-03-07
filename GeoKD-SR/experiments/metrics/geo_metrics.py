"""
地理特异性评测指标模块

提供用于评估地理空间推理模型性能的专门指标函数。

主要指标类别：
1. 方向相关指标：direction_error_rate, direction_accuracy, direction_confusion_matrix
2. 拓扑关系指标：topology_confusion_matrix, topology_classification_report
3. 距离相关指标：distance_mape, distance_mae, distance_rmse
4. 空间关系提取指标：spatial_relation_f1, spatial_relation_precision, spatial_relation_recall
5. 推理链指标：reasoning_accuracy, reasoning_step_accuracy, reasoning_chain_completeness
"""

import math
import json
from typing import Dict, List, Tuple, Any, Union, Optional
from collections import defaultdict
from dataclasses import dataclass, field
import numpy as np


# ==================== 常量定义 ====================

# 八方位方向定义
DIRECTIONS_8 = ["东", "东南", "南", "西南", "西", "西北", "北", "东北"]

# 方向相邻关系（用于计算相邻方向容错）
ADJACENT_DIRECTIONS = {
    "东": ["东北", "东南"],
    "南": ["东南", "西南"],
    "西": ["西南", "西北"],
    "北": ["西北", "东北"],
    "东北": ["东", "北"],
    "东南": ["东", "南"],
    "西北": ["西", "北"],
    "西南": ["西", "南"]
}

# 拓扑关系类型
TOPOLOGY_TYPES = ["包含", "相邻", "相交", "相离"]

# 空间关系类型
SPATIAL_RELATION_TYPES = ["方向", "拓扑", "度量"]


# ==================== 方向相关指标 ====================

def direction_error_rate(
    predictions: List[str],
    ground_truth: List[str],
    allow_adjacent: bool = False
) -> Dict[str, float]:
    """
    计算方向预测的错误率

    Args:
        predictions: 模型预测的方向列表
        ground_truth: 真实方向列表
        allow_adjacent: 是否将相邻方向视为正确（如东北 vs 北）

    Returns:
        包含错误率统计的字典：
        - error_rate: 总体错误率
        - strict_error_rate: 严格错误率（不考虑相邻方向）
        - adjacent_correct: 相邻方向正确的数量
        - total: 总样本数
    """
    if len(predictions) != len(ground_truth):
        raise ValueError(f"预测和真实值数量不匹配: {len(predictions)} vs {len(ground_truth)}")

    total = len(predictions)
    strict_correct = 0
    adjacent_correct = 0

    for pred, truth in zip(predictions, ground_truth):
        # 标准化方向名称
        pred_norm = _normalize_direction(pred)
        truth_norm = _normalize_direction(truth)

        if pred_norm == truth_norm:
            strict_correct += 1
            adjacent_correct += 1
        elif allow_adjacent and _is_adjacent_direction(pred_norm, truth_norm):
            adjacent_correct += 1

    strict_error_rate = 1 - (strict_correct / total) if total > 0 else 0
    loose_error_rate = 1 - (adjacent_correct / total) if total > 0 else 0

    return {
        "error_rate": loose_error_rate if allow_adjacent else strict_error_rate,
        "strict_error_rate": strict_error_rate,
        "adjacent_correct": adjacent_correct,
        "total": total,
        "strict_correct": strict_correct
    }


def direction_accuracy(
    predictions: List[str],
    ground_truth: List[str],
    allow_adjacent: bool = False
) -> Dict[str, float]:
    """
    计算方向预测的准确率

    Args:
        predictions: 模型预测的方向列表
        ground_truth: 真实方向列表
        allow_adjacent: 是否将相邻方向视为正确

    Returns:
        包含准确率统计的字典
    """
    error_stats = direction_error_rate(predictions, ground_truth, allow_adjacent)

    return {
        "accuracy": 1 - error_stats["error_rate"],
        "strict_accuracy": 1 - error_stats["strict_error_rate"],
        "total": error_stats["total"]
    }


def direction_confusion_matrix(
    predictions: List[str],
    ground_truth: List[str]
) -> Dict[str, Any]:
    """
    生成方向预测的混淆矩阵

    Args:
        predictions: 模型预测的方向列表
        ground_truth: 真实方向列表

    Returns:
        包含混淆矩阵的字典：
        - matrix: 混淆矩阵（真实方向 x 预测方向）
        - labels: 方向标签
        - per_direction_accuracy: 每个方向的准确率
    """
    # 标准化方向
    normalized_pred = [_normalize_direction(p) for p in predictions]
    normalized_truth = [_normalize_direction(t) for t in ground_truth]

    # 初始化混淆矩阵
    labels = DIRECTIONS_8
    n = len(labels)
    matrix = np.zeros((n, n), dtype=int)

    # 填充混淆矩阵
    label_to_idx = {label: i for i, label in enumerate(labels)}

    for pred, truth in zip(normalized_pred, normalized_truth):
        if pred in label_to_idx and truth in label_to_idx:
            matrix[label_to_idx[truth], label_to_idx[pred]] += 1

    # 计算每个方向的准确率
    per_direction_accuracy = {}
    for i, label in enumerate(labels):
        row_sum = matrix[i, :].sum()
        if row_sum > 0:
            per_direction_accuracy[label] = matrix[i, i] / row_sum
        else:
            per_direction_accuracy[label] = 0.0

    return {
        "matrix": matrix.tolist(),
        "labels": labels,
        "per_direction_accuracy": per_direction_accuracy
    }


def _normalize_direction(direction: str) -> str:
    """标准化方向名称"""
    direction = direction.strip().replace("方向", "")

    # 处理常见的方向别名
    aliases = {
        "正东": "东", "正南": "南", "正西": "西", "正北": "北",
        "偏东": "东", "偏南": "南", "偏西": "西", "偏北": "北",
        "东方": "东", "南方": "南", "西方": "西", "北方": "北",
        "E": "东", "S": "南", "W": "西", "N": "北",
        "NE": "东北", "SE": "东南", "NW": "西北", "SW": "西南"
    }

    return aliases.get(direction, direction)


def _is_adjacent_direction(dir1: str, dir2: str) -> bool:
    """判断两个方向是否相邻"""
    return dir2 in ADJACENT_DIRECTIONS.get(dir1, [])


# ==================== 拓扑关系指标 ====================

def topology_confusion_matrix(
    predictions: List[str],
    ground_truth: List[str]
) -> Dict[str, Any]:
    """
    生成拓扑关系预测的混淆矩阵

    拓扑关系类型：包含、相邻、相交、相离

    Args:
        predictions: 模型预测的拓扑关系列表
        ground_truth: 真实拓扑关系列表

    Returns:
        包含混淆矩阵的字典：
        - matrix: 混淆矩阵
        - labels: 拓扑关系标签
        - per_class_accuracy: 每个类别的准确率
    """
    if len(predictions) != len(ground_truth):
        raise ValueError(f"预测和真实值数量不匹配: {len(predictions)} vs {len(ground_truth)}")

    # 标准化拓扑关系
    normalized_pred = [_normalize_topology(p) for p in predictions]
    normalized_truth = [_normalize_topology(t) for t in ground_truth]

    # 获取实际出现的标签
    all_labels = list(set(normalized_pred + normalized_truth))
    labels = [l for l in TOPOLOGY_TYPES if l in all_labels]

    # 初始化混淆矩阵
    n = len(labels)
    matrix = np.zeros((n, n), dtype=int)

    # 填充混淆矩阵
    label_to_idx = {label: i for i, label in enumerate(labels)}

    for pred, truth in zip(normalized_pred, normalized_truth):
        if pred in label_to_idx and truth in label_to_idx:
            matrix[label_to_idx[truth], label_to_idx[pred]] += 1

    # 计算每个类别的准确率
    per_class_accuracy = {}
    for i, label in enumerate(labels):
        row_sum = matrix[i, :].sum()
        if row_sum > 0:
            per_class_accuracy[label] = matrix[i, i] / row_sum
        else:
            per_class_accuracy[label] = 0.0

    return {
        "matrix": matrix.tolist(),
        "labels": labels,
        "per_class_accuracy": per_class_accuracy
    }


def topology_classification_report(
    predictions: List[str],
    ground_truth: List[str]
) -> Dict[str, Dict[str, float]]:
    """
    生成拓扑关系分类报告

    Args:
        predictions: 模型预测的拓扑关系列表
        ground_truth: 真实拓扑关系列表

    Returns:
        每个类别的详细指标报告
    """
    if len(predictions) != len(ground_truth):
        raise ValueError(f"预测和真实值数量不匹配: {len(predictions)} vs {len(ground_truth)}")

    # 标准化
    normalized_pred = [_normalize_topology(p) for p in predictions]
    normalized_truth = [_normalize_topology(t) for t in ground_truth]

    # 获取所有标签
    all_labels = list(set(normalized_pred + normalized_truth))

    report = {}

    for label in all_labels:
        tp = sum(1 for p, t in zip(normalized_pred, normalized_truth) if p == label and t == label)
        fp = sum(1 for p, t in zip(normalized_pred, normalized_truth) if p == label and t != label)
        fn = sum(1 for p, t in zip(normalized_pred, normalized_truth) if p != label and t == label)
        tn = sum(1 for p, t in zip(normalized_pred, normalized_truth) if p != label and t != label)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        report[label] = {
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "support": tp + fn
        }

    return report


def _normalize_topology(topology: str) -> str:
    """标准化拓扑关系名称"""
    topology = topology.strip()

    aliases = {
        "内含": "包含", "在...内": "包含", "在...中": "包含",
        "接壤": "相邻", "交界": "相邻", "毗邻": "相邻",
        "交叉": "相交", "穿过": "相交",
        "分离": "相离", "不相连": "相离",
        "contain": "包含", "adjacent": "相邻", "intersect": "相交", "disjoint": "相离"
    }

    return aliases.get(topology, topology)


# ==================== 距离相关指标 ====================

def distance_mape(
    predictions: List[float],
    ground_truth: List[float],
    epsilon: float = 1e-8
) -> Dict[str, float]:
    """
    计算距离预测的平均绝对百分比误差 (MAPE)

    Args:
        predictions: 预测的距离值列表（公里）
        ground_truth: 真实距离值列表（公里）
        epsilon: 防止除零的小值

    Returns:
        包含MAPE相关指标的字典：
        - mape: 平均绝对百分比误差
        - mean_ae: 平均绝对误差（公里）
        - max_ape: 最大绝对百分比误差
        - median_ape: 中位数绝对百分比误差
    """
    if len(predictions) != len(ground_truth):
        raise ValueError(f"预测和真实值数量不匹配: {len(predictions)} vs {len(ground_truth)}")

    n = len(predictions)
    if n == 0:
        return {"mape": 0.0, "mean_ae": 0.0, "max_ape": 0.0, "median_ape": 0.0}

    ape_values = []
    ae_values = []

    for pred, truth in zip(predictions, ground_truth):
        ae = abs(pred - truth)
        ae_values.append(ae)

        # 避免除零
        denominator = max(abs(truth), epsilon)
        ape = (ae / denominator) * 100
        ape_values.append(ape)

    return {
        "mape": np.mean(ape_values),
        "mean_ae": np.mean(ae_values),
        "max_ape": np.max(ape_values) if ape_values else 0.0,
        "median_ape": np.median(ape_values) if ape_values else 0.0
    }


def distance_mae(predictions: List[float], ground_truth: List[float]) -> float:
    """
    计算距离预测的平均绝对误差 (MAE)

    Args:
        predictions: 预测的距离值列表
        ground_truth: 真实距离值列表

    Returns:
        平均绝对误差（公里）
    """
    if len(predictions) != len(ground_truth):
        raise ValueError(f"预测和真实值数量不匹配: {len(predictions)} vs {len(ground_truth)}")

    if len(predictions) == 0:
        return 0.0

    return np.mean([abs(p - t) for p, t in zip(predictions, ground_truth)])


def distance_rmse(predictions: List[float], ground_truth: List[float]) -> float:
    """
    计算距离预测的均方根误差 (RMSE)

    Args:
        predictions: 预测的距离值列表
        ground_truth: 真实距离值列表

    Returns:
        均方根误差（公里）
    """
    if len(predictions) != len(ground_truth):
        raise ValueError(f"预测和真实值数量不匹配: {len(predictions)} vs {len(ground_truth)}")

    if len(predictions) == 0:
        return 0.0

    return np.sqrt(np.mean([(p - t) ** 2 for p, t in zip(predictions, ground_truth)]))


# ==================== 空间关系提取指标 ====================

def spatial_relation_f1(
    predictions: List[Dict[str, Any]],
    ground_truth: List[Dict[str, Any]],
    relation_type: Optional[str] = None
) -> Dict[str, float]:
    """
    计算空间关系提取的F1分数

    Args:
        predictions: 预测的空间关系列表，每个关系是包含以下字段的字典：
            - entity1: 实体1
            - entity2: 实体2
            - relation: 关系类型（方向、拓扑、度量）
            - value: 关系值（可选）
        ground_truth: 真实空间关系列表
        relation_type: 指定计算的关系类型（None表示所有类型）

    Returns:
        包含precision, recall, f1的字典
    """
    # 标准化预测和真实值
    normalized_pred = [_normalize_relation(r) for r in predictions]
    normalized_truth = [_normalize_relation(r) for r in ground_truth]

    # 过滤关系类型
    if relation_type:
        normalized_pred = [r for r in normalized_pred if r["relation"] == relation_type]
        normalized_truth = [r for r in normalized_truth if r["relation"] == relation_type]

    # 转换为集合便于比较
    pred_set = {(r["entity1"], r["entity2"], r["relation"], str(r.get("value", ""))) for r in normalized_pred}
    truth_set = {(r["entity1"], r["entity2"], r["relation"], str(r.get("value", ""))) for r in normalized_truth}

    # 计算TP, FP, FN
    tp = len(pred_set & truth_set)
    fp = len(pred_set - truth_set)
    fn = len(truth_set - pred_set)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn
    }


def spatial_relation_precision(
    predictions: List[Dict[str, Any]],
    ground_truth: List[Dict[str, Any]]
) -> float:
    """计算空间关系提取的精确率"""
    result = spatial_relation_f1(predictions, ground_truth)
    return result["precision"]


def spatial_relation_recall(
    predictions: List[Dict[str, Any]],
    ground_truth: List[Dict[str, Any]]
) -> float:
    """计算空间关系提取的召回率"""
    result = spatial_relation_f1(predictions, ground_truth)
    return result["recall"]


def _normalize_relation(relation: Dict[str, Any]) -> Dict[str, Any]:
    """标准化空间关系格式"""
    return {
        "entity1": str(relation.get("entity1", "")).strip(),
        "entity2": str(relation.get("entity2", "")).strip(),
        "relation": str(relation.get("relation", "")).strip(),
        "value": relation.get("value", "")
    }


# ==================== 推理链指标 ====================

def reasoning_accuracy(
    predictions: List[str],
    ground_truth: List[str]
) -> float:
    """
    计算推理结果的准确率

    Args:
        predictions: 模型输出的推理结论列表
        ground_truth: 真实结论列表

    Returns:
        准确率（0-1之间的浮点数）
    """
    if len(predictions) != len(ground_truth):
        raise ValueError(f"预测和真实值数量不匹配: {len(predictions)} vs {len(ground_truth)}")

    if len(predictions) == 0:
        return 0.0

    correct = sum(1 for p, t in zip(predictions, ground_truth)
                  if _normalize_answer(p) == _normalize_answer(t))

    return correct / len(predictions)


def reasoning_step_accuracy(
    predictions: List[List[str]],
    ground_truth: List[List[str]]
) -> Dict[str, float]:
    """
    计算推理步骤的准确率

    Args:
        predictions: 预测的推理步骤列表（每个样本是一个步骤列表）
        ground_truth: 真实推理步骤列表

    Returns:
        包含步骤准确率的字典：
        - step_accuracy: 各步骤的平均准确率
        - per_step_accuracy: 每个步骤位置的平均准确率
        - avg_steps: 平均步骤数
    """
    if len(predictions) != len(ground_truth):
        raise ValueError(f"预测和真实值数量不匹配: {len(predictions)} vs {len(ground_truth)}")

    if len(predictions) == 0:
        return {"step_accuracy": 0.0, "per_step_accuracy": [], "avg_steps": 0.0}

    total_correct = 0
    total_steps = 0
    step_accuracies = defaultdict(list)

    for pred_steps, truth_steps in zip(predictions, ground_truth):
        max_steps = max(len(pred_steps), len(truth_steps))

        for i in range(max_steps):
            pred_step = pred_steps[i] if i < len(pred_steps) else ""
            truth_step = truth_steps[i] if i < len(truth_steps) else ""

            is_correct = _normalize_answer(pred_step) == _normalize_answer(truth_step)
            step_accuracies[i].append(1.0 if is_correct else 0.0)

            total_steps += 1
            if is_correct:
                total_correct += 1

    per_step_accuracy = [np.mean(step_accuracies[i]) for i in sorted(step_accuracies.keys())]

    return {
        "step_accuracy": total_correct / total_steps if total_steps > 0 else 0.0,
        "per_step_accuracy": per_step_accuracy,
        "avg_steps": np.mean([len(steps) for steps in ground_truth])
    }


def reasoning_chain_completeness(
    predictions: List[List[str]],
    ground_truth: List[List[str]]
) -> Dict[str, float]:
    """
    计算推理链的完整性

    评估预测的推理链是否覆盖了真实推理链的关键步骤

    Args:
        predictions: 预测的推理步骤列表
        ground_truth: 真实推理步骤列表

    Returns:
        包含完整性指标的字典：
        - completeness: 完整性得分（0-1）
        - coverage: 真实步骤被预测覆盖的比例
        - precision: 预测步骤中真实步骤的比例
    """
    if len(predictions) != len(ground_truth):
        raise ValueError(f"预测和真实值数量不匹配: {len(predictions)} vs {len(ground_truth)}")

    if len(predictions) == 0:
        return {"completeness": 0.0, "coverage": 0.0, "precision": 0.0}

    total_coverage = 0.0
    total_precision = 0.0

    for pred_steps, truth_steps in zip(predictions, ground_truth):
        normalized_pred = [_normalize_answer(s) for s in pred_steps]
        normalized_truth = [_normalize_answer(s) for s in truth_steps]

        # 计算覆盖率和精确率
        truth_set = set(normalized_truth)
        pred_set = set(normalized_pred)

        if len(truth_set) > 0:
            coverage = len(truth_set & pred_set) / len(truth_set)
        else:
            coverage = 1.0 if len(pred_set) == 0 else 0.0

        if len(pred_set) > 0:
            precision = len(truth_set & pred_set) / len(pred_set)
        else:
            precision = 0.0

        total_coverage += coverage
        total_precision += precision

    n = len(predictions)
    completeness = (total_coverage + total_precision) / (2 * n) if n > 0 else 0.0

    return {
        "completeness": completeness,
        "coverage": total_coverage / n if n > 0 else 0.0,
        "precision": total_precision / n if n > 0 else 0.0
    }


def _normalize_answer(answer: str) -> str:
    """标准化答案文本"""
    answer = str(answer).strip().lower()
    # 移除标点符号
    for punct in "。，！？、；：""''（）【】《》":
        answer = answer.replace(punct, "")
    return answer


# ==================== 综合计算器 ====================

@dataclass
class GeoMetricsResult:
    """地理评测指标结果数据类"""
    # 方向指标
    direction_accuracy: float = 0.0
    direction_error_rate: float = 0.0
    direction_adjacent_accuracy: float = 0.0

    # 拓扑指标
    topology_accuracy: float = 0.0
    topology_f1: float = 0.0

    # 距离指标
    distance_mape: float = 0.0
    distance_mae: float = 0.0
    distance_rmse: float = 0.0

    # 空间关系提取指标
    relation_precision: float = 0.0
    relation_recall: float = 0.0
    relation_f1: float = 0.0

    # 推理指标
    reasoning_accuracy: float = 0.0
    reasoning_step_accuracy: float = 0.0
    reasoning_completeness: float = 0.0

    # 样本统计
    total_samples: int = 0
    dimension_counts: Dict[str, int] = field(default_factory=dict)


class GeoMetricsCalculator:
    """
    地理评测指标综合计算器

    用于批量计算和汇总地理空间推理模型的各种评测指标。
    """

    def __init__(self):
        """初始化计算器"""
        self.reset()

    def reset(self):
        """重置所有统计信息"""
        self._direction_predictions = []
        self._direction_truth = []
        self._topology_predictions = []
        self._topology_truth = []
        self._distance_predictions = []
        self._distance_truth = []
        self._relation_predictions = []
        self._relation_truth = []
        self._reasoning_predictions = []
        self._reasoning_truth = []
        self._reasoning_steps_pred = []
        self._reasoning_steps_truth = []

        self._dimension_counts = defaultdict(int)

    def add_direction_sample(self, prediction: str, ground_truth: str):
        """添加单个方向样本"""
        self._direction_predictions.append(prediction)
        self._direction_truth.append(ground_truth)

    def add_topology_sample(self, prediction: str, ground_truth: str):
        """添加单个拓扑关系样本"""
        self._topology_predictions.append(prediction)
        self._topology_truth.append(ground_truth)

    def add_distance_sample(self, prediction: float, ground_truth: float):
        """添加单个距离样本"""
        self._distance_predictions.append(prediction)
        self._distance_truth.append(ground_truth)

    def add_relation_sample(self, prediction: Dict[str, Any], ground_truth: Dict[str, Any]):
        """添加单个空间关系样本"""
        self._relation_predictions.append(prediction)
        self._relation_truth.append(ground_truth)

    def add_reasoning_sample(self, prediction: str, ground_truth: str):
        """添加单个推理结论样本"""
        self._reasoning_predictions.append(prediction)
        self._reasoning_truth.append(ground_truth)

    def add_reasoning_steps(self, prediction_steps: List[str], truth_steps: List[str]):
        """添加推理步骤样本"""
        self._reasoning_steps_pred.append(prediction_steps)
        self._reasoning_steps_truth.append(truth_steps)

    def add_dimension(self, dimension: str):
        """记录维度计数"""
        self._dimension_counts[dimension] += 1

    def compute_metrics(self) -> GeoMetricsResult:
        """
        计算所有指标

        Returns:
            GeoMetricsResult: 包含所有计算结果的对象
        """
        result = GeoMetricsResult()

        # 方向指标
        if self._direction_predictions:
            dir_acc = direction_accuracy(
                self._direction_predictions,
                self._direction_truth,
                allow_adjacent=False
            )
            result.direction_accuracy = dir_acc["strict_accuracy"]
            result.direction_error_rate = dir_acc["accuracy"]

            dir_adj_acc = direction_accuracy(
                self._direction_predictions,
                self._direction_truth,
                allow_adjacent=True
            )
            result.direction_adjacent_accuracy = dir_adj_acc["accuracy"]

        # 拓扑指标
        if self._topology_predictions:
            topo_report = topology_classification_report(
                self._topology_predictions,
                self._topology_truth
            )
            if topo_report:
                f1_scores = [r["f1_score"] for r in topo_report.values()]
                result.topology_f1 = np.mean(f1_scores) if f1_scores else 0.0

        # 距离指标
        if self._distance_predictions:
            mape_result = distance_mape(
                self._distance_predictions,
                self._distance_truth
            )
            result.distance_mape = mape_result["mape"]
            result.distance_mae = distance_mae(
                self._distance_predictions,
                self._distance_truth
            )
            result.distance_rmse = distance_rmse(
                self._distance_predictions,
                self._distance_truth
            )

        # 空间关系提取指标
        if self._relation_predictions:
            relation_result = spatial_relation_f1(
                self._relation_predictions,
                self._relation_truth
            )
            result.relation_precision = relation_result["precision"]
            result.relation_recall = relation_result["recall"]
            result.relation_f1 = relation_result["f1"]

        # 推理指标
        if self._reasoning_predictions:
            result.reasoning_accuracy = reasoning_accuracy(
                self._reasoning_predictions,
                self._reasoning_truth
            )

        if self._reasoning_steps_pred:
            step_acc = reasoning_step_accuracy(
                self._reasoning_steps_pred,
                self._reasoning_steps_truth
            )
            result.reasoning_step_accuracy = step_acc["step_accuracy"]

            completeness = reasoning_chain_completeness(
                self._reasoning_steps_pred,
                self._reasoning_steps_truth
            )
            result.reasoning_completeness = completeness["completeness"]

        # 样本统计
        result.total_samples = (
            len(self._direction_predictions) +
            len(self._topology_predictions) +
            len(self._distance_predictions)
        )
        result.dimension_counts = dict(self._dimension_counts)

        return result

    def get_summary(self) -> str:
        """
        获取指标摘要报告

        Returns:
            格式化的摘要字符串
        """
        result = self.compute_metrics()

        lines = [
            "=" * 60,
            "地理评测指标摘要报告",
            "=" * 60,
            "",
            "【方向相关指标】",
            f"  严格准确率: {result.direction_accuracy:.2%}",
            f"  相邻容错准确率: {result.direction_adjacent_accuracy:.2%}",
            f"  错误率: {result.direction_error_rate:.2%}",
            "",
            "【拓扑关系指标】",
            f"  F1分数: {result.topology_f1:.4f}",
            "",
            "【距离相关指标】",
            f"  MAPE: {result.distance_mape:.2f}%",
            f"  MAE: {result.distance_mae:.2f} 公里",
            f"  RMSE: {result.distance_rmse:.2f} 公里",
            "",
            "【空间关系提取指标】",
            f"  Precision: {result.relation_precision:.4f}",
            f"  Recall: {result.relation_recall:.4f}",
            f"  F1 Score: {result.relation_f1:.4f}",
            "",
            "【推理链指标】",
            f"  推理准确率: {result.reasoning_accuracy:.2%}",
            f"  步骤准确率: {result.reasoning_step_accuracy:.2%}",
            f"  链完整性: {result.reasoning_completeness:.4f}",
            "",
            "【样本统计】",
            f"  总样本数: {result.total_samples}",
        ]

        if result.dimension_counts:
            lines.append("  维度分布:")
            for dim, count in result.dimension_counts.items():
                lines.append(f"    {dim}: {count}")

        lines.append("=" * 60)

        return "\n".join(lines)

    def save_to_file(self, filepath: str):
        """
        将评测结果保存到JSON文件

        Args:
            filepath: 输出文件路径
        """
        result = self.compute_metrics()

        output = {
            "timestamp": str(np.datetime64('now')),
            "metrics": {
                "direction": {
                    "accuracy": result.direction_accuracy,
                    "error_rate": result.direction_error_rate,
                    "adjacent_accuracy": result.direction_adjacent_accuracy
                },
                "topology": {
                    "f1": result.topology_f1
                },
                "distance": {
                    "mape": result.distance_mape,
                    "mae": result.distance_mae,
                    "rmse": result.distance_rmse
                },
                "relation": {
                    "precision": result.relation_precision,
                    "recall": result.relation_recall,
                    "f1": result.relation_f1
                },
                "reasoning": {
                    "accuracy": result.reasoning_accuracy,
                    "step_accuracy": result.reasoning_step_accuracy,
                    "completeness": result.reasoning_completeness
                }
            },
            "statistics": {
                "total_samples": result.total_samples,
                "dimension_counts": result.dimension_counts
            }
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)


# ==================== 辅助函数 ====================

def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    """
    计算从点1到点2的8方向方位角

    Args:
        lat1, lon1: 起点的纬度和经度
        lat2, lon2: 终点的纬度和经度

    Returns:
        方向字符串（东、南、西、北、东北、东南、西北、西南）
    """
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(dlon))

    bearing = math.atan2(x, y)
    bearing = math.degrees(bearing)
    bearing = (bearing + 360) % 360

    # 转换为8方向
    directions = ["东", "东南", "南", "西南", "西", "西北", "北", "东北"]
    index = round(bearing / 45) % 8
    return directions[index]


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    使用Haversine公式计算两点间的球面距离（公里）

    Args:
        lat1, lon1: 点1的纬度和经度
        lat2, lon2: 点2的纬度和经度

    Returns:
        距离（公里）
    """
    R = 6371  # 地球半径（公里）

    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))

    return R * c


# ==================== 示例用法 ====================

if __name__ == "__main__":
    print("=" * 60)
    print("地理评测指标模块测试")
    print("=" * 60)

    # 创建计算器
    calculator = GeoMetricsCalculator()

    # 添加方向样本
    print("\n【测试1】方向错误率")
    directions_pred = ["东", "南", "西", "北", "东北"]
    directions_truth = ["东", "东南", "西", "西北", "东北"]

    for p, t in zip(directions_pred, directions_truth):
        calculator.add_direction_sample(p, t)

    # 添加拓扑样本
    print("\n【测试2】拓扑关系混淆矩阵")
    topo_pred = ["包含", "相邻", "相交", "相离"]
    topo_truth = ["包含", "相邻", "相离", "相离"]

    for p, t in zip(topo_pred, topo_truth):
        calculator.add_topology_sample(p, t)

    # 添加距离样本
    print("\n【测试3】距离误差MAPE")
    distance_pred = [100, 200, 150, 180]
    distance_truth = [105, 195, 160, 175]

    for p, t in zip(distance_pred, distance_truth):
        calculator.add_distance_sample(p, t)

    # 添加推理样本
    print("\n【测试4】推理链准确率")
    reasoning_pred = ["北京距离天津约120公里", "上海位于江苏省", "长江流经湖北"]
    reasoning_truth = ["北京距离天津约120公里", "上海位于上海市", "长江流经湖北"]

    for p, t in zip(reasoning_pred, reasoning_truth):
        calculator.add_reasoning_sample(p, t)

    # 计算并打印结果
    print("\n" + calculator.get_summary())

    # 保存结果
    import os
    output_dir = "D:/30_keyan/GeoKD-SR/outputs/metrics"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "test_metrics.json")
    calculator.save_to_file(output_path)
    print(f"\n结果已保存至: {output_path}")
