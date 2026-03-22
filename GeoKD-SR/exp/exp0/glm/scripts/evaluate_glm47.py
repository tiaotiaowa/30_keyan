"""
GLM-4.7 评测主脚本

用法:
    # 测试5条样本
    python evaluate_glm47.py --config config/glm47_eval_config.yaml --sample_size 5

    # 完整评测
    python evaluate_glm47.py --config config/glm47_eval_config.yaml --dataset both

    # 仅评测含坐标版本
    python evaluate_glm47.py --config config/glm47_eval_config.yaml --dataset split_coords

更新时间: 2026-03-17
修复内容:
    - 添加空值检查 (calculate_all_metrics中 if not items: continue)
    - 添加tqdm进度条支持 (run_inference函数)
    - 使用logging模块替代print语句
    - 复用 exp/exp0/metrics/deterministic.py 中的指标计算函数
"""

import os
import sys
import json
import yaml
import argparse
import re
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from collections import defaultdict, Counter

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 添加项目根目录到路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 导入本地模块
sys.path.insert(0, str(SCRIPT_DIR.parent))
from scripts.glm47_client import GLM47Client
from prompts.inference_prompt import format_inference_prompt
from prompts.eval_prompt import format_eval_prompt, parse_eval_response

# 尝试导入tqdm进度条
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    logger.warning("未安装tqdm，将使用简单进度显示。安装: pip install tqdm")

# 尝试导入确定性指标模块
try:
    # 添加metrics目录到路径
    METRICS_DIR = PROJECT_ROOT / "exp" / "exp0" / "metrics"
    sys.path.insert(0, str(METRICS_DIR.parent))
    from metrics.deterministic import (
        calculate_overall_accuracy,
        calculate_format_valid_rate as calc_format_valid_rate,
        calculate_corpus_bleu_4,
        calculate_corpus_rouge_l,
        calculate_corpus_spatial_f1
    )
    HAS_DETERMINISTIC = True
    logger.info("成功导入exp0/metrics/deterministic.py")
except ImportError as e:
    HAS_DETERMINISTIC = False
    logger.warning(f"无法导入deterministic模块，将使用内置简化版: {e}")


