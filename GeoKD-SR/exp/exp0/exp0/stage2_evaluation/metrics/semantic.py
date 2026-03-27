"""
语义评测指标（BERTScore）
使用 bert-base-chinese 模型计算语义相似度
"""
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class SemanticMetrics:
    """语义评测指标计算器（BERTScore）"""

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化

        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.model_type = self.config.get('model_type', 'bert-base-chinese')
        self.lang = self.config.get('lang', 'zh')
        self.rescale_with_baseline = self.config.get('rescale_with_baseline', True)

        # 延迟加载bert_score
        self._bert_score = None

    def _load_bert_score(self):
        """延迟加载bert_score库"""
        if self._bert_score is None:
            try:
                import bert_score
                self._bert_score = bert_score
                logger.info(f"bert_score 加载成功，使用模型: {self.model_type}")
            except ImportError:
                logger.warning("bert_score 未安装，请运行: pip install bert-score")
                raise ImportError("bert_score 未安装")

    def compute_all(self, predictions: List[Dict]) -> Dict[str, float]:
        """
        计算所有语义指标

        Args:
            predictions: 预测结果列表

        Returns:
            语义指标结果
        """
        self._load_bert_score()

        references = [p.get('reference', '') for p in predictions]
        predictions_text = [p.get('prediction', '') for p in predictions]

        # 过滤空值
        valid_pairs = [(r, p) for r, p in zip(references, predictions_text) if r and p]

        if not valid_pairs:
            return {
                'bertscore_precision': 0.0,
                'bertscore_recall': 0.0,
                'bertscore_f1': 0.0
            }

        refs, preds = zip(*valid_pairs)

        try:
            # 计算BERTScore
            P, R, F1 = self._bert_score.score(
                cands=list(preds),
                refs=list(refs),
                model_type=self.model_type,
                lang=self.lang,
                rescale_with_baseline=self.rescale_with_baseline,
                verbose=False
            )

            return {
                'bertscore_precision': float(P.mean()),
                'bertscore_recall': float(R.mean()),
                'bertscore_f1': float(F1.mean())
            }

        except Exception as e:
            logger.error(f"计算BERTScore时出错: {e}")
            return {
                'bertscore_precision': 0.0,
                'bertscore_recall': 0.0,
                'bertscore_f1': 0.0
            }

    def compute_individual_scores(self, predictions: List[Dict]) -> List[Dict[str, float]]:
        """
        计算每条预测的BERTScore

        Args:
            predictions: 预测结果列表

        Returns:
            每条预测的分数列表
        """
        self._load_bert_score()

        results = []

        for pred in predictions:
            reference = pred.get('reference', '')
            prediction = pred.get('prediction', '')

            if not reference or not prediction:
                results.append({
                    'precision': 0.0,
                    'recall': 0.0,
                    'f1': 0.0
                })
                continue

            try:
                P, R, F1 = self._bert_score.score(
                    cands=[prediction],
                    refs=[reference],
                    model_type=self.model_type,
                    lang=self.lang,
                    rescale_with_baseline=self.rescale_with_baseline,
                    verbose=False
                )

                results.append({
                    'precision': float(P[0]),
                    'recall': float(R[0]),
                    'f1': float(F1[0])
                })

            except Exception as e:
                logger.warning(f"计算单条BERTScore时出错: {e}")
                results.append({
                    'precision': 0.0,
                    'recall': 0.0,
                    'f1': 0.0
                })

        return results

    def compute_by_type(self, predictions: List[Dict]) -> Dict[str, Dict[str, float]]:
        """
        按空间类型分层计算语义指标

        Args:
            predictions: 预测结果列表

        Returns:
            分层语义指标结果
        """
        type_groups = {}

        for pred in predictions:
            spatial_type = pred.get('spatial_type', 'unknown')
            if spatial_type not in type_groups:
                type_groups[spatial_type] = []
            type_groups[spatial_type].append(pred)

        results = {}
        for stype, preds in type_groups.items():
            if preds:
                results[stype] = self.compute_all(preds)

        return results

    def compute_by_difficulty(self, predictions: List[Dict]) -> Dict[str, Dict[str, float]]:
        """
        按难度分层计算语义指标

        Args:
            predictions: 预测结果列表

        Returns:
            分层语义指标结果
        """
        diff_groups = {}

        for pred in predictions:
            difficulty = pred.get('difficulty', 'unknown')
            if difficulty not in diff_groups:
                diff_groups[difficulty] = []
            diff_groups[difficulty].append(pred)

        results = {}
        for diff, preds in diff_groups.items():
            if preds:
                results[diff] = self.compute_all(preds)

        return results


def compute_semantic_metrics(
    predictions: List[Dict],
    model_type: str = "bert-base-chinese"
) -> Dict[str, float]:
    """
    便捷函数：计算语义指标

    Args:
        predictions: 预测结果列表
        model_type: BERT模型类型

    Returns:
        语义指标结果
    """
    config = {
        'model_type': model_type,
        'lang': 'zh',
        'rescale_with_baseline': True
    }
    metrics = SemanticMetrics(config)
    return metrics.compute_all(predictions)


if __name__ == "__main__":
    # 测试
    test_predictions = [
        {
            "reference": "东南方向",
            "prediction": "东南"
        },
        {
            "reference": "约1200公里",
            "prediction": "大约1200公里"
        }
    ]

    results = compute_semantic_metrics(test_predictions)
    print(f"BERTScore结果: {results}")
