r"""
确定性指标模块

实现6个确定性指标：
1. Overall Accuracy - 整体准确率
2. Format Valid Rate - 格式有效率
3. BLEU-4 - 文本相似度
4. ROUGE-L - 最长公共子序列
5. Perplexity - 困惑度
6. Spatial F1 - 空间关键词F1

参考文档: D:\30_keyan\docs\GeoKD-SR-9实验统一评测指标设计方案_20260313.md
"""

import re
import json
import math
import torch
from collections import Counter
from typing import Tuple, List, Optional


# ==================== 关键词定义 ====================

# 方向关键词定义（8方位 + 同义词映射）
DIRECTION_KEYWORDS = {
    "东": ["东", "东方", "东边", "东侧"],
    "西": ["西", "西方", "西边", "西侧"],
    "南": ["南", "南方", "南边", "南侧"],
    "北": ["北", "北方", "北边", "北侧"],
    "东北": ["东北", "东北方", "东北方向"],
    "西北": ["西北", "西北方", "西北方向"],
    "东南": ["东南", "东南方", "东南方向"],
    "西南": ["西南", "西南方", "西南方向"]
}

# 拓扑关键词定义
TOPOLOGY_KEYWORDS = {
    "within": ["在...内部", "位于...内", "在...里面", "属于", "包含于"],
    "contains": ["包含", "内部有", "有...在", "涵盖"],
    "adjacent": ["相邻", "毗邻", "接壤", "邻近"],
    "disjoint": ["不相交", "分离", "相离", "没有重叠"],
    "overlap": ["重叠", "部分重叠", "交叉"]
}

# 空间关键词词表
SPATIAL_KEYWORDS = {
    "directional": [
        "东", "西", "南", "北",
        "东北", "西北", "东南", "西南",
        "东方", "西方", "南方", "北方",
        "向东", "向西", "向南", "向北"
    ],
    "topological": [
        "包含", "被包含", "位于", "在...内",
        "内部", "外部", "相邻", "接壤",
        "相离", "重叠", "交叉", "毗邻",
        "属于", "涵盖"
    ],
    "metric": [
        "距离", "公里", "千米", "米",
        "远", "近", "相距", "间隔",
        "半径", "范围", "约"
    ]
}


# ==================== 方向相关函数 ====================

def normalize_direction(text: str) -> str:
    """将方向描述归一化为8方位之一"""
    for standard, variants in DIRECTION_KEYWORDS.items():
        for v in variants:
            if v in text:
                return standard
    return ""


def match_direction(prediction: str, reference: str) -> int:
    """
    方向匹配：比较预测与参考答案的方向是否一致

    返回：1表示正确，0表示错误
    """
    pred_dir = normalize_direction(prediction)
    ref_dir = normalize_direction(reference)

    if not pred_dir or not ref_dir:
        return 0

    return 1 if pred_dir == ref_dir else 0


# ==================== 拓扑相关函数 ====================

def match_topology(prediction: str, reference: str) -> int:
    """
    拓扑匹配：比较预测与参考答案的拓扑关系是否一致

    返回：1表示正确，0表示错误
    """
    pred_type = None
    ref_type = None

    for topo_type, keywords in TOPOLOGY_KEYWORDS.items():
        for kw in keywords:
            if kw in prediction and pred_type is None:
                pred_type = topo_type
            if kw in reference and ref_type is None:
                ref_type = topo_type

    if pred_type is None or ref_type is None:
        return 0

    return 1 if pred_type == ref_type else 0


# ==================== 距离相关函数 ====================

def extract_distance(text: str) -> Tuple[Optional[float], Optional[str]]:
    """
    从文本中提取距离数值和单位

    返回：(数值, 单位) 或 (None, None)
    """
    # 匹配 "XX公里/千米/米" 模式
    patterns = [
        r'(\d+(?:\.\d+)?)\s*公里',
        r'(\d+(?:\.\d+)?)\s*千米',
        r'(\d+(?:\.\d+)?)\s*km',
        r'(\d+(?:\.\d+)?)\s*米',
        r'(\d+(?:\.\d+)?)\s*m\b'
    ]

    for i, pattern in enumerate(patterns):
        match = re.search(pattern, text)
        if match:
            value = float(match.group(1))
            unit = 'km' if i < 3 else 'm'
            return value, unit

    return None, None


