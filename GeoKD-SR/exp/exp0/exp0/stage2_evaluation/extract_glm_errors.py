"""
================================================================================
GLM错误样本提取脚本
================================================================================

目的:
    使用与evaluate.py完全相同的DeterministicMetrics判断逻辑，
    重新提取错误样本，确保结果与metrics.json一致。

使用方法:
    cd D:/30_keyan/GeoKD-SR/exp/exp0/exp0/stage2_evaluation
    python extract_glm_errors.py

输出文件:
    - glm_splits_eval/error_samples.jsonl: 所有错误样本（包含完整信息）
    - glm_splits_eval/error_stats.json: 错误样本统计信息

作者: GeoKD-SR 项目组
日期: 2026-03-20
================================================================================
"""

import json
import os
import sys
import yaml
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict
from datetime import datetime

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from metrics.deterministic import DeterministicMetrics


def load_jsonl(file_path: str) -> List[Dict]:
    """加载JSONL文件"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def save_jsonl(data: List[Dict], file_path: str):
    """保存JSONL文件"""
    with open(file_path, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')


def save_json(data: Dict, file_path: str):
    """保存JSON文件"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def determine_error_type(spatial_type: str, reference: str, prediction: str, metrics: DeterministicMetrics) -> str:
    """
    根据空间类型和具体内容判断错误类型

    Args:
        spatial_type: 空间类型
        reference: 参考答案
        prediction: 预测答案
        metrics: DeterministicMetrics实例

    Returns:
        str: 错误类型描述
    """
    ref_lower = reference.lower().strip()
    pred_lower = prediction.lower().strip()

    if spatial_type == 'directional':
        # 检查方向是否正确
        ref_dir = metrics._extract_direction(ref_lower)
        pred_dir = metrics._extract_direction(pred_lower)
        if not pred_dir:
            return "方向未识别"
        elif ref_dir != pred_dir:
            return f"方向错误（应为{ref_dir}，预测为{pred_dir}）"
        else:
            return "方向格式问题"

    elif spatial_type == 'metric':
        # 检查距离
        import re
        ref_numbers = re.findall(r'(\d+(?:\.\d+)?)', ref_lower)
        pred_numbers = re.findall(r'(\d+(?:\.\d+)?)', pred_lower)
        if not pred_numbers:
            return "距离未识别"
        elif ref_numbers and pred_numbers:
            ref_dist = float(ref_numbers[0])
            pred_dist = float(pred_numbers[0])
            diff = abs(ref_dist - pred_dist)
            tolerance = max(ref_dist * 0.15, 50)
            if pred_dist < ref_dist - tolerance:
                return f"距离偏小（应为约{ref_dist}km，预测{pred_dist}km）"
            else:
                return f"距离偏大（应为约{ref_dist}km，预测{pred_dist}km）"
        return "距离错误"

    elif spatial_type == 'topological':
        # 检查拓扑类型
        ref_type = metrics._extract_topology_type(ref_lower)
        pred_type = metrics._extract_topology_type(pred_lower)
        if pred_type is None:
            return "拓扑关系未识别"
        elif ref_type != pred_type:
            type_names = {
                'within': '包含于',
                'contains': '包含',
                'adjacent': '相邻',
                'disjoint': '分离',
                'overlap': '重叠'
            }
            ref_name = type_names.get(ref_type, ref_type)
            pred_name = type_names.get(pred_type, pred_type)
            return f"拓扑类型错误（应为{ref_name}，预测为{pred_name}）"
        return "拓扑描述错误"

    elif spatial_type == 'composite':
        # 复合问题，检查是方向错误还是距离错误
        dir_match = metrics._check_direction_match(ref_lower, pred_lower, True)
        dist_match = metrics._check_distance_match(ref_lower, pred_lower, 0.15)

        errors = []
        if not dir_match:
            ref_dir = metrics._extract_direction(ref_lower)
            pred_dir = metrics._extract_direction(pred_lower)
            if pred_dir:
                errors.append(f"方向错误（应为{ref_dir}，预测为{pred_dir}）")
            else:
                errors.append("方向未识别")
        if not dist_match:
            import re
            pred_numbers = re.findall(r'(\d+(?:\.\d+)?)', pred_lower)
            if pred_numbers:
                errors.append("距离错误")
            else:
                errors.append("距离未识别")

        if errors:
            return "；".join(errors)
        return "复合错误"

    return "未知错误"


