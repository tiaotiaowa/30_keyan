# -*- coding: utf-8 -*-
"""
微调前后模型深度对比分析脚本

功能：
1. 加载微调前后的predictions数据
2. 进行样本级对比分析
3. 计算各维度指标变化
4. 分析错误模式
5. 生成详细分析报告

作者：GeoKD-SR项目组
日期：2026-03-27
"""

import json
import os
from collections import defaultdict
from typing import Dict, List, Any, Tuple
from pathlib import Path


def load_predictions(file_path: str) -> Dict[str, Dict]:
    """加载predictions文件，返回以id为key的字典"""
    predictions = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                predictions[data['id']] = data
    return predictions


def load_metrics(file_path: str) -> Dict:
    """加载metrics.json文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def analyze_sample_differences(
    before_preds: Dict[str, Dict],
    after_preds: Dict[str, Dict],
    test_data: Dict[str, Dict]
) -> Dict[str, Any]:
    """
    分析样本级别的预测差异

    分类：
    - regressed: 微调前正确→微调后错误
    - improved: 微调前错误→微调后正确
    - both_correct: 两者都正确
    - both_wrong: 两者都错误
    """
    results = {
        'regressed': [],  # 退化样本
        'improved': [],   # 改进样本
        'both_correct': [],
        'both_wrong': [],
        'stats': {
            'total': 0,
            'regressed_count': 0,
            'improved_count': 0,
            'both_correct_count': 0,
            'both_wrong_count': 0
        },
        'by_type': defaultdict(lambda: {'regressed': 0, 'improved': 0, 'both_correct': 0, 'both_wrong': 0}),
        'by_difficulty': defaultdict(lambda: {'regressed': 0, 'improved': 0, 'both_correct': 0, 'both_wrong': 0})
    }

    for sample_id, test_item in test_data.items():
        if sample_id not in before_preds or sample_id not in after_preds:
            continue

        before_pred = before_preds[sample_id]
        after_pred = after_preds[sample_id]
        reference = test_item.get('answer', '')
        spatial_type = test_item.get('spatial_relation_type', 'unknown')
        difficulty = test_item.get('difficulty', 'unknown')

        # 简单的正确性判断（与参考答案的文本匹配）
        before_correct = check_correctness(before_pred['prediction'], reference, spatial_type)
        after_correct = check_correctness(after_pred['prediction'], reference, spatial_type)

        results['stats']['total'] += 1

        sample_info = {
            'id': sample_id,
            'question': test_item.get('question', ''),
            'reference': reference,
            'before_prediction': before_pred['prediction'],
            'after_prediction': after_pred['prediction'],
            'spatial_type': spatial_type,
            'difficulty': difficulty
        }

        if before_correct and not after_correct:
            results['regressed'].append(sample_info)
            results['stats']['regressed_count'] += 1
            results['by_type'][spatial_type]['regressed'] += 1
            results['by_difficulty'][difficulty]['regressed'] += 1
        elif not before_correct and after_correct:
            results['improved'].append(sample_info)
            results['stats']['improved_count'] += 1
            results['by_type'][spatial_type]['improved'] += 1
            results['by_difficulty'][difficulty]['improved'] += 1
        elif before_correct and after_correct:
            results['both_correct'].append(sample_info)
            results['stats']['both_correct_count'] += 1
            results['by_type'][spatial_type]['both_correct'] += 1
            results['by_difficulty'][difficulty]['both_correct'] += 1
        else:
            results['both_wrong'].append(sample_info)
            results['stats']['both_wrong_count'] += 1
            results['by_type'][spatial_type]['both_wrong'] += 1
            results['by_difficulty'][difficulty]['both_wrong'] += 1

    return results


def check_correctness(prediction: str, reference: str, spatial_type: str) -> bool:
    """
    检查预测是否正确（简化版）
    实际应该使用deterministic.py中的match函数
    """
    pred_lower = prediction.lower().strip()
    ref_lower = reference.lower().strip()

    # 完全匹配
    if pred_lower == ref_lower:
        return True

    # 简单的关键词匹配
    if spatial_type == 'directional':
        directions = ['东', '西', '南', '北', '东北', '东南', '西北', '西南']
        for d in directions:
            if d in reference and d in prediction:
                return True
    elif spatial_type == 'metric':
        # 提取数字
        import re
        ref_nums = re.findall(r'\d+', reference)
        pred_nums = re.findall(r'\d+', prediction)
        if ref_nums and pred_nums:
            # 检查是否有相近的数字
            for rn in ref_nums:
                for pn in pred_nums:
                    if abs(int(rn) - int(pn)) < 50:  # 允许50公里误差
                        return True
    elif spatial_type == 'topological':
        # 拓扑关键词
        topo_keywords = ['内部', '包含', '相邻', '独立', '交叉', '边界']
        ref_has = [k for k in topo_keywords if k in reference]
        pred_has = [k for k in topo_keywords if k in prediction]
        if ref_has and pred_has and set(ref_has) & set(pred_has):
            return True
    elif spatial_type == 'composite':
        # 复合问题需要更复杂的判断
        pass

    return False


def analyze_error_patterns(predictions: Dict[str, Dict], test_data: Dict[str, Dict]) -> Dict[str, Any]:
    """
    分析错误模式
    """
    patterns = {
        'topological_bias': {
            'description': '拓扑关系偏见：倾向于回答"位于内部"',
            'count': 0,
            'samples': []
        },
        'distance_bias': {
            'description': '距离偏向：频繁输出"约1200公里"',
            'count': 0,
            'samples': []
        },
        'direction_confusion': {
            'description': '方向混淆：方向判断错误',
            'count': 0,
            'samples': []
        },
        'format_issues': {
            'description': '格式问题：输出格式不规范',
            'count': 0,
            'samples': []
        }
    }

    for sample_id, pred in predictions.items():
        if sample_id not in test_data:
            continue

        test_item = test_data[sample_id]
        prediction = pred['prediction']
        reference = test_item.get('answer', '')
        spatial_type = test_item.get('spatial_relation_type', '')

        # 检测拓扑偏见
        if spatial_type == 'topological':
            if '内部' in prediction and '内部' not in reference:
                patterns['topological_bias']['count'] += 1
                if len(patterns['topological_bias']['samples']) < 20:
                    patterns['topological_bias']['samples'].append({
                        'id': sample_id,
                        'question': test_item.get('question', ''),
                        'prediction': prediction,
                        'reference': reference
                    })

        # 检测距离偏向
        if '约1200公里' in prediction or '1200公里' in prediction:
            if '1200' not in reference:
                patterns['distance_bias']['count'] += 1
                if len(patterns['distance_bias']['samples']) < 20:
                    patterns['distance_bias']['samples'].append({
                        'id': sample_id,
                        'question': test_item.get('question', ''),
                        'prediction': prediction,
                        'reference': reference
                    })

        # 检测方向混淆
        if spatial_type == 'directional':
            if not check_correctness(prediction, reference, spatial_type):
                patterns['direction_confusion']['count'] += 1
                if len(patterns['direction_confusion']['samples']) < 20:
                    patterns['direction_confusion']['samples'].append({
                        'id': sample_id,
                        'question': test_item.get('question', ''),
                        'prediction': prediction,
                        'reference': reference
                    })

    return patterns


def generate_report(
    before_metrics: Dict,
    after_metrics: Dict,
    sample_diff: Dict,
    before_patterns: Dict,
    after_patterns: Dict,
    output_dir: str
) -> str:
    """生成分析报告"""

    report = []
    report.append("# 微调前后模型深度对比分析报告\n")
    report.append("生成时间: 2026-03-27\n\n")

    # 1. 整体指标对比
    report.append("## 1. 整体指标对比\n\n")
    report.append("| 指标 | 微调前 | 微调后 | 变化 | 变化率 |\n")
    report.append("|------|--------|--------|------|--------|\n")

    before_det = before_metrics.get('deterministic', {})
    after_det = after_metrics.get('deterministic', {})

    metrics_to_compare = [
        ('Overall Accuracy', 'accuracy', 'overall'),
        ('Directional Accuracy', 'accuracy', 'directional_accuracy'),
        ('Metric Accuracy', 'accuracy', 'metric_accuracy'),
        ('Topological Accuracy', 'accuracy', 'topological_accuracy'),
        ('Composite Accuracy', 'accuracy', 'composite_accuracy'),
        ('Format Valid Rate', 'format_valid_rate', None),
        ('BLEU-4', 'bleu4', None),
        ('ROUGE-L', 'rouge_l', None),
        ('Spatial F1', 'spatial_f1', 'overall'),
    ]

    for name, metric_key, sub_key in metrics_to_compare:
        if sub_key:
            before_val = before_det.get(metric_key, {})
            if isinstance(before_val, dict):
                before_val = before_val.get(sub_key, 0)
            after_val = after_det.get(metric_key, {})
            if isinstance(after_val, dict):
                after_val = after_val.get(sub_key, 0)
        else:
            before_val = before_det.get(metric_key, 0)
            after_val = after_det.get(metric_key, 0)

        # 确保值是数值类型
        if isinstance(before_val, dict) or isinstance(after_val, dict):
            continue

        change = after_val - before_val
        change_rate = (change / before_val * 100) if before_val != 0 else 0

        report.append(f"| {name} | {before_val:.4f} | {after_val:.4f} | {change:+.4f} | {change_rate:+.2f}% |\n")

    # 2. 样本级差异统计
    report.append("\n## 2. 样本级差异统计\n\n")
    stats = sample_diff['stats']
    report.append(f"- **总样本数**: {stats['total']}\n")
    report.append(f"- **退化样本** (正确→错误): {stats['regressed_count']} ({stats['regressed_count']/stats['total']*100:.2f}%)\n")
    report.append(f"- **改进样本** (错误→正确): {stats['improved_count']} ({stats['improved_count']/stats['total']*100:.2f}%)\n")
    report.append(f"- **持续正确**: {stats['both_correct_count']} ({stats['both_correct_count']/stats['total']*100:.2f}%)\n")
    report.append(f"- **持续错误**: {stats['both_wrong_count']} ({stats['both_wrong_count']/stats['total']*100:.2f}%)\n")

    # 按空间类型统计
    report.append("\n### 2.1 按空间类型分层\n\n")
    report.append("| 空间类型 | 退化 | 改进 | 持续正确 | 持续错误 |\n")
    report.append("|----------|------|------|----------|----------|\n")
    for stype, type_stats in sample_diff['by_type'].items():
        report.append(f"| {stype} | {type_stats['regressed']} | {type_stats['improved']} | {type_stats['both_correct']} | {type_stats['both_wrong']} |\n")

    # 按难度统计
    report.append("\n### 2.2 按难度分层\n\n")
    report.append("| 难度 | 退化 | 改进 | 持续正确 | 持续错误 |\n")
    report.append("|------|------|------|----------|----------|\n")
    for diff, diff_stats in sample_diff['by_difficulty'].items():
        report.append(f"| {diff} | {diff_stats['regressed']} | {diff_stats['improved']} | {diff_stats['both_correct']} | {diff_stats['both_wrong']} |\n")

    # 3. 错误模式分析
    report.append("\n## 3. 错误模式分析\n\n")

    report.append("### 3.1 微调前错误模式\n\n")
    for pattern_name, pattern_info in before_patterns.items():
        if pattern_info['count'] > 0:
            report.append(f"**{pattern_info['description']}**: {pattern_info['count']} 个样本\n\n")

    report.append("### 3.2 微调后错误模式\n\n")
    for pattern_name, pattern_info in after_patterns.items():
        if pattern_info['count'] > 0:
            report.append(f"**{pattern_info['description']}**: {pattern_info['count']} 个样本\n\n")
            if pattern_info['samples']:
                report.append("示例:\n\n")
                for i, sample in enumerate(pattern_info['samples'][:5], 1):
                    report.append(f"**样本 {i}** (ID: {sample['id']})\n")
                    report.append(f"- 问题: {sample['question'][:100]}...\n")
                    report.append(f"- 预测: {sample['prediction'][:100]}...\n")
                    report.append(f"- 参考: {sample['reference']}\n\n")

    # 4. 典型退化样本分析
    report.append("\n## 4. 典型退化样本分析\n\n")
    report.append("以下是微调前正确但微调后错误的样本（前10个）：\n\n")
    for i, sample in enumerate(sample_diff['regressed'][:10], 1):
        report.append(f"### 样本 {i} (ID: {sample['id']})\n\n")
        report.append(f"- **空间类型**: {sample['spatial_type']}\n")
        report.append(f"- **难度**: {sample['difficulty']}\n")
        report.append(f"- **问题**: {sample['question']}\n")
        report.append(f"- **参考答案**: {sample['reference']}\n")
        report.append(f"- **微调前预测**: {sample['before_prediction']}\n")
        report.append(f"- **微调后预测**: {sample['after_prediction']}\n\n")

    # 5. 典型改进样本分析
    report.append("\n## 5. 典型改进样本分析\n\n")
    report.append("以下是微调前错误但微调后正确的样本（前10个）：\n\n")
    for i, sample in enumerate(sample_diff['improved'][:10], 1):
        report.append(f"### 样本 {i} (ID: {sample['id']})\n\n")
        report.append(f"- **空间类型**: {sample['spatial_type']}\n")
        report.append(f"- **难度**: {sample['difficulty']}\n")
        report.append(f"- **问题**: {sample['question']}\n")
        report.append(f"- **参考答案**: {sample['reference']}\n")
        report.append(f"- **微调前预测**: {sample['before_prediction']}\n")
        report.append(f"- **微调后预测**: {sample['after_prediction']}\n\n")

    # 6. 微调失败原因诊断
    report.append("\n## 6. 微调失败原因诊断\n\n")

    # 分析退化>改进的情况
    if stats['regressed_count'] > stats['improved_count']:
        report.append("### 6.1 主要发现\n\n")
        report.append(f"**退化样本 ({stats['regressed_count']}) 多于改进样本 ({stats['improved_count']})**，说明微调过程可能存在以下问题：\n\n")

        # 检查拓扑偏见
        topo_before = before_patterns['topological_bias']['count']
        topo_after = after_patterns['topological_bias']['count']
        if topo_after > topo_before:
            report.append(f"1. **拓扑关系偏见加剧**: 微调后'位于内部'偏见从{topo_before}增加到{topo_after}\n")

        # 检查距离偏向
        dist_before = before_patterns['distance_bias']['count']
        dist_after = after_patterns['distance_bias']['count']
        if dist_after > dist_before:
            report.append(f"2. **距离数值偏向加剧**: '约1200公里'偏向从{dist_before}增加到{dist_after}\n")

        report.append("\n### 6.2 可能原因\n\n")
        report.append("1. **训练数据不平衡**: 某些类型的样本可能过多，导致模型产生偏见\n")
        report.append("2. **灾难性遗忘**: 微调过程中模型可能遗忘了部分原有能力\n")
        report.append("3. **过拟合**: 模型可能过拟合了训练数据中的某些模式\n")
        report.append("4. **提示词格式不一致**: 训练和推理使用的提示词格式可能存在差异\n")

    report_content = ''.join(report)

    # 保存报告
    report_path = os.path.join(output_dir, 'comparison_analysis_deep.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_content)

    return report_content


def main():
    # 文件路径
    before_pred_path = "/mnt/workspace/30_keyan/GeoKD-SR/exp/exp0/exp0/stage1_generation/outputs/predictions_qwen.jsonl"
    after_pred_path = "/mnt/workspace/30_keyan/GeoKD-SR/exp/exp0/qwen-1.5B-sft/eval_results_exp0/predictions.jsonl"
    before_metrics_path = "/mnt/workspace/30_keyan/GeoKD-SR/exp/exp0/exp0/stage2_evaluation/results/qwen_eval/metrics.json"
    after_metrics_path = "/mnt/workspace/30_keyan/GeoKD-SR/exp/exp0/qwen-1.5B-sft/eval_results_exp0/metrics.json"
    test_data_path = "/mnt/workspace/30_keyan/GeoKD-SR/data/splits/test.jsonl"
    output_dir = "/mnt/workspace/30_keyan/GeoKD-SR/exp/exp0/qwen-1.5B-sft/eval_results_exp0"

    print("=" * 60)
    print("微调前后模型深度对比分析")
    print("=" * 60)

    # 加载数据
    print("\n[1/6] 加载预测数据...")
    before_preds = load_predictions(before_pred_path)
    after_preds = load_predictions(after_pred_path)
    print(f"  微调前样本数: {len(before_preds)}")
    print(f"  微调后样本数: {len(after_preds)}")

    print("\n[2/6] 加载测试数据...")
    test_data = load_predictions(test_data_path)
    print(f"  测试样本数: {len(test_data)}")

    print("\n[3/6] 加载指标数据...")
    before_metrics = load_metrics(before_metrics_path)
    after_metrics = load_metrics(after_metrics_path)

    # 样本级差异分析
    print("\n[4/6] 进行样本级差异分析...")
    sample_diff = analyze_sample_differences(before_preds, after_preds, test_data)
    print(f"  退化样本: {sample_diff['stats']['regressed_count']}")
    print(f"  改进样本: {sample_diff['stats']['improved_count']}")

    # 错误模式分析
    print("\n[5/6] 进行错误模式分析...")
    before_patterns = analyze_error_patterns(before_preds, test_data)
    after_patterns = analyze_error_patterns(after_preds, test_data)
    print(f"  微调后拓扑偏见样本: {after_patterns['topological_bias']['count']}")
    print(f"  微调后距离偏向样本: {after_patterns['distance_bias']['count']}")

    # 生成报告
    print("\n[6/6] 生成分析报告...")
    report = generate_report(
        before_metrics, after_metrics,
        sample_diff,
        before_patterns, after_patterns,
        output_dir
    )

    # 保存样本差异详情
    sample_diff_path = os.path.join(output_dir, 'sample_differences.json')
    with open(sample_diff_path, 'w', encoding='utf-8') as f:
        # 转换defaultdict为普通dict
        sample_diff_copy = dict(sample_diff)
        sample_diff_copy['by_type'] = dict(sample_diff_copy['by_type'])
        sample_diff_copy['by_difficulty'] = dict(sample_diff_copy['by_difficulty'])
        json.dump(sample_diff_copy, f, ensure_ascii=False, indent=2)

    # 保存错误模式统计
    error_patterns_path = os.path.join(output_dir, 'error_patterns.json')
    with open(error_patterns_path, 'w', encoding='utf-8') as f:
        json.dump({
            'before': before_patterns,
            'after': after_patterns
        }, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("分析完成！")
    print("=" * 60)
    print(f"\n输出文件:")
    print(f"  - 分析报告: {os.path.join(output_dir, 'comparison_analysis_deep.md')}")
    print(f"  - 样本差异: {sample_diff_path}")
    print(f"  - 错误模式: {error_patterns_path}")


if __name__ == "__main__":
    main()
