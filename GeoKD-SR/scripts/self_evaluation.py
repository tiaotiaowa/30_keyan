"""
评测指标自评测验证脚本

目标：使用当前评测指标对原始数据集的答案进行自评测
理论预期：答案自己和自己比较应该达到100%准确率
实际结果：如果不是100%，说明评测指标设计存在问题
"""

import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "exp/exp0/exp0/stage2_evaluation"))
from metrics.deterministic import DeterministicMetrics


def prepare_self_eval_data(test_file: str, output_file: str):
    """
    准备自评测数据：prediction = answer

    Args:
        test_file: 原始测试数据文件路径
        output_file: 输出文件路径

    Returns:
        处理后的样本列表
    """
    samples = []
    with open(test_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            samples.append({
                "id": data["id"],
                "question": data["question"],
                "answer": data["answer"],
                "prediction": data["answer"],  # 预测 = 答案
                "reference": data["answer"],   # 参考 = 答案
                "spatial_type": data["spatial_relation_type"],
                "spatial_relation_type": data["spatial_relation_type"],
                "difficulty": data.get("difficulty", "medium")
            })

    with open(output_file, 'w', encoding='utf-8') as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + '\n')

    return samples


def run_self_evaluation(data_file: str, config: dict = None):
    """
    执行自评测并分析结果

    Args:
        data_file: 自评测数据文件路径
        config: 评测配置

    Returns:
        评测结果字典
    """
    metrics = DeterministicMetrics(config)

    results = {
        "total": 0,
        "correct": 0,
        "by_type": {
            "directional": {"total": 0, "correct": 0, "errors": []},
            "metric": {"total": 0, "correct": 0, "errors": []},
            "topological": {"total": 0, "correct": 0, "errors": []},
            "composite": {"total": 0, "correct": 0, "errors": []}
        }
    }

    with open(data_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            results["total"] += 1
            spatial_type = data.get("spatial_type", "unknown")

            # 使用 DeterministicMetrics 的检查方法
            is_correct = metrics._check_answer_correct(
                data["reference"],
                data["prediction"],
                spatial_type,
                True,  # fuzzy_direction
                0.15   # distance_tolerance
            )

            if spatial_type not in results["by_type"]:
                results["by_type"][spatial_type] = {"total": 0, "correct": 0, "errors": []}

            results["by_type"][spatial_type]["total"] += 1

            if is_correct:
                results["correct"] += 1
                results["by_type"][spatial_type]["correct"] += 1
            else:
                # 记录错误样本
                results["by_type"][spatial_type]["errors"].append({
                    "id": data["id"],
                    "question": data.get("question", ""),
                    "answer": data["answer"],
                    "reason": "自评测失败：答案无法匹配自己"
                })

    return results


def generate_self_eval_report(results: dict) -> str:
    """
    生成自评测报告

    Args:
        results: 评测结果字典

    Returns:
        报告文本
    """
    report = []
    report.append("# 评测指标自评测验证报告\n\n")
    report.append("## 验证目标\n\n")
    report.append("使用评测指标对原始数据集答案进行自评测，理论上应达到100%准确率。\n\n")
    report.append("**核心原理**：将预测值设为参考答案本身，如果评测指标设计合理，")
    report.append("答案和自己比较应该达到100%匹配。\n\n")

    report.append("## 总体结果\n\n")
    overall_acc = results["correct"] / results["total"] * 100 if results["total"] > 0 else 0
    report.append("| 指标 | 值 |\n")
    report.append("|------|------|\n")
    report.append(f"| 总体准确率 | {overall_acc:.2f}% |\n")
    report.append(f"| 预期准确率 | 100% |\n")
    report.append(f"| 差距 | {100 - overall_acc:.2f}% |\n")
    report.append(f"| 总样本数 | {results['total']} |\n")
    report.append(f"| 正确样本数 | {results['correct']} |\n")
    report.append(f"| 错误样本数 | {results['total'] - results['correct']} |\n\n")

    # 判断是否通过
    if overall_acc == 100:
        report.append("**结论**: 自评测通过，评测指标设计合理。\n\n")
    elif overall_acc >= 95:
        report.append(f"**结论**: 自评测基本通过，准确率{overall_acc:.2f}% >= 95%，但仍有{results['total'] - results['correct']}个样本未通过。\n\n")
    else:
        report.append(f"**结论**: 自评测未通过，准确率{overall_acc:.2f}% < 95%，评测指标存在问题需要修复。\n\n")

    report.append("## 按类型分析\n\n")
    report.append("| 类型 | 样本数 | 正确数 | 准确率 | 错误数 | 状态 |\n")
    report.append("|------|--------|--------|--------|--------|------|\n")

    for type_name, type_data in results["by_type"].items():
        if type_data["total"] > 0:
            acc = type_data["correct"] / type_data["total"] * 100
            status = "通过" if acc == 100 else "未通过"
            report.append(f"| {type_name} | {type_data['total']} | {type_data['correct']} | {acc:.2f}% | {len(type_data['errors'])} | {status} |\n")
        else:
            report.append(f"| {type_name} | 0 | 0 | N/A | 0 | 无数据 |\n")

    # 错误样本分析
    has_errors = any(len(type_data["errors"]) > 0 for type_data in results["by_type"].values())
    if has_errors:
        report.append("\n## 错误样本分析\n\n")
        report.append("以下样本在自评测中失败，说明评测指标无法正确识别这些答案：\n\n")

        for type_name, type_data in results["by_type"].items():
            if type_data["errors"]:
                report.append(f"### {type_name} 错误样本 ({len(type_data['errors'])}个)\n\n")
                for i, err in enumerate(type_data["errors"][:20], 1):  # 只显示前20个
                    report.append(f"#### {i}. `{err['id']}`\n\n")
                    report.append(f"- **问题**: {err.get('question', 'N/A')}\n")
                    report.append(f"- **答案**: `{err['answer']}`\n")
                    report.append(f"- **原因**: {err['reason']}\n\n")
                if len(type_data["errors"]) > 20:
                    report.append(f"... 还有{len(type_data['errors']) - 20}个错误样本未显示\n\n")
    else:
        report.append("\n## 错误样本分析\n\n")
        report.append("没有错误样本，所有样本自评测通过。\n\n")

    # 问题诊断
    report.append("## 问题诊断与建议\n\n")
    if overall_acc < 100:
        report.append("### 发现的问题\n\n")

        for type_name, type_data in results["by_type"].items():
            if type_data["errors"]:
                acc = type_data["correct"] / type_data["total"] * 100
                report.append(f"#### {type_name} 类型 (准确率: {acc:.2f}%)\n\n")
                report.append("可能的原因：\n")

                # 根据类型给出具体建议
                if type_name == "directional":
                    report.append("1. 方向关键词提取不完整（如：\"东偏北\"vs\"东北\"）\n")
                    report.append("2. 模糊方向匹配规则未覆盖所有变体\n")
                    report.append("3. 答案格式多样（如：\"东南方向\"vs\"东南\"）\n")
                elif type_name == "metric":
                    report.append("1. 距离数字提取失败（如：\"约1200公里\"vs\"1200公里\"）\n")
                    report.append("2. 容忍度设置过小导致严格匹配失败\n")
                    report.append("3. 单位变化处理不当（如：\"1200公里\"vs\"1200千米\"）\n")
                elif type_name == "topological":
                    report.append("1. 拓扑关键词匹配规则不完善\n")
                    report.append("2. 同义词未处理（如：\"相邻\"vs\"接壤\"）\n")
                elif type_name == "composite":
                    report.append("1. 复合关系的匹配逻辑过于严格\n")
                    report.append("2. 多要素匹配要求可能过高\n")

                report.append("\n建议的修复方案：\n")
                report.append("1. 扩展关键词库和别名映射\n")
                report.append("2. 改进答案预处理（去除标点、统一格式）\n")
                report.append("3. 调整匹配逻辑，增加容错性\n\n")
    else:
        report.append("未发现问题，评测指标设计合理。\n\n")

    return "".join(report)


if __name__ == "__main__":
    # 测试数据路径
    test_file = "D:/30_keyan/GeoKD-SR/data/splits/test.jsonl"
    output_file = "D:/30_keyan/GeoKD-SR/data/self_eval.jsonl"
    report_file = "D:/30_keyan/GeoKD-SR/results/self_eval_report.md"

    # 创建结果目录
    Path(report_file).parent.mkdir(parents=True, exist_ok=True)

    # 评测配置
    config = {
        'accuracy': {
            'directional_fuzzy': True,
            'distance_tolerance': 0.15
        },
        'spatial_keywords': {
            'directions': [
                "东", "南", "西", "北", "东北", "东南", "西北", "西南",
                "东偏北", "东偏南", "西偏北", "西偏南",
                "北偏东", "北偏西", "南偏东", "南偏西",
                "正北", "正南", "正东", "正西"
            ],
            'topological': [
                "相邻", "包含", "被包含", "交叉", "分离", "接壤", "重叠"
            ]
        }
    }

    print("=" * 60)
    print("评测指标自评测验证")
    print("=" * 60)

    # 准备数据
    print("\n[1/3] 准备自评测数据...")
    samples = prepare_self_eval_data(test_file, output_file)
    print(f"  处理样本数: {len(samples)}")
    print(f"  输出文件: {output_file}")

    # 执行评测
    print("\n[2/3] 执行自评测...")
    results = run_self_evaluation(output_file, config)

    # 生成报告
    print("\n[3/3] 生成报告...")
    report = generate_self_eval_report(results)

    # 保存报告
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)

    # 输出摘要
    print("\n" + "=" * 60)
    print("自评测结果摘要")
    print("=" * 60)
    overall_acc = results["correct"] / results["total"] * 100
    print(f"总体准确率: {overall_acc:.2f}%")
    print(f"预期准确率: 100%")
    print(f"差距: {100 - overall_acc:.2f}%")
    print(f"\n按类型统计:")
    for type_name, type_data in results["by_type"].items():
        if type_data["total"] > 0:
            acc = type_data["correct"] / type_data["total"] * 100
            print(f"  {type_name}: {acc:.2f}% ({type_data['correct']}/{type_data['total']})")

    print(f"\n报告已保存到: {report_file}")
    print("=" * 60)