def load_test_data(file_path: str, sample_size: Optional[int] = None) -> List[Dict]:
    """加载测试数据"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))

    if sample_size:
        data = data[:sample_size]

    logger.info(f"加载数据: {len(data)} 条 from {file_path}")
    return data


def run_inference(
    client: GLM47Client,
    data: List[Dict],
    output_path: Path,
    checkpoint_path: Optional[Path] = None
) -> List[Dict]:
    """运行推理"""
    logger.info("="*60)
    logger.info("Phase 2: GLM-4.7 推理")
    logger.info("="*60)

    results = []
    total = len(data)

    # 检查checkpoint
    start_idx = 0
    if checkpoint_path and checkpoint_path.exists():
        with open(checkpoint_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    results.append(json.loads(line))
        start_idx = len(results)
        logger.info(f"从checkpoint恢复: {start_idx} 条")

    logger.info(f"处理数据: {total} 条，从第 {start_idx + 1} 条开始")

    # 使用tqdm进度条或简单迭代
    iterator = range(start_idx, total)
    if HAS_TQDM:
        iterator = tqdm(iterator, desc="推理进度", unit="条")

    # 处理每条数据
    for i in iterator:
        item = data[i]

        # 格式化Prompt
        messages = format_inference_prompt(item['question'])

        # 调用API
        prediction = client.generate(messages)

        # 保存结果
        result = {
            'id': item.get('id', f'item_{i}'),
            'question': item['question'],
            'reference': item.get('answer', ''),
            'prediction': prediction,
            'spatial_type': item.get('spatial_relation_type', 'unknown'),
            'difficulty': item.get('difficulty', 'unknown')
        }
        results.append(result)

        # 进度显示 (非tqdm模式)
        if not HAS_TQDM and (i + 1) % 10 == 0:
            logger.info(f"进度: {i + 1}/{total} ({(i+1)/total*100:.1f}%)")

        # 保存checkpoint
        if checkpoint_path and (i + 1) % 50 == 0:
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                for r in results:
                    f.write(json.dumps(r, ensure_ascii=False) + '\n')
            logger.info(f"Checkpoint已保存: {i + 1} 条")

    # 保存最终结果
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for item in results:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    logger.info(f"推理结果已保存: {output_path}")
    return results


# ========================================
# 指标计算函数
# ========================================

def calculate_format_valid_rate_builtin(predictions: List[str]) -> float:
    """计算格式有效率 (内置简化版)"""
    if not predictions:
        return 0.0

    valid_count = 0
    for pred in predictions:
        if pred and not pred.startswith("[API_ERROR]"):
            # 检查是否包含有效答案
            if any(kw in pred for kw in ['方向', '公里', '千米', '米', '是的', '不是', '位于', '在']):
                valid_count += 1
    return valid_count / len(predictions)


def calculate_accuracy_builtin(predictions: List[str], references: List[str], spatial_types: List[str]) -> Dict:
    """计算准确率 (内置简化版关键词匹配)"""
    if not predictions or not references:
        return {'overall': 0, 'by_type': defaultdict(lambda: {'correct': 0, 'total': 0})}

    results = {
        'overall': 0,
        'by_type': defaultdict(lambda: {'correct': 0, 'total': 0})
    }

    correct_count = 0

    for pred, ref, stype in zip(predictions, references, spatial_types):
        # 提取中文关键词
        pred_words = set(re.findall(r'[\u4e00-\u9fff]+', pred))
        ref_words = set(re.findall(r'[\u4e00-\u9fff]+', ref))

        # 检查关键词重叠
        overlap = ref_words & pred_words
        is_correct = len(overlap) > 0

        if is_correct:
            correct_count += 1
            results['by_type'][stype]['correct'] += 1

        results['by_type'][stype]['total'] += 1

    results['overall'] = correct_count / len(predictions) if predictions else 0
    return results


def calculate_bleu_builtin(predictions: List[str], references: List[str]) -> float:
    """简化版BLEU计算 (字符级)"""
    if not predictions or not references:
        return 0.0

    scores = []
    for pred, ref in zip(predictions, references):
        pred_chars = list(pred)
        ref_chars = list(ref)

        if not pred_chars or not ref_chars:
            scores.append(0)
            continue

        # 计算精确率
        pred_counter = Counter(pred_chars)
        ref_counter = Counter(ref_chars)

        matches = sum(min(pred_counter[c], ref_counter[c]) for c in pred_counter)
        precision = matches / len(pred_chars) if pred_chars else 0

        # 简化的BP
        bp = min(1.0, len(pred_chars) / len(ref_chars)) if ref_chars else 0

        scores.append(bp * precision)

    return sum(scores) / len(scores) if scores else 0


def calculate_rouge_l_builtin(predictions: List[str], references: List[str]) -> float:
    """简化版ROUGE-L计算"""

    def lcs_length(s1: str, s2: str) -> int:
        """计算最长公共子序列长度"""
        m, n = len(s1), len(s2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i-1] == s2[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])

        return dp[m][n]

    if not predictions or not references:
        return 0.0

    scores = []
    for pred, ref in zip(predictions, references):
        if not pred or not ref:
            scores.append(0)
            continue

        lcs_len = lcs_length(pred, ref)
        precision = lcs_len / len(pred)
        recall = lcs_len / len(ref)

        if precision + recall > 0:
            f1 = 2 * precision * recall / (precision + recall)
        else:
            f1 = 0

        scores.append(f1)

    return sum(scores) / len(scores) if scores else 0


def calculate_spatial_f1_builtin(predictions: List[str], references: List[str]) -> float:
    """计算空间关键词F1 (内置版)"""
    if not predictions or not references:
        return 0.0

    SPATIAL_KEYWORDS = {
        '东', '西', '南', '北', '东北', '西北', '东南', '西南',
        '向东', '向西', '向南', '向北', '偏东', '偏西', '偏南', '偏北',
        '包含', '被包含', '位于', '在', '内', '外', '内部', '外部',
        '相邻', '接壤', '相离', '重叠', '交叉', '连接',
        '距离', '公里', '千米', '米', '远', '近', '相距', '间隔', '约'
    }

    scores = []
    for pred, ref in zip(predictions, references):
        pred_words = set(re.findall(r'[\u4e00-\u9fff]+', pred))
        ref_words = set(re.findall(r'[\u4e00-\u9fff]+', ref))

        pred_spatial = pred_words & SPATIAL_KEYWORDS
        ref_spatial = ref_words & SPATIAL_KEYWORDS

        if not pred_spatial and not ref_spatial:
            scores.append(1.0)
            continue

        if not pred_spatial or not ref_spatial:
            scores.append(0)
            continue

        overlap = pred_spatial & ref_spatial
        precision = len(overlap) / len(pred_spatial)
        recall = len(overlap) / len(ref_spatial)

        if precision + recall > 0:
            f1 = 2 * precision * recall / (precision + recall)
        else:
            f1 = 0

        scores.append(f1)

    return sum(scores) / len(scores) if scores else 0


def calculate_all_metrics(results: List[Dict]) -> Dict:
    """计算所有指标"""
    if not results:
        logger.warning("结果为空，返回空指标")
        return {
            "sample_count": 0,
            "timestamp": datetime.now().isoformat(),
            "deterministic": {
                "format_valid_rate": 0,
                "overall_accuracy": 0,
                "bleu_4": 0,
                "rouge_l": 0,
                "spatial_f1": 0
            },
            "by_spatial_type": {},
            "by_difficulty": {}
        }

    predictions = [r['prediction'] for r in results]
    references = [r['reference'] for r in results]
    spatial_types = [r['spatial_type'] for r in results]

    logger.info("计算确定性指标...")

    # 使用确定性指标模块或内置版本
    if HAS_DETERMINISTIC:
        try:
            format_valid_rate = calc_format_valid_rate(predictions)
            accuracy_result = calculate_overall_accuracy(predictions, references, spatial_types)
            bleu_4 = calculate_corpus_bleu_4(predictions, references)
            rouge_l = calculate_corpus_rouge_l(predictions, references)
            spatial_f1 = calculate_corpus_spatial_f1(predictions, references, spatial_types)
            overall_accuracy = accuracy_result if isinstance(accuracy_result, float) else accuracy_result
        except Exception as e:
            logger.warning(f"确定性指标计算失败，使用内置版本: {e}")
            format_valid_rate = calculate_format_valid_rate_builtin(predictions)
            accuracy_result = calculate_accuracy_builtin(predictions, references, spatial_types)
            bleu_4 = calculate_bleu_builtin(predictions, references)
            rouge_l = calculate_rouge_l_builtin(predictions, references)
            spatial_f1 = calculate_spatial_f1_builtin(predictions, references)
            overall_accuracy = accuracy_result['overall']
    else:
        format_valid_rate = calculate_format_valid_rate_builtin(predictions)
        accuracy_result = calculate_accuracy_builtin(predictions, references, spatial_types)
        bleu_4 = calculate_bleu_builtin(predictions, references)
        rouge_l = calculate_rouge_l_builtin(predictions, references)
        spatial_f1 = calculate_spatial_f1_builtin(predictions, references)
        overall_accuracy = accuracy_result['overall']

    metrics = {
        "sample_count": len(results),
        "timestamp": datetime.now().isoformat(),
        "deterministic": {
            "format_valid_rate": format_valid_rate,
            "overall_accuracy": overall_accuracy,
            "bleu_4": bleu_4,
            "rouge_l": rouge_l,
            "spatial_f1": spatial_f1
        },
        "by_spatial_type": {},
        "by_difficulty": {}
    }

    # 按空间类型分组
    type_groups = defaultdict(list)
    for r in results:
        type_groups[r['spatial_type']].append(r)

    for stype, items in type_groups.items():
        if not items:  # 空检查
            continue
        preds = [i['prediction'] for i in items]
        refs = [i['reference'] for i in items]
        types = [stype] * len(items)

        acc_result = calculate_accuracy_builtin(preds, refs, types)
        metrics["by_spatial_type"][stype] = {
            "count": len(items),
            "accuracy": acc_result['overall'],
            "format_valid_rate": calculate_format_valid_rate_builtin(preds)
        }

    # 按难度分组
    diff_groups = defaultdict(list)
    for r in results:
        diff_groups[r['difficulty']].append(r)

    for diff, items in diff_groups.items():
        if not items:  # 空检查
            continue
        preds = [i['prediction'] for i in items]
        refs = [i['reference'] for i in items]
        types = [i['spatial_type'] for i in items]

        acc_result = calculate_accuracy_builtin(preds, refs, types)
        metrics["by_difficulty"][diff] = {
            "count": len(items),
            "accuracy": acc_result['overall']
        }

    return metrics


def generate_report(metrics: Dict, dataset_name: str, output_path: Path):
    """生成评测报告"""
    report = f"""# GLM-4.7 地理空间推理评测报告

