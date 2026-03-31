"""
Stage 2: 评测计算脚本 (Qwen2.5-7B-Instruct)
读取 Stage 1 生成的预测结果，计算评测指标
复用 exp/exp0/exp0/stage2_evaluation/metrics 模块（15%距离容差）
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import yaml

# 添加统一评价模块路径（使用15%容差版本）
UNIFIED_EVAL_PATH = Path(__file__).resolve().parents[2] / "exp0" / "stage2_evaluation"
sys.path.insert(0, str(UNIFIED_EVAL_PATH))

from metrics.deterministic import DeterministicMetrics

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Evaluator:
    """评测器（使用统一指标模块，15%距离容差）"""

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化评测器

        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.predictions = []

        # 初始化确定性指标计算器（使用15%容差）
        metrics_config = self.config.get('metrics', {})
        self.deterministic_metrics = DeterministicMetrics(
            metrics_config.get('deterministic', {})
        )

    def load_predictions(self, predictions_file: str) -> List[Dict]:
        """
        加载预测结果

        Args:
            predictions_file: 预测结果文件路径

        Returns:
            预测结果列表
        """
        predictions = []
        with open(predictions_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    predictions.append(json.loads(line))

        logger.info(f"加载了 {len(predictions)} 条预测结果")
        self.predictions = predictions
        return predictions

    def run_evaluation(self) -> Dict[str, Any]:
        """
        运行完整评测

        Returns:
            评测结果字典
        """
        if not self.predictions:
            raise ValueError("没有预测结果，请先加载预测文件")

        results = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'total_samples': len(self.predictions),
                'model': 'Qwen2.5-7B-Instruct'
            }
        }

        # 1. 计算确定性指标
        logger.info("计算确定性指标...")
        results['deterministic'] = self._compute_deterministic_metrics()

        # 2. 按空间类型分层分析
        if self.config.get('stratified_analysis', {}).get('by_spatial_type', True):
            logger.info("按空间类型分层分析...")
            results['by_spatial_type'] = self._compute_by_spatial_type()

        # 3. 按难度分层分析
        if self.config.get('stratified_analysis', {}).get('by_difficulty', True):
            logger.info("按难度分层分析...")
            results['by_difficulty'] = self._compute_by_difficulty()

        return results

    def _compute_deterministic_metrics(self) -> Dict[str, Any]:
        """计算确定性指标（使用统一指标模块）"""
        return self.deterministic_metrics.compute_all(self.predictions)

    def _compute_by_spatial_type(self) -> Dict[str, Any]:
        """按空间类型分层计算指标（使用统一指标模块）"""
        return self.deterministic_metrics.compute_by_type(self.predictions)

    def _compute_by_difficulty(self) -> Dict[str, Any]:
        """按难度分层计算指标（使用统一指标模块）"""
        return self.deterministic_metrics.compute_by_difficulty(self.predictions)

    def save_results(self, results: Dict[str, Any], output_dir: str):
        """
        保存评测结果

        Args:
            results: 评测结果
            output_dir: 输出目录
        """
        os.makedirs(output_dir, exist_ok=True)

        # 保存JSON结果
        json_path = os.path.join(output_dir, 'metrics.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"JSON结果已保存: {json_path}")

        # 生成Markdown报告
        report_path = os.path.join(output_dir, 'report.md')
        self._generate_report(results, report_path)
        logger.info(f"Markdown报告已保存: {report_path}")

        return json_path, report_path

    def _generate_report(self, results: Dict[str, Any], output_path: str):
        """生成Markdown评测报告"""
        report = []
        report.append("# Qwen2.5-7B-Instruct 评测报告\n\n")
        report.append(f"**生成时间**: {results['metadata']['timestamp']}\n\n")
        report.append(f"**样本数量**: {results['metadata']['total_samples']}\n\n")

        # 确定性指标
        report.append("## 1. 整体指标\n\n")
        det = results.get('deterministic', {})

        report.append("| 指标 | 值 |\n|------|----|\n")
        acc = det.get('accuracy', {})
        report.append(f"| 总体准确率 | {acc.get('overall', 0):.4f} |\n")
        report.append(f"| 方向准确率 | {acc.get('directional_accuracy', 0):.4f} |\n")
        report.append(f"| 拓扑准确率 | {acc.get('topological_accuracy', 0):.4f} |\n")
        report.append(f"| 度量准确率 | {acc.get('metric_accuracy', 0):.4f} |\n")
        report.append(f"| 组合准确率 | {acc.get('composite_accuracy', 0):.4f} |\n")
        report.append(f"| 格式有效率 | {det.get('format_valid_rate', 0):.4f} |\n")
        report.append(f"| BLEU-4 | {det.get('bleu4', 0):.4f} |\n")
        report.append(f"| ROUGE-L | {det.get('rouge_l', 0):.4f} |\n")

        spatial_f1 = det.get('spatial_f1', {})
        report.append(f"| 空间F1-Precision | {spatial_f1.get('precision', 0):.4f} |\n")
        report.append(f"| 空间F1-Recall | {spatial_f1.get('recall', 0):.4f} |\n")
        report.append(f"| 空间F1-F1 | {spatial_f1.get('f1', 0):.4f} |\n")

        # 按空间类型分层
        report.append("\n## 2. 按空间类型分层\n\n")
        report.append("| 空间类型 | 数量 | 准确率 | BLEU-4 | ROUGE-L | 空间F1 |\n")
        report.append("|----------|------|--------|--------|---------|--------|\n")

        by_type = results.get('by_spatial_type', {})
        for stype, metrics in sorted(by_type.items()):
            acc = metrics.get('accuracy', {}).get('overall', 0)
            bleu = metrics.get('bleu4', 0)
            rouge = metrics.get('rouge_l', 0)
            f1 = metrics.get('spatial_f1', {}).get('f1', 0)
            report.append(f"| {stype} | {metrics.get('total', 0)} | {acc:.4f} | {bleu:.4f} | {rouge:.4f} | {f1:.4f} |\n")

        # 按难度分层
        report.append("\n## 3. 按难度分层\n\n")
        report.append("| 难度 | 数量 | 准确率 | BLEU-4 | ROUGE-L |\n")
        report.append("|------|------|--------|--------|--------|\n")

        by_diff = results.get('by_difficulty', {})
        for diff, metrics in sorted(by_diff.items()):
            acc = metrics.get('accuracy', {}).get('overall', 0)
            bleu = metrics.get('bleu4', 0)
            rouge = metrics.get('rouge_l', 0)
            report.append(f"| {diff} | {metrics.get('total', 0)} | {acc:.4f} | {bleu:.4f} | {rouge:.4f} |\n")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(report)


def main():
    parser = argparse.ArgumentParser(description='Stage 2: 评测计算 (Qwen2.5-7B)')
    parser.add_argument(
        '--predictions',
        type=str,
        required=True,
        help='预测结果文件路径'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config/eval_config.yaml',
        help='配置文件路径'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='./results',
        help='输出目录'
    )
    args = parser.parse_args()

    # 加载配置
    config = {}
    if os.path.exists(args.config):
        with open(args.config, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

    # 创建评测器
    evaluator = Evaluator(config)

    # 加载预测结果
    evaluator.load_predictions(args.predictions)

    # 运行评测
    results = evaluator.run_evaluation()

    # 保存结果
    evaluator.save_results(results, args.output)

    logger.info("评测完成！")


if __name__ == "__main__":
    main()