def match_distance(prediction: str, reference: str) -> int:
    """
    距离匹配：比较预测与参考答案的距离是否在容差范围内

    容差规则：±10% 或 ±50km（取较大值）

    返回：1表示正确，0表示错误
    """
    pred_val, pred_unit = extract_distance(prediction)
    ref_val, ref_unit = extract_distance(reference)

    if pred_val is None or ref_val is None:
        return 0

    # 统一转换为公里
    if pred_unit == 'm':
        pred_val = pred_val / 1000
    if ref_unit == 'm':
        ref_val = ref_val / 1000

    # 计算容差
    tolerance = max(ref_val * 0.1, 50)  # ±10% 或 ±50km

    return 1 if abs(pred_val - ref_val) <= tolerance else 0


# ==================== 组合匹配函数 ====================

def match_composite(prediction: str, reference: str) -> int:
    """
    组合匹配：方向和距离都正确才算正确

    返回：1表示正确，0表示错误
    """
    dir_ok = match_direction(prediction, reference)
    dist_ok = match_distance(prediction, reference)
    return 1 if (dir_ok and dist_ok) else 0


# ==================== Overall Accuracy ====================

def calculate_overall_accuracy(predictions: List[str],
                               references: List[str],
                               spatial_types: List[str]) -> float:
    """
    计算整体准确率

    参数：
        predictions: 模型输出列表
        references: 标准答案列表
        spatial_types: 空间关系类型列表

    返回：准确率 (0.0 - 1.0)
    """
    correct = 0
    total = len(predictions)

    for pred, ref, stype in zip(predictions, references, spatial_types):
        if stype == "directional":
            correct += match_direction(pred, ref)
        elif stype == "topological":
            correct += match_topology(pred, ref)
        elif stype == "metric":
            correct += match_distance(pred, ref)
        elif stype == "composite":
            correct += match_composite(pred, ref)

    return correct / total if total > 0 else 0.0


# ==================== Format Valid Rate ====================

def extract_json_block(text: str) -> Optional[dict]:
    """
    从文本中提取JSON块

    支持格式：
    1. ```json ... ```
    2. {...} 直接JSON对象
    """
    # 尝试提取 ```json ... ``` 格式
    json_match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试提取直接JSON对象
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def has_answer_keywords(text: str) -> bool:
    """
    检查文本是否包含明确答案关键词

    用于处理非JSON格式的输出
    """
    # 方向关键词
    direction_patterns = ["东", "西", "南", "北", "东北", "西北", "东南", "西南"]

    # 拓扑关键词
    topology_patterns = ["包含", "位于", "相邻", "相离", "重叠", "内部", "外部"]

    # 距离关键词
    distance_patterns = ["公里", "千米", "米", "距离"]

    # 肯定/否定词
    answer_patterns = ["是", "否", "对", "错", "正确", "错误"]

    all_patterns = (direction_patterns + topology_patterns +
                   distance_patterns + answer_patterns)

    return any(kw in text for kw in all_patterns)


def calculate_format_valid_rate(predictions: List[str]) -> float:
    """
    计算格式有效率

    判定标准：
    1. JSON可解析
    2. 或包含明确答案关键词

    参数：
        predictions: 模型输出列表

    返回：格式有效率 (0.0 - 1.0)
    """
    valid = 0
    total = len(predictions)

    for pred in predictions:
        # 检查JSON可解析
        if extract_json_block(pred) is not None:
            valid += 1
        # 或包含明确答案关键词
        elif has_answer_keywords(pred):
            valid += 1

    return valid / total if total > 0 else 0.0


# ==================== BLEU-4 ====================