def extract_error_samples(
    predictions_file: str,
    test_file: str,
    output_dir: str,
    config_file: str = None
):
    """
    提取错误样本

    Args:
        predictions_file: GLM预测结果文件路径
        test_file: 原始测试数据文件路径
        output_dir: 输出目录
        config_file: 配置文件路径（可选，默认使用eval_config.yaml）
    """
    print("=" * 60)
    print("GLM错误样本提取脚本")
    print("=" * 60)

    # 1. 加载配置文件
    if config_file is None:
        config_file = str(Path(__file__).parent / "config" / "eval_config.yaml")

    with open(config_file, 'r', encoding='utf-8') as f:
        full_config = yaml.safe_load(f)

    # 使用与evaluate.py相同的配置
    metrics_config = full_config.get('metrics', {}).get('deterministic', {})

    # 初始化DeterministicMetrics（使用与evaluate.py相同的配置）
    metrics = DeterministicMetrics(metrics_config)
    print(f"[INFO] 已初始化DeterministicMetrics")
    print(f"       - 配置文件: {config_file}")
    print(f"       - directional_fuzzy: {metrics_config.get('accuracy', {}).get('directional_fuzzy', True)}")
    print(f"       - distance_tolerance: {metrics_config.get('accuracy', {}).get('distance_tolerance', 0.15)}")

    # 从配置中获取accuracy设置
    accuracy_config = metrics_config.get('accuracy', {})
    fuzzy_direction = accuracy_config.get('directional_fuzzy', True)
    distance_tolerance = accuracy_config.get('distance_tolerance', 0.15)

    # 2. 加载预测结果
    print(f"\n[INFO] 加载预测结果: {predictions_file}")
    predictions = load_jsonl(predictions_file)
    print(f"       共加载 {len(predictions)} 条预测结果")

    # 3. 加载原始测试数据（用于获取完整信息）
    print(f"\n[INFO] 加载原始测试数据: {test_file}")
    test_data = load_jsonl(test_file)
    test_data_map = {item['id']: item for item in test_data}
    print(f"       共加载 {len(test_data)} 条测试数据")

    # 4. 提取错误样本
    print(f"\n[INFO] 开始提取错误样本...")

    error_samples = []
    correct_samples = []

    # 统计信息
    stats = {
        'total': len(predictions),
        'correct': 0,
        'error': 0,
        'by_type': defaultdict(lambda: {'correct': 0, 'error': 0, 'total': 0}),
        'by_difficulty': defaultdict(lambda: {'correct': 0, 'error': 0, 'total': 0}),
        'error_types': defaultdict(int)
    }

    accuracy_config = metrics_config.get('accuracy', {})
    fuzzy_direction = accuracy_config.get('directional_fuzzy', True)
    distance_tolerance = accuracy_config.get('distance_tolerance', 0.15)

    for pred in predictions:
        sample_id = pred.get('id', '')
        spatial_type = pred.get('spatial_type', 'unknown')
        reference = pred.get('reference', '')
        prediction = pred.get('prediction', '')
        difficulty = pred.get('difficulty', 'unknown')

        # 更新统计
        stats['by_type'][spatial_type]['total'] += 1
        stats['by_difficulty'][difficulty]['total'] += 1

        # 使用与evaluate.py相同的判断逻辑
        is_correct = metrics._check_answer_correct(
            reference, prediction, spatial_type,
            fuzzy_direction, distance_tolerance
        )

        if is_correct:
            stats['correct'] += 1
            stats['by_type'][spatial_type]['correct'] += 1
            stats['by_difficulty'][difficulty]['correct'] += 1
        else:
            stats['error'] += 1
            stats['by_type'][spatial_type]['error'] += 1
            stats['by_difficulty'][difficulty]['error'] += 1

            # 获取原始测试数据中的完整信息
            test_item = test_data_map.get(sample_id, {})

            # 判断错误类型
            error_type = determine_error_type(spatial_type, reference, prediction, metrics)
            stats['error_types'][error_type] += 1

            # 构建错误样本
            error_sample = {
                'id': sample_id,
                'spatial_type': spatial_type,
                'difficulty': difficulty,
                'question': pred.get('question', test_item.get('question', '')),
                'reference': reference,
                'prediction': prediction,
                'error_type': error_type,
                # 从原始测试数据中获取额外信息
                'entities': test_item.get('entities', []),
                'reasoning_chain': test_item.get('reasoning_chain', []),
                'spatial_tokens': test_item.get('spatial_tokens', []),
                'entity_to_token': test_item.get('entity_to_token', {}),
            }

            # 如果是拓扑类型，添加子类型信息
            if spatial_type == 'topological':
                ref_type = metrics._extract_topology_type(reference.lower())
                pred_type = metrics._extract_topology_type(prediction.lower())
                error_sample['topology_subtype_ref'] = ref_type
                error_sample['topology_subtype_pred'] = pred_type

            error_samples.append(error_sample)

    # 5. 计算准确率
    overall_accuracy = stats['correct'] / stats['total'] if stats['total'] > 0 else 0

    # 6. 准备输出统计信息
    output_stats = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'script': 'extract_glm_errors.py',
            'config_file': config_file,
            'metrics_config': metrics_config
        },
        'summary': {
            'total_samples': stats['total'],
            'correct_samples': stats['correct'],
            'error_samples': stats['error'],
            'overall_accuracy': f"{overall_accuracy:.4f} ({stats['correct']}/{stats['total']})"
        },
        'by_spatial_type': {},
        'by_difficulty': {},
        'error_types_distribution': dict(stats['error_types'])
    }

    # 按空间类型统计
    for stype, type_stats in stats['by_type'].items():
        acc = type_stats['correct'] / type_stats['total'] if type_stats['total'] > 0 else 0
        output_stats['by_spatial_type'][stype] = {
            'total': type_stats['total'],
            'correct': type_stats['correct'],
            'error': type_stats['error'],
            'accuracy': f"{acc:.4f}"
        }

    # 按难度统计
    for diff, diff_stats in stats['by_difficulty'].items():
        acc = diff_stats['correct'] / diff_stats['total'] if diff_stats['total'] > 0 else 0
        output_stats['by_difficulty'][diff] = {
            'total': diff_stats['total'],
            'correct': diff_stats['correct'],
            'error': diff_stats['error'],
            'accuracy': f"{acc:.4f}"
        }

    # 7. 保存结果
    os.makedirs(output_dir, exist_ok=True)

    error_samples_file = os.path.join(output_dir, 'error_samples.jsonl')
    error_stats_file = os.path.join(output_dir, 'error_stats.json')

    save_jsonl(error_samples, error_samples_file)
    print(f"\n[INFO] 错误样本已保存: {error_samples_file}")
    print(f"       共 {len(error_samples)} 条错误样本")

    save_json(output_stats, error_stats_file)
    print(f"\n[INFO] 统计信息已保存: {error_stats_file}")

    # 8. 打印摘要
    print("\n" + "=" * 60)
    print("提取结果摘要")
    print("=" * 60)
    print(f"总样本数: {stats['total']}")
    print(f"正确样本: {stats['correct']} ({overall_accuracy*100:.2f}%)")
    print(f"错误样本: {stats['error']} ({(1-overall_accuracy)*100:.2f}%)")
    print()

    print("按空间类型统计:")
    print("-" * 50)
    print(f"{'类型':<15} {'总数':<8} {'正确':<8} {'错误':<8} {'准确率':<10}")
    print("-" * 50)
    for stype in ['directional', 'metric', 'topological', 'composite']:
        if stype in stats['by_type']:
            type_stats = stats['by_type'][stype]
            acc = type_stats['correct'] / type_stats['total'] if type_stats['total'] > 0 else 0
            print(f"{stype:<15} {type_stats['total']:<8} {type_stats['correct']:<8} {type_stats['error']:<8} {acc*100:.2f}%")
    print()

    print("错误类型分布（Top 10）:")
    print("-" * 50)
    sorted_error_types = sorted(stats['error_types'].items(), key=lambda x: x[1], reverse=True)[:10]
    for error_type, count in sorted_error_types:
        print(f"  {error_type}: {count}")

    print("\n" + "=" * 60)
    print("验证：与metrics.json对比")
    print("=" * 60)
    print(f"预期错误数: 321 (来自 metrics.json)")
    print(f"实际错误数: {stats['error']}")
    if stats['error'] == 321:
        print("[PASS] 验证通过！错误样本数量与 metrics.json 一致")
    else:
        print(f"[FAIL] 验证失败！差异: {abs(stats['error'] - 321)}")

    # 验证各类型错误数
    expected_errors = {
        'directional': 42,
        'metric': 34,
        'composite': 95,
        'topological': 150
    }
    print("\n各类型验证:")
    all_match = True
    for stype, expected in expected_errors.items():
        actual = stats['by_type'].get(stype, {}).get('error', 0)
        match = "[PASS]" if actual == expected else "[FAIL]"
        print(f"  {stype}: 预期 {expected}, 实际 {actual} {match}")
        if actual != expected:
            all_match = False

    if all_match:
        print("\n[PASS] 所有类型验证通过！")
    else:
        print("\n[FAIL] 存在差异，请检查判断逻辑")

    return error_samples, output_stats


if __name__ == "__main__":
    # 配置路径
    BASE_DIR = Path(__file__).parent

    predictions_file = str(BASE_DIR.parent / "glm_evaluate" / "predictions_splits.jsonl")
    # 直接指定正确的test.jsonl路径
    test_file = "D:/30_keyan/GeoKD-SR/data/splits/test.jsonl"
    output_dir = str(BASE_DIR / "results" / "glm_splits_eval")

    # 检查文件是否存在
    if not os.path.exists(predictions_file):
        print(f"错误: 预测文件不存在: {predictions_file}")
        sys.exit(1)

    if not os.path.exists(test_file):
        print(f"错误: 测试文件不存在: {test_file}")
        sys.exit(1)

    # 执行提取
    extract_error_samples(predictions_file, test_file, output_dir)
