r"""
GeoKD-SR 评测指标模块

本模块实现了确定性指标和语义指标，用于评测地理空间推理模型的性能：

【确定性指标】
1. Overall Accuracy - 整体准确率
2. Format Valid Rate - 格式有效率
3. BLEU-4 - 文本相似度
4. ROUGE-L - 最长公共子序列
5. Perplexity - 困惑度
6. Spatial F1 - 空间关键词F1

【语义指标】
1. BERTScore - 语义相似度（Precision/Recall/F1）
   - 基于预训练中文BERT模型
   - 能够捕捉同义词、近义词的语义匹配
   - 支持IDF加权，提升专有名词权重

参考文档: D:\30_keyan\docs\GeoKD-SR-9实验统一评测指标设计方案_20260313.md
"""

from .deterministic import (
    # 关键词定义
    DIRECTION_KEYWORDS,
    TOPOLOGY_KEYWORDS,
    SPATIAL_KEYWORDS,

    # 方向相关函数
    normalize_direction,
    match_direction,

    # 拓扑相关函数
    match_topology,

    # 距离相关函数
    extract_distance,
    match_distance,

    # 组合匹配函数
    match_composite,

    # Overall Accuracy
    calculate_overall_accuracy,

    # Format Valid Rate
    extract_json_block,
    has_answer_keywords,
    calculate_format_valid_rate,

    # BLEU-4
    get_ngrams,
    calculate_bleu_4,
    calculate_corpus_bleu_4,

    # ROUGE-L
    calculate_lcs_length,
    calculate_rouge_l,
    calculate_corpus_rouge_l,

    # Perplexity
    calculate_perplexity,
    calculate_perplexity_by_batch,

    # Spatial F1
    extract_spatial_keywords,
    calculate_spatial_f1,
    calculate_corpus_spatial_f1,
)

from .semantic import (
    # BERTScore计算器类
    BERTScoreCalculator,

    # 便捷函数
    calculate_bertscore_with_idf,
    calculate_single_bertscore,
    calculate_corpus_bertscore,
)

__all__ = [
    # ============ 确定性指标导出 ============

    # 关键词定义
    "DIRECTION_KEYWORDS",
    "TOPOLOGY_KEYWORDS",
    "SPATIAL_KEYWORDS",

    # 方向相关函数
    "normalize_direction",
    "match_direction",

    # 拓扑相关函数
    "match_topology",

    # 距离相关函数
    "extract_distance",
    "match_distance",

    # 组合匹配函数
    "match_composite",

    # Overall Accuracy
    "calculate_overall_accuracy",

    # Format Valid Rate
    "extract_json_block",
    "has_answer_keywords",
    "calculate_format_valid_rate",

    # BLEU-4
    "get_ngrams",
    "calculate_bleu_4",
    "calculate_corpus_bleu_4",

    # ROUGE-L
    "calculate_lcs_length",
    "calculate_rouge_l",
    "calculate_corpus_rouge_l",

    # Perplexity
    "calculate_perplexity",
    "calculate_perplexity_by_batch",

    # Spatial F1
    "extract_spatial_keywords",
    "calculate_spatial_f1",
    "calculate_corpus_spatial_f1",

    # ============ 语义指标导出 ============

    # BERTScore计算器类
    "BERTScoreCalculator",

    # 便捷函数
    "calculate_bertscore_with_idf",
    "calculate_single_bertscore",
    "calculate_corpus_bertscore",
]
