# -*- coding: utf-8 -*-
"""
评测结果对比分析脚本
===================

对比两种提示词格式的评测结果

使用方法:
    python compare_results.py \
        --raw-results ./results/raw_format/metrics.json \
        --prompt-results ./results/prompt_format/metrics.json \
        --raw-predictions ./results/raw_format/predictions.jsonl \
        --prompt-predictions ./results/prompt_format/predictions.jsonl \
        --output ./results/comparison_report.md

作者: GeoKD-SR Project
日期: 2026-03-27
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any


def load_metrics(metrics_file: str) -> Dict[str, Any]:
    """加载评测指标"""
    with open(metrics_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_predictions(predictions_file: str) -> List[Dict[str, Any]]:
    """加载预测结果"""
    predictions = []
    with open(predictions_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                predictions.append(json.loads(line))
    return predictions


def generate_comparison_report(
    raw_metrics: Dict[str, Any],
    prompt_metrics: Dict[str, Any],
    raw_predictions: List[Dict[str, Any]],
    prompt_predictions: List[Dict[str, Any]],
    output_file: str
):
    """生成对比报告"""

    report = []
    report.append("# LoRA微调模型双格式对比评测报告\n")
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report.append("\n---\n")

    # 1. 总体对比
    report.append("\n## 1. 总体指标对比\n")
    report.append("| 指标 | 原始问题格式 | Prompt Template格式 | 差异 | 差异率 |")
    report.append("\n|------|--------------|---------------------|------|--------|\n")

    raw_acc = raw_metrics['overall']['accuracy']
    prompt_acc = prompt_metrics['overall']['accuracy']
    acc_diff = raw_acc - prompt_acc
    acc_diff_rate = (acc_diff / prompt_acc * 100) if prompt_acc > 0 else 0

    report.append(f"| 总体准确率 | {raw_acc:.4f} | {prompt_acc:.4f} | {acc_diff:+.4f} | {acc_diff_rate:+.2f}% |\n")

    raw_fvr = raw_metrics['overall']['format_valid_rate']
    prompt_fvr = prompt_metrics['overall']['format_valid_rate']
    fvr_diff = raw_fvr - prompt_fvr
    fvr_diff_rate = (fvr_diff / prompt_fvr * 100) if prompt_fvr > 0 else 0

    report.append(f"| 格式有效率 | {raw_fvr:.4f} | {prompt_fvr:.4f} | {fvr_diff:+.4f} | {fvr_diff_rate:+.2f}% |\n")

    # 2. 按空间类型对比
    report.append("\n## 2. 按空间类型对比\n")
    report.append("| 空间类型 | 样本数 | 原始格式准确率 | Prompt格式准确率 | 差异 |")
    report.append("\n|----------|--------|----------------|------------------|------|\n")

    all_types = set(raw_metrics['by_type'].keys()) | set(prompt_metrics['by_type'].keys())
    for stype in sorted(all_types):
        raw_data = raw_metrics['by_type'].get(stype, {'count': 0, 'accuracy': 0})
        prompt_data = prompt_metrics['by_type'].get(stype, {'count': 0, 'accuracy': 0})

        count = raw_data['count']
        raw_type_acc = raw_data['accuracy']
        prompt_type_acc = prompt_data['accuracy']
        type_diff = raw_type_acc - prompt_type_acc

        report.append(f"| {stype} | {count} | {raw_type_acc:.4f} | {prompt_type_acc:.4f} | {type_diff:+.4f} |\n")

    # 3. 分析结论
    report.append("\n## 3. 分析结论\n")

    if raw_acc > prompt_acc + 0.05:
        report.append("**结论**: 原始问题格式的准确率**显著高于** Prompt Template格式。\n")
        report.append("- 这表明**提示词不一致是导致精度下降的主要原因**。\n")
        report.append("- 模型在训练时学习了原始问题的格式，使用不同的prompt_template会影响其表现。\n")
        report.append("- **建议**: 评测时应使用与训练一致的原始问题格式。\n")
    elif prompt_acc > raw_acc + 0.05:
        report.append("**结论**: Prompt Template格式的准确率**显著高于** 原始问题格式。\n")
        report.append("- 这表明详细的提示词能够帮助模型更好地理解任务。\n")
        report.append("- **建议**: 考虑在训练时也使用类似的prompt_template。\n")
    else:
        report.append("**结论**: 两种格式的准确率**差异不大**。\n")
        report.append("- 提示词格式不是影响模型表现的主要因素。\n")
        report.append("- 需要从其他方面寻找精度下降的原因（如学习率、训练轮数等）。\n")

    # 4. 典型样本对比
    report.append("\n## 4. 典型预测样本对比\n")
    report.append("展示两种格式预测差异最大的样本：\n")

    # 找出差异最大的样本
    diff_samples = []
    for i, (raw_pred, prompt_pred) in enumerate(zip(raw_predictions[:50], prompt_predictions[:50])):
        if raw_pred['prediction'] != prompt_pred['prediction']:
            diff_samples.append({
                'id': raw_pred['id'],
                'question': raw_pred['question'],
                'reference': raw_pred['reference'],
                'raw_prediction': raw_pred['prediction'],
                'prompt_prediction': prompt_pred['prediction'],
                'spatial_type': raw_pred['spatial_type']
            })

    report.append(f"\n共发现 {len(diff_samples)} 个预测差异样本（前50条中）。\n")

    # 展示前5个差异样本
    for i, sample in enumerate(diff_samples[:5]):
        report.append(f"\n### 样例 {i+1} ({sample['spatial_type']})\n")
        report.append(f"- **问题**: {sample['question']}\n")
        report.append(f"- **参考答案**: {sample['reference']}\n")
        report.append(f"- **原始格式预测**: {sample['raw_prediction']}\n")
        report.append(f"- **Prompt格式预测**: {sample['prompt_prediction']}\n")

    # 5. 建议
    report.append("\n## 5. 后续建议\n")
    report.append("1. 如果原始格式准确率更高：\n")
    report.append("   - 评测时使用原始问题格式\n")
    report.append("   - 或在训练时使用与评测一致的prompt_template\n")
    report.append("2. 如果两种格式差异不大：\n")
    report.append("   - 检查学习率是否过高\n")
    report.append("   - 减少训练轮数\n")
    report.append("   - 考虑使用知识蒸馏而非直接SFT\n")

    # 保存报告
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(''.join(report))

    print(f"对比报告已保存到: {output_file}")
    print("\n" + "="*60)
    print("对比摘要")
    print("="*60)
    print(f"原始格式准确率: {raw_acc:.4f}")
    print(f"Prompt格式准确率: {prompt_acc:.4f}")
    print(f"差异: {acc_diff:+.4f} ({acc_diff_rate:+.2f}%)")


def main():
    parser = argparse.ArgumentParser(description="评测结果对比分析")
    parser.add_argument("--raw-results", type=str, required=True, help="原始格式评测结果")
    parser.add_argument("--prompt-results", type=str, required=True, help="Prompt格式评测结果")
    parser.add_argument("--raw-predictions", type=str, required=True, help="原始格式预测文件")
    parser.add_argument("--prompt-predictions", type=str, required=True, help="Prompt格式预测文件")
    parser.add_argument("--output", type=str, default="./results/comparison_report.md", help="输出报告路径")

    args = parser.parse_args()

    # 加载数据
    raw_metrics = load_metrics(args.raw_results)
    prompt_metrics = load_metrics(args.prompt_results)
    raw_predictions = load_predictions(args.raw_predictions)
    prompt_predictions = load_predictions(args.prompt_predictions)

    # 生成报告
    generate_comparison_report(
        raw_metrics, prompt_metrics,
        raw_predictions, prompt_predictions,
        args.output
    )


if __name__ == "__main__":
    main()
