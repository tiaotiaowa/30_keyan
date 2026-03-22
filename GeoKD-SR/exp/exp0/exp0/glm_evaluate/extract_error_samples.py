"""
================================================================================
GLM错误样本提取脚本 (V2)
================================================================================

功能:
    从GLM预测结果中提取所有评测错误的样本，用于后续分析

输入文件:
    - predictions_splits.jsonl: GLM预测结果
    - test.jsonl: 原始测试数据（包含完整信息）

输出文件:
    - error_samples.jsonl: 所有预测错误的样本

判断逻辑:
    直接使用原评测脚本DeterministicMetrics的判断逻辑，确保完全一致

作者: GeoKD-SR 项目组
日期: 2026-03-20
================================================================================
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any

# 添加评测模块路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'stage2_evaluation'))

from metrics.deterministic import DeterministicMetrics


def extract_error_samples(
    predictions_file: str,
    test_file: str,
    output_file: str
) -> Dict[str, Any]:
    """
    提取所有错误样本

    Args:
        predictions_file: 预测结果文件路径
        test_file: 原始测试数据文件路径
        output_file: 输出文件路径

    Returns:
        统计信息字典
    """
    # 初始化评测器（使用与原评测相同的配置）
    config = {
        'accuracy': {
            'directional_fuzzy': True,
            'distance_tolerance': 0.15
        }
    }
    metrics = DeterministicMetrics(config)

    # 读取预测结果
    predictions = []
    with open(predictions_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                predictions.append(json.loads(line))

    # 读取原始测试数据
    test_data = {}
    with open(test_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                test_data[data['id']] = data

    # 提取错误样本
    error_samples = []
    stats = {
        'total': 0,
        'correct': 0,
        'error': 0,
        'by_type': {
            'directional': {'correct': 0, 'error': 0},
            'metric': {'correct': 0, 'error': 0},
            'topological': {'correct': 0, 'error': 0},
            'composite': {'correct': 0, 'error': 0}
        }
    }

    for pred in predictions:
        stats['total'] += 1

        sample_id = pred.get('id', '')
        reference = pred.get('reference', '')
        prediction = pred.get('prediction', '')
        spatial_type = pred.get('spatial_type', 'unknown')
        difficulty = pred.get('difficulty', 'unknown')
        question = pred.get('question', '')

        # 使用原评测逻辑判断正确性
        is_correct = metrics._check_answer_correct(
            reference, prediction, spatial_type,
            fuzzy_direction=True,
            distance_tolerance=0.15
        )

        if is_correct:
            stats['correct'] += 1
            if spatial_type in stats['by_type']:
                stats['by_type'][spatial_type]['correct'] += 1
        else:
            stats['error'] += 1
            if spatial_type in stats['by_type']:
                stats['by_type'][spatial_type]['error'] += 1

            # 构建错误样本记录
            error_record = {
                'id': sample_id,
                'spatial_type': spatial_type,
                'difficulty': difficulty,
                'question': question,
                'reference': reference,
                'prediction': prediction
            }

            # 从原始测试数据获取更多信息
            if sample_id in test_data:
                original = test_data[sample_id]
                error_record['entities'] = original.get('entities', [])
                error_record['reasoning_chain'] = original.get('reasoning_chain', [])
                error_record['topology_subtype'] = original.get('topology_subtype', '')
                error_record['spatial_relation_type'] = original.get('spatial_relation_type', '')

            error_samples.append(error_record)

    # 写入错误样本
    with open(output_file, 'w', encoding='utf-8') as f:
        for sample in error_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')

    # 计算准确率
    stats['accuracy'] = stats['correct'] / stats['total'] if stats['total'] > 0 else 0
    for stype in stats['by_type']:
        total = stats['by_type'][stype]['correct'] + stats['by_type'][stype]['error']
        stats['by_type'][stype]['total'] = total
        stats['by_type'][stype]['accuracy'] = (
            stats['by_type'][stype]['correct'] / total if total > 0 else 0
        )

    return stats


def main():
    """主函数"""
    # 文件路径
    base_dir = Path(__file__).parent
    predictions_file = base_dir / 'predictions_splits.jsonl'
    test_file = base_dir.parent.parent.parent.parent / 'data' / 'splits' / 'test.jsonl'
    output_file = base_dir / 'error_samples.jsonl'

    print("=" * 60)
    print("GLM错误样本提取工具 V2")
    print("=" * 60)
    print(f"\n输入文件:")
    print(f"  - 预测结果: {predictions_file}")
    print(f"  - 测试数据: {test_file}")
    print(f"\n输出文件: {output_file}")

    # 检查文件是否存在
    if not predictions_file.exists():
        print(f"\n错误: 预测结果文件不存在 - {predictions_file}")
        return

    if not test_file.exists():
        print(f"\n错误: 测试数据文件不存在 - {test_file}")
        return

    # 提取错误样本
    stats = extract_error_samples(
        str(predictions_file),
        str(test_file),
        str(output_file)
    )

    # 打印统计信息
    print("\n" + "=" * 60)
    print("提取完成 - 统计信息")
    print("=" * 60)
    print(f"\n总体统计:")
    print(f"  - 总样本数: {stats['total']}")
    print(f"  - 正确数: {stats['correct']}")
    print(f"  - 错误数: {stats['error']}")
    print(f"  - 准确率: {stats['accuracy']*100:.2f}%")

    print(f"\n按空间类型统计:")
    for stype, type_stats in stats['by_type'].items():
        if type_stats['total'] > 0:
            print(f"  {stype}:")
            print(f"    - 正确: {type_stats['correct']}, 错误: {type_stats['error']}")
            print(f"    - 准确率: {type_stats['accuracy']*100:.2f}%")

    print(f"\n错误样本已保存到: {output_file}")
    print(f"共提取 {stats['error']} 个错误样本")

    # 与metrics.json对比
    print("\n" + "=" * 60)
    print("与metrics.json对比验证")
    print("=" * 60)
    print("\n预期错误数（来自metrics.json）:")
    print("  - directional: 42")
    print("  - metric: 34")
    print("  - composite: 95")
    print("  - topological: 150")
    print("  - 总计: 321")
    print(f"\n实际提取错误数:")
    print(f"  - directional: {stats['by_type']['directional']['error']}")
    print(f"  - metric: {stats['by_type']['metric']['error']}")
    print(f"  - composite: {stats['by_type']['composite']['error']}")
    print(f"  - topological: {stats['by_type']['topological']['error']}")
    print(f"  - 总计: {stats['error']}")


if __name__ == '__main__':
    main()