## 1. 评测概况
- 评测时间: {metrics['timestamp']}
- 评测模型: GLM-4.7
- 数据集: {dataset_name}
- 样本数量: {metrics['sample_count']}

## 2. 确定性指标

| 指标 | 分数 | 说明 |
|------|------|------|
| Format Valid Rate | {metrics['deterministic']['format_valid_rate']:.4f} | 格式有效率 |
| Overall Accuracy | {metrics['deterministic']['overall_accuracy']:.4f} | 整体准确率 |
| BLEU-4 | {metrics['deterministic']['bleu_4']:.4f} | 文本相似度(简化版) |
| ROUGE-L | {metrics['deterministic']['rouge_l']:.4f} | 最长公共子序列F1 |
| Spatial F1 | {metrics['deterministic']['spatial_f1']:.4f} | 空间关键词F1 |

## 3. 按空间类型分析

| 类型 | 数量 | 准确率 | 格式有效率 |
|------|------|--------|------------|
"""

    for stype, data in metrics['by_spatial_type'].items():
        report += f"| {stype} | {data['count']} | {data['accuracy']:.4f} | {data['format_valid_rate']:.4f} |\n"

    report += """
## 4. 按难度分析

| 难度 | 数量 | 准确率 |
|------|------|--------|
"""

    for diff, data in metrics['by_difficulty'].items():
        report += f"| {diff} | {data['count']} | {data['accuracy']:.4f} |\n"

    report += f"""