def get_ngrams(text: str, n: int) -> List[Tuple]:
    """
    获取文本的n-gram列表（字符级，适用于中文）
    """
    chars = list(text)
    return [tuple(chars[i:i+n]) for i in range(len(chars)-n+1)]


def calculate_bleu_n(prediction: str, reference: str, n: int) -> float:
    """
    计算单个n-gram的精确率
    """
    if len(prediction) < n or len(reference) < n:
        return 0.0

    pred_ngrams = get_ngrams(prediction, n)
    ref_ngrams = get_ngrams(reference, n)

    if not pred_ngrams:
        return 0.0

    pred_counter = Counter(pred_ngrams)
    ref_counter = Counter(ref_ngrams)

    # 计算clipped counts
    clipped_counts = 0
    for ngram, count in pred_counter.items():
        clipped_counts += min(count, ref_counter.get(ngram, 0))

    return clipped_counts / len(pred_ngrams)


def calculate_bleu_4(prediction: str, reference: str) -> float:
    """
    计算BLEU-4分数

    公式：BLEU = BP * exp(sum(w_n * log(p_n)))

    其中：
    - BP (Brevity Penalty) = exp(1 - r/c) if c < r else 1
    - p_n = n-gram精确率
    - w_n = 1/4 (权重均等)

    参数：
        prediction: 模型输出
        reference: 标准答案

    返回：BLEU-4分数 (0.0 - 1.0)
    """
    # 检查边界条件
    if not prediction or not reference:
        return 0.0

    # 计算各阶n-gram精确率
    precisions = []
    for n in range(1, 5):
        p = calculate_bleu_n(prediction, reference, n)
        if p == 0:
            # 如果某阶精确率为0，使用平滑
            p = 1e-10
        precisions.append(p)

    # 计算几何平均
    log_precision_sum = sum(math.log(p) for p in precisions)
    geo_mean = math.exp(log_precision_sum / 4)

    # 计算Brevity Penalty
    pred_len = len(prediction)
    ref_len = len(reference)

    if pred_len < ref_len:
        bp = math.exp(1 - ref_len / pred_len)
    else:
        bp = 1.0

    return bp * geo_mean


def calculate_corpus_bleu_4(predictions: List[str], references: List[str]) -> float:
    """
    计算语料级别的BLEU-4分数（平均值）
    """
    scores = [calculate_bleu_4(p, r) for p, r in zip(predictions, references)]
    return sum(scores) / len(scores) if scores else 0.0


# ==================== ROUGE-L ====================

def calculate_lcs_length(text1: str, text2: str) -> int:
    """
    计算两个字符串的最长公共子序列长度

    使用动态规划算法
    """
    chars1 = list(text1)
    chars2 = list(text2)

    m, n = len(chars1), len(chars2)

    if m == 0 or n == 0:
        return 0

    # DP表
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if chars1[i-1] == chars2[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])

    return dp[m][n]


def calculate_rouge_l(prediction: str, reference: str) -> float:
    """
    计算ROUGE-L F1分数

    公式：F1 = 2 * P * R / (P + R)

    其中：
    - P (Precision) = LCS长度 / 预测文本长度
    - R (Recall) = LCS长度 / 参考文本长度

    参数：
        prediction: 模型输出
        reference: 标准答案

    返回：ROUGE-L F1分数 (0.0 - 1.0)
    """
    if not prediction or not reference:
        return 0.0

    lcs_len = calculate_lcs_length(prediction, reference)

    precision = lcs_len / len(prediction) if prediction else 0
    recall = lcs_len / len(reference) if reference else 0

    if precision + recall == 0:
        return 0.0

    return 2 * precision * recall / (precision + recall)


def calculate_corpus_rouge_l(predictions: List[str], references: List[str]) -> float:
    """
    计算语料级别的ROUGE-L分数（平均值）
    """
    scores = [calculate_rouge_l(p, r) for p, r in zip(predictions, references)]
    return sum(scores) / len(scores) if scores else 0.0


