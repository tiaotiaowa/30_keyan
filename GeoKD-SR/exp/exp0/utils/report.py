# -*- coding: utf-8 -*-
"""
报告生成模块

提供评估报告和排行榜生成功能。
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path


def generate_report(
    metrics: Dict[str, Any],
    output_path: str,
    model_name: str = "model",
    config: Optional[Dict] = None
) -> str:
    """
    生成评估报告

    参数:
        metrics: 指标字典
        output_path: 输出目录路径
        model_name: 模型名称
        config: 配置信息（可选）

    返回:
        报告文件路径
    """
    os.makedirs(output_path, exist_ok=True)

    # 创建报告文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(output_path, f"report_{model_name}_{timestamp}.json")

    # 构建报告数据
    report = {
        "model_name": model_name,
        "timestamp": timestamp,
        "datetime": datetime.now().isoformat(),
        "config": config or {},
        "metrics": metrics,
        "summary": _generate_summary(metrics)
    }

    # 保存JSON报告
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 生成Markdown报告
    md_file = report_file.replace('.json', '.md')
    _generate_markdown_report(report, md_file)

    return report_file


def _generate_summary(metrics: Dict[str, Any]) -> Dict[str, str]:
    """生成指标摘要"""
    summary = {}

    # 整体准确率
    if "accuracy" in metrics:
        summary["overall_accuracy"] = f"{metrics['accuracy']:.2%}"

    # 方向准确率
    if "direction_accuracy" in metrics:
        summary["direction_accuracy"] = f"{metrics['direction_accuracy']:.2%}"

    # 拓扑准确率
    if "topology_accuracy" in metrics:
        summary["topology_accuracy"] = f"{metrics['topology_accuracy']:.2%}"

    # 距离MAPE
    if "distance_mape" in metrics:
        summary["distance_mape"] = f"{metrics['distance_mape']:.2f}%"

    return summary


def _generate_markdown_report(report: Dict[str, Any], output_path: str):
    """生成Markdown格式的报告"""
    lines = [
        f"# {report['model_name']} 评估报告",
        "",
        f"**生成时间**: {report['datetime']}\n",
        "---",
        "",
        "## 概要",
        "",
    ]

    # 添加摘要
    summary = report.get('summary', {})
    if summary:
        lines.append("| 指标 | 值 |")
        lines.append("|------|------|")
        for key, value in summary.items():
            lines.append(f"| {key} | {value} |")
        lines.append("")

    # 添加详细指标
    lines.append("## 详细指标")
    lines.append("")

    metrics = report.get('metrics', {})

    # 准确率指标
    if any(k in metrics for k in ['accuracy', 'direction_accuracy', 'topology_accuracy']):
        lines.append("### 准确率")
        lines.append("")
        for key, value in metrics.items():
            if 'accuracy' in key or 'error' in key:
                lines.append(f"- **{key}**: {value:.4f}")
        lines.append("")

    # 距离指标
    if any(k in metrics for k in ['distance_mape', 'distance_mae', 'distance_rmse']):
        lines.append("### 距离误差")
        lines.append("")
        for key, value in metrics.items():
            if 'distance' in key:
                lines.append(f"- **{key}**: {value:.4f}")
        lines.append("")

    # 混淆矩阵
    if 'confusion_matrix' in metrics:
        lines.append("### 混淆矩阵")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(metrics['confusion_matrix'], indent=2, ensure_ascii=False))
        lines.append("```")
        lines.append("")

    # 分类报告
    if 'classification_report' in metrics:
        lines.append("### 分类报告")
        lines.append("")
        for class_name, class_metrics in metrics['classification_report'].items():
            lines.append(f"#### {class_name}")
            lines.append("")
            for metric_name, metric_value in class_metrics.items():
                lines.append(f"- {metric_name}: {metric_value:.4f}")
            lines.append("")

    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def generate_leaderboard(
    results: List[Dict[str, Any]],
    output_path: str,
    metric: str = "accuracy",
    ascending: bool = False
) -> str:
    """
    生成对比排行榜

    参数:
        results: 结果列表，每个元素包含模型名称和指标
        output_path: 输出文件路径
        metric: 排序依据的指标
        ascending: 是否升序排列

    返回:
        排行榜文件路径
    """
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    # 按指标排序
    sorted_results = sorted(
        results,
        key=lambda x: x.get('metrics', {}).get(metric, 0),
        reverse=not ascending
    )

    # 生成排行榜
    leaderboard = {
        "timestamp": datetime.now().isoformat(),
        "sort_metric": metric,
        "rankings": []
    }

    for rank, result in enumerate(sorted_results, 1):
        entry = {
            "rank": rank,
            "model_name": result.get('model_name', 'unknown'),
            "metrics": result.get('metrics', {})
        }
        leaderboard["rankings"].append(entry)

    # 保存JSON
    json_file = output_path
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(leaderboard, f, ensure_ascii=False, indent=2)

    # 生成Markdown
    md_file = output_path.replace('.json', '.md')
    _generate_leaderboard_md(leaderboard, md_file)

    return json_file


def _generate_leaderboard_md(leaderboard: Dict[str, Any], output_path: str):
    """生成Markdown格式的排行榜"""
    lines = [
        f"# 模型排行榜",
        "",
        f"**生成时间**: {leaderboard['timestamp']}",
        f"**排序指标**: {leaderboard['sort_metric']}",
        "",
        "---",
        "",
        "## 排名",
        "",
        "| 排名 | 模型 |",
    ]

    # 添加所有指标列
    if leaderboard['rankings']:
        sample_metrics = leaderboard['rankings'][0].get('metrics', {})
        for metric_key in sample_metrics.keys():
            lines.append(f" {metric_key} |")
        lines.append("|" + "----|" * (len(sample_metrics) + 2))

        # 添加数据行
        for entry in leaderboard['rankings']:
            row = f"| {entry['rank']} | {entry['model_name']} |"
            for metric_key in sample_metrics.keys():
                value = entry['metrics'].get(metric_key, 0)
                if isinstance(value, float):
                    row += f" {value:.4f} |"
                else:
                    row += f" {value} |"
            lines.append(row)

    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def append_to_leaderboard(
    leaderboard_path: str,
    new_result: Dict[str, Any],
    metric: str = "accuracy"
) -> str:
    """
    向现有排行榜添加新结果

    参数:
        leaderboard_path: 现有排行榜文件路径
        new_result: 新的模型结果
        metric: 排序依据的指标

    返回:
        更新后的排行榜文件路径
    """
    # 读取现有排行榜
    if os.path.exists(leaderboard_path):
        with open(leaderboard_path, 'r', encoding='utf-8') as f:
            leaderboard = json.load(f)
        results = leaderboard.get('rankings', [])
    else:
        results = []

    # 添加新结果
    results.append(new_result)

    # 重新生成排行榜
    return generate_leaderboard(
        results,
        leaderboard_path,
        metric=metric
    )


def compare_results(
    result1: Dict[str, Any],
    result2: Dict[str, Any],
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    比较两个模型的结果

    参数:
        result1: 第一个模型的结果
        result2: 第二个模型的结果
        output_path: 输出文件路径（可选）

    返回:
        比较结果字典
    """
    comparison = {
        "model1": result1.get('model_name', 'model1'),
        "model2": result2.get('model_name', 'model2'),
        "timestamp": datetime.now().isoformat(),
        "differences": {}
    }

    metrics1 = result1.get('metrics', {})
    metrics2 = result2.get('metrics', {})

    # 找出所有共同的指标
    all_keys = set(metrics1.keys()) | set(metrics2.keys())

    for key in all_keys:
        val1 = metrics1.get(key, 0)
        val2 = metrics2.get(key, 0)

        if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            diff = val2 - val1
            pct_diff = (diff / val1 * 100) if val1 != 0 else 0

            comparison['differences'][key] = {
                "model1": val1,
                "model2": val2,
                "difference": diff,
                "percentage_change": pct_diff,
                "better": "model2" if diff > 0 else "model1" if diff < 0 else "tie"
            }

    # 保存比较结果
    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(comparison, f, ensure_ascii=False, indent=2)

    return comparison


if __name__ == "__main__":
    # 测试报告生成
    print("测试报告生成模块...")

    # 示例指标
    test_metrics = {
        "accuracy": 0.85,
        "direction_accuracy": 0.82,
        "topology_accuracy": 0.88,
        "distance_mape": 12.5,
        "distance_mae": 15.3
    }

    report_path = generate_report(
        test_metrics,
        "D:/30_keyan/GeoKD-SR/exp/exp0/outputs/reports",
        "test_model"
    )

    print(f"报告已生成: {report_path}")
