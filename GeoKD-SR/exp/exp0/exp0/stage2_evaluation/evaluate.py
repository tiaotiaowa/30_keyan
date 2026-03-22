"""
Stage 2: 评测计算脚本
读取 Stage 1 生成的预测结果，计算评测指标
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

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from metrics.deterministic import DeterministicMetrics
from metrics.semantic import SemanticMetrics

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Evaluator:
    """评测器"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化评测器

        Args:
            config: 配置字典
        """
        self.config = config
        self.predictions = []

        # 初始化指标计算器
        metrics_config = config.get('metrics', {})

        self.deterministic_metrics = DeterministicMetrics(
            metrics_config.get('deterministic', {})
        )

        if metrics_config.get('semantic', {}).get('enabled', True):
            self.semantic_metrics = SemanticMetrics(
                metrics_config.get('semantic', {})
            )
        else:
            self.semantic_metrics = None

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
                'total_samples': len(self.predictions)
            }
        }

        # 1. 计算确定性指标
        logger.info("计算确定性指标...")
        results['deterministic'] = self.deterministic_metrics.compute_all(self.predictions)

        # 2. 计算语义指标
        if self.semantic_metrics:
            logger.info("计算语义指标（BERTScore）...")
            results['semantic'] = self.semantic_metrics.compute_all(self.predictions)

        # 3. 分层分析
        stratified_config = self.config.get('stratified_analysis', {})

        if stratified_config.get('by_spatial_type', True):
            logger.info("按空间类型分层分析...")
            results['by_spatial_type'] = self.deterministic_metrics.compute_by_type(self.predictions)
            if self.semantic_metrics:
                results['semantic_by_type'] = self.semantic_metrics.compute_by_type(self.predictions)

        if stratified_config.get('by_difficulty', True):
            logger.info("按难度分层分析...")
            results['by_difficulty'] = self.deterministic_metrics.compute_by_difficulty(self.predictions)
            if self.semantic_metrics:
                results['semantic_by_difficulty'] = self.semantic_metrics.compute_by_difficulty(self.predictions)

        return results

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
        report.append("# GeoKD-SR Qwen2.5-1.5B 评测报告\n")
        report.append(f"生成时间: {results['metadata']['timestamp']}\n")
        report.append(f"样本数量: {results['metadata']['total_samples']}\n")

        # 确定性指标
        report.append("\n## 1. 确定性指标\n")
        det = results.get('deterministic', {})

        report.append("### 1.1 整体指标\n")
        report.append(f"| 指标 | 值 |\n|------|----|\n")
        report.append(f"| 总体准确率 | {det.get('accuracy', {}).get('overall', 0):.4f} |\n")
        report.append(f"| 格式有效率 | {det.get('format_valid_rate', 0):.4f} |\n")
        report.append(f"| BLEU-4 | {det.get('bleu4', 0):.4f} |\n")
        report.append(f"| ROUGE-L | {det.get('rouge_l', 0):.4f} |\n")

        spatial_f1 = det.get('spatial_f1', {})
        report.append(f"| 空间关键词 Precision | {spatial_f1.get('precision', 0):.4f} |\n")
        report.append(f"| 空间关键词 Recall | {spatial_f1.get('recall', 0):.4f} |\n")
        report.append(f"| 空间关键词 F1 | {spatial_f1.get('f1', 0):.4f} |\n")

        # 按空间类型分层
        report.append("\n### 1.2 按空间类型分层准确率\n")
        report.append("| 空间类型 | 准确率 |\n|----------|--------|\n")
        by_type = results.get('by_spatial_type', {})
        for stype, metrics in by_type.items():
            acc = metrics.get('accuracy', {}).get('overall', 0)
            report.append(f"| {stype} | {acc:.4f} |\n")

        # 语义指标
        if 'semantic' in results:
            report.append("\n## 2. 语义指标（BERTScore）\n")
            sem = results.get('semantic', {})
            report.append(f"| 指标 | 值 |\n|------|----|\n")
            report.append(f"| BERTScore Precision | {sem.get('bertscore_precision', 0):.4f} |\n")
            report.append(f"| BERTScore Recall | {sem.get('bertscore_recall', 0):.4f} |\n")
            report.append(f"| BERTScore F1 | {sem.get('bertscore_f1', 0):.4f} |\n")

        # 按难度分层
        report.append("\n## 3. 按难度分层分析\n")
        report.append("| 难度 | 准确率 | BLEU-4 | ROUGE-L |\n|------|--------|--------|--------|\n")
        by_diff = results.get('by_difficulty', {})
        for diff, metrics in by_diff.items():
            acc = metrics.get('accuracy', {}).get('overall', 0)
            bleu = metrics.get('bleu4', 0)
            rouge = metrics.get('rouge_l', 0)
            report.append(f"| {diff} | {acc:.4f} | {bleu:.4f} | {rouge:.4f} |\n")

        # 示例分析
        report_config = self.config.get('report', {})
        if report_config.get('include_examples', True):
            report.append("\n## 4. 示例分析\n")
            max_examples = report_config.get('max_examples', 10)

            # 展示一些预测示例
            for i, pred in enumerate(self.predictions[:max_examples]):
                report.append(f"\n### 示例 {i+1}\n")
                report.append(f"- **ID**: {pred.get('id', 'N/A')}\n")
                report.append(f"- **空间类型**: {pred.get('spatial_type', 'N/A')}\n")
                report.append(f"- **难度**: {pred.get('difficulty', 'N/A')}\n")
                report.append(f"- **问题**: {pred.get('question', 'N/A')}\n")
                report.append(f"- **参考答案**: {pred.get('reference', 'N/A')}\n")
                report.append(f"- **模型预测**: {pred.get('prediction', 'N/A')}\n")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(report)


def main():
    parser = argparse.ArgumentParser(description='Stage 2: 评测计算')
    parser.add_argument(
        '--predictions',
        type=str,
        default='../stage1_generation/outputs/predictions.jsonl',
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
    with open(args.config, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 覆盖配置中的路径
    config['data']['predictions_file'] = args.predictions
    config['data']['output_dir'] = args.output

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