# ==================== Perplexity ====================

def calculate_perplexity(model, tokenizer, texts: List[str],
                         device: str = "cuda") -> float:
    """
    计算模型在给定文本上的困惑度

    公式：PPL = exp(总交叉熵损失 / 总token数)

    参数：
        model: 语言模型
        tokenizer: 分词器
        texts: 文本列表
        device: 计算设备

    返回：困惑度（越小越好）
    """
    model.eval()
    model.to(device)

    total_loss = 0.0
    total_tokens = 0

    with torch.no_grad():
        for text in texts:
            # 编码文本
            encodings = tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=2048
            )
            input_ids = encodings["input_ids"].to(device)

            # 计算损失（使用labels自动计算交叉熵）
            outputs = model(input_ids, labels=input_ids)
            loss = outputs.loss.item()

            # 累加损失（按token数加权）
            num_tokens = input_ids.size(1)
            total_loss += loss * num_tokens
            total_tokens += num_tokens

    # 计算平均损失并转换为困惑度
    avg_loss = total_loss / total_tokens if total_tokens > 0 else float('inf')
    perplexity = math.exp(avg_loss)

    return perplexity


def calculate_perplexity_by_batch(model, tokenizer, texts: List[str],
                                   batch_size: int = 8,
                                   device: str = "cuda") -> float:
    """
    批量计算困惑度（更高效的实现）
    """
    model.eval()
    model.to(device)

    total_loss = 0.0
    total_tokens = 0

    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]

            # 编码批处理
            encodings = tokenizer(
                batch_texts,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=2048
            )

            input_ids = encodings["input_ids"].to(device)
            attention_mask = encodings["attention_mask"].to(device)

            # 计算损失
            outputs = model(input_ids, attention_mask=attention_mask, labels=input_ids)
            loss = outputs.loss.item()

            # 计算有效token数（排除padding）
            valid_tokens = attention_mask.sum().item()
            total_loss += loss * valid_tokens
            total_tokens += valid_tokens

    avg_loss = total_loss / total_tokens if total_tokens > 0 else float('inf')
    return math.exp(avg_loss)


# ==================== Spatial F1 ====================

def extract_spatial_keywords(text: str, spatial_type: str) -> set:
    """
    从文本中提取空间关键词

    参数：
        text: 输入文本
        spatial_type: 空间关系类型

    返回：关键词集合
    """
    keywords = SPATIAL_KEYWORDS.get(spatial_type, [])
    return {kw for kw in keywords if kw in text}


def calculate_spatial_f1(prediction: str, reference: str,
                         spatial_type: str) -> float:
    """
    计算空间关键词F1分数

    公式：F1 = 2 * P * R / (P + R)

    其中：
    - P (Precision) = 共有关键词数 / 预测关键词数
    - R (Recall) = 共有关键词数 / 参考关键词数

    参数：
        prediction: 模型输出
        reference: 标准答案
        spatial_type: 空间关系类型

    返回：Spatial F1分数 (0.0 - 1.0)
    """
    pred_keywords = extract_spatial_keywords(prediction, spatial_type)
    ref_keywords = extract_spatial_keywords(reference, spatial_type)

    # 如果参考答案没有关键词，返回1.0（无法评估）
    if not ref_keywords:
        return 1.0

    # 计算交集
    common = pred_keywords & ref_keywords

    # 计算精确率和召回率
    precision = len(common) / len(pred_keywords) if pred_keywords else 0
    recall = len(common) / len(ref_keywords)

    # 计算F1
    if precision + recall == 0:
        return 0.0

    return 2 * precision * recall / (precision + recall)


def calculate_corpus_spatial_f1(predictions: List[str], references: List[str],
                                 spatial_types: List[str]) -> float:
    """
    计算语料级别的Spatial F1分数（平均值）
    """
    scores = [
        calculate_spatial_f1(p, r, s)
        for p, r, s in zip(predictions, references, spatial_types)
    ]
    return sum(scores) / len(scores) if scores else 0.0
