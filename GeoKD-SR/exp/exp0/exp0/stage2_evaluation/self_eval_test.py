"""
自评测数据准备和评估脚本
用于验证评测指标的正确性

原理：将预测值设为参考答案本身，理论上应达到100%准确率
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from metrics.deterministic import DeterministicMetrics
from metrics.semantic import SemanticMetrics


def prepare_self_eval_data(test_file: str, output_file: str):
    """
    准备自评测数据

    Args:
        test_file: 测试数据文件路径
        output_file: 输出预测文件路径

    Returns:
        样本数量
    """
    predictions = []

    with open(test_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data = json.loads(line)

                # 创建预测记录，预测值=参考答案
                prediction = {
                    'id': data.get('id', ''),
                    'question': data.get('question', ''),
                    'reference': data.get('answer', ''),  # 参考答案
                    'prediction': data.get('answer', ''),  # 预测值=参考答案（自评测核心）
                    'spatial_type': data.get('spatial_relation_type', ''),
                    'difficulty': data.get('difficulty', 'medium'),
                    'topology_subtype': data.get('topology_subtype', '')
                }
                predictions.append(prediction)

    # 保存预测结果
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        for pred in predictions:
            f.write(json.dumps(pred, ensure_ascii=False) + '\n')

    return len(predictions)


def run_self_evaluation(predictions_file: str, config: dict):
    """
    运行自评测

    Args:
        predictions_file: 预测文件路径
        config: 配置字典

    Returns:
        评测结果
    """
    # 加载预测数据
    predictions = []
    with open(predictions_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                predictions.append(json.loads(line))

    print(f"加载 {len(predictions)} 条预测数据")

    # 初始化指标计算器
    deterministic = DeterministicMetrics(config.get('deterministic', {}))

    # 计算确定性指标
    print("\n计算确定性指标...")
    det_results = deterministic.compute_all(predictions)

    # 按类型分层分析
    print("\n按空间关系类型分层分析...")
    type_results = {}

    for spatial_type in ['directional', 'metric', 'topological', 'composite']:
        type_preds = [p for p in predictions if p.get('spatial_type') == spatial_type]
        if type_preds:
            type_result = deterministic.compute_all(type_preds)
            # 修复：从by_type中获取正确数
            by_type_stats = type_result.get('accuracy', {}).get('by_type', {})
            type_results[spatial_type] = {
                'count': len(type_preds),
                'accuracy': type_result.get('accuracy', {}).get('overall', 0),
                'correct': by_type_stats.get(spatial_type, {}).get('correct', 0)
            }

    return {
        'total_samples': len(predictions),
        'deterministic': det_results,
        'by_type': type_results
    }


def generate_report(results: dict, output_file: str):
    """
    生成自评测报告

    Args:
        results: 评测结果
        output_file: 输出文件路径
    """
    report = []
    report.append("# 自评测验证报告\n")
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 总体结果
    report.append("\n## 验证目标\n")
    report.append("使用评测指标对原始数据集答案进行自评测，理论上应达到100%准确率。\n")
    report.append("\n**核心原理**：将预测值设为参考答案本身，如果评测指标设计合理，答案和自己比较应该达到100%匹配。\n")

    det = results.get('deterministic', {})
    accuracy = det.get('accuracy', {}).get('overall', 0)
    total = results.get('total_samples', 0)

    # 从by_type统计中计算正确样本数
    by_type_stats = det.get('accuracy', {}).get('by_type', {})
    correct = sum(stats.get('correct', 0) for stats in by_type_stats.values())

    report.append("\n## 总体结果\n")
    report.append(f"| 指标 | 值 |\n|------|------|\n")
    report.append(f"| 总体准确率 | {accuracy*100:.2f}% |\n")
    report.append(f"| 预期准确率 | 100% |\n")
    report.append(f"| 差距 | {abs(accuracy - 1.0)*100:.2f}% |\n")
    report.append(f"| 总样本数 | {total} |\n")
    report.append(f"| 正确样本数 | {correct} |\n")
    report.append(f"| 错误样本数 | {total - correct} |\n")

    # 判断结果
    if accuracy == 1.0:
        report.append("\n**结论**: ✅ 自评测通过，评测指标设计合理。\n")
    else:
        report.append(f"\n**结论**: ❌ 自评测未通过，准确率差距 {abs(accuracy - 1.0)*100:.2f}%\n")

    # 按类型分析
    report.append("\n## 按类型分析\n")
    report.append("| 类型 | 样本数 | 正确数 | 准确率 | 状态 |\n")
    report.append("|------|--------|--------|--------|------|--------|\n")

    for spatial_type, type_data in results.get('by_type', {}).items():
        count = type_data.get('count', 0)
        correct_count = type_data.get('correct', 0)
        acc = type_data.get('accuracy', 0)
        status = "✅ 通过" if acc == 1.0 else f"❌ 差距{abs(acc-1.0)*100:.2f}%"
        report.append(f"| {spatial_type} | {count} | {correct_count} | {acc*100:.2f}% | {status} |\n")

    # 其他指标
    report.append("\n## 其他确定性指标\n")
    report.append(f"| 指标 | 值 |\n|------|------|\n")
    report.append(f"| BLEU-4 | {det.get('bleu4', 0):.4f} |\n")
    report.append(f"| ROUGE-L | {det.get('rouge_l', 0):.4f} |\n")
    report.append(f"| 格式有效率 | {det.get('format_valid_rate', 0):.4f} |\n")
    spatial_f1 = det.get('spatial_f1', {})
    if isinstance(spatial_f1, dict):
        spatial_f1_val = spatial_f1.get('f1', 0)
    else:
        spatial_f1_val = spatial_f1 if spatial_f1 else 0
    report.append(f"| 空间F1 | {spatial_f1_val:.4f} |\n")

    # 保存报告
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(report)

    print(f"\n报告已保存: {output_file}")


def main():
    """主函数"""
    # 配置路径
    test_file = "D:/30_keyan/GeoKD-SR/data/splits/test.jsonl"
    output_dir = "D:/30_keyan/GeoKD-SR/exp/exp0/exp0/stage2_evaluation/self_eval_results"
    predictions_file = os.path.join(output_dir, "self_eval_predictions.jsonl")
    report_file = os.path.join(output_dir, "self_eval_report.md")

    # 评测配置
    config = {
        'deterministic': {
            'accuracy': {
                'directional_fuzzy': True,
                'topological_exact': True,
                'distance_tolerance': 0.15
            },
            'spatial_keywords': {
                'directions': ["东", "南", "西", "北", "东北", "东南", "西北", "西南",
                              "东偏北", "东偏南", "西偏北", "西偏南", "北偏东", "北偏西",
                              "南偏东", "南偏西", "正北", "正南", "正东", "正西"],
                'topological': ["相邻", "包含", "被包含", "交叉", "分离", "接壤", "重叠"],
                'distance_units': ["公里", "千米", "米"]
            }
        }
    }

    # Step 1: 准备自评测数据
    print("=" * 60)
    print("Step 1: 准备自评测数据")
    print("=" * 60)
    count = prepare_self_eval_data(test_file, predictions_file)
    print(f"已生成 {count} 条自评测预测数据")
    print(f"预测文件: {predictions_file}")

    # Step 2: 运行自评测
    print("\n" + "=" * 60)
    print("Step 2: 运行自评测")
    print("=" * 60)
    results = run_self_evaluation(predictions_file, config)

    # Step 3: 生成报告
    print("\n" + "=" * 60)
    print("Step 3: 生成报告")
    print("=" * 60)
    os.makedirs(output_dir, exist_ok=True)
    generate_report(results, report_file)

    # 打印摘要
    print("\n" + "=" * 60)
    print("自评测完成摘要")
    print("=" * 60)
    accuracy = results.get('deterministic', {}).get('accuracy', {}).get('overall', 0)
    print(f"总体准确率: {accuracy*100:.2f}%")
    print(f"总样本数: {results.get('total_samples', 0)}")

    if accuracy == 1.0:
        print("\n✅ 自评测通过！评测指标设计合理。")
    else:
        print(f"\n❌ 自评测未通过，请检查评测指标实现。")

    return results


if __name__ == "__main__":
    main()