## 5. 指标有效性验证建议

基于以上结果，建议检查：

1. **区分度**: 各空间类型的准确率是否有显著差异？
2. **相关性**: Accuracy与BLEU/ROUGE的趋势是否一致？
3. **覆盖度**: Spatial F1是否能有效反映空间词汇的使用？

---

*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)

    logger.info(f"报告已生成: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="GLM-4.7评测脚本")
    parser.add_argument("--config", required=True, help="配置文件路径")
    parser.add_argument(
        "--dataset",
        choices=["split_coords", "splits", "both"],
        default="both",
        help="要评测的数据集"
    )
    parser.add_argument("--sample_size", type=int, default=None, help="采样数量(测试用)")
    parser.add_argument("--skip_inference", action="store_true", help="跳过推理，直接计算指标")
    args = parser.parse_args()

    # 加载配置
    with open(args.config, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    logger.info("="*60)
    logger.info("GLM-4.7 测试集评测")
    logger.info("="*60)
    logger.info(f"配置文件: {args.config}")
    logger.info(f"数据集: {args.dataset}")
    logger.info(f"采样数量: {args.sample_size or '全量'}")
    logger.info(f"确定性指标模块: {'可用' if HAS_DETERMINISTIC else '不可用，使用内置版本'}")
    logger.info(f"tqdm进度条: {'可用' if HAS_TQDM else '不可用'}")

    # 初始化客户端
    client = GLM47Client(config)

    # 创建输出目录
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path(config['paths']['output_dir']) / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存配置
    with open(output_dir / 'config.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True)

    # 确定要评测的数据集
    datasets = []
    if args.dataset in ["split_coords", "both"]:
        datasets.append(("split_coords", config['paths']['split_coords_test']))
    if args.dataset in ["splits", "both"]:
        datasets.append(("splits", config['paths']['splits_test']))

    # 对每个数据集执行评测
    for name, path in datasets:
        logger.info(f"\n{'#'*60}")
        logger.info(f"# 评测数据集: {name}")
        logger.info(f"{'#'*60}")

        # Phase 1: 加载数据
        data = load_test_data(path, args.sample_size)

        # Phase 2: 推理
        if not args.skip_inference:
            checkpoint_path = Path(config['paths']['checkpoint_dir']) / f"{name}_checkpoint.jsonl"
            predictions_path = output_dir / f"predictions_{name}.jsonl"
            results = run_inference(client, data, predictions_path, checkpoint_path)
        else:
            predictions_path = output_dir / f"predictions_{name}.jsonl"
            logger.info(f"跳过推理，加载已有结果: {predictions_path}")
            results = []
            with open(predictions_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        results.append(json.loads(line))

        # Phase 3: 计算指标
        metrics = calculate_all_metrics(results)

        # 保存指标
        metrics_path = output_dir / f"metrics_{name}.json"
        with open(metrics_path, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        logger.info(f"指标已保存: {metrics_path}")

        # Phase 4: 生成报告
        report_path = output_dir / f"report_{name}.md"
        generate_report(metrics, name, report_path)

        # 打印摘要
        logger.info(f"\n--- {name} 评测结果 ---")
        logger.info(f"Format Valid Rate: {metrics['deterministic']['format_valid_rate']:.4f}")
        logger.info(f"Overall Accuracy: {metrics['deterministic']['overall_accuracy']:.4f}")
        logger.info(f"BLEU-4: {metrics['deterministic']['bleu_4']:.4f}")
        logger.info(f"ROUGE-L: {metrics['deterministic']['rouge_l']:.4f}")
        logger.info(f"Spatial F1: {metrics['deterministic']['spatial_f1']:.4f}")

    # 打印API统计
    logger.info(f"\n{'='*60}")
    logger.info("API调用统计")
    logger.info(f"{'='*60}")
    stats = client.get_stats()
    for k, v in stats.items():
        logger.info(f"{k}: {v}")

    logger.info(f"\n评测完成! 结果目录: {output_dir}")


if __name__ == "__main__":
    main()
