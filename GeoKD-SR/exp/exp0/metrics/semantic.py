"""
语义指标模块 - BERTScore计算

使用预训练的中文BERT模型计算语义相似度。
"""

import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer
from typing import List, Dict, Tuple
import numpy as np
from collections import Counter


class BERTScoreCalculator:
    """
    BERTScore计算器

    使用预训练的中文BERT模型计算语义相似度。

    特点：
    - 语义感知：能够识别同义词、近义词
    - 上下文相关：基于BERT上下文嵌入
    - 鲁棒性：对文本长度变化和表述差异具有较好的鲁棒性
    - 中文支持：使用 bert-base-chinese 模型
    """

    def __init__(self, model_name: str = "bert-base-chinese", device: str = "cuda"):
        """
        初始化BERT模型

        参数：
            model_name: 预训练模型名称（默认：bert-base-chinese）
            device: 计算设备（"cuda" 或 "cpu"）
        """
        self.device = device
        self.model_name = model_name

        # 自动检测设备是否可用
        if device == "cuda" and not torch.cuda.is_available():
            self.device = "cpu"

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()

    def get_embeddings(self, text: str) -> torch.Tensor:
        """
        获取文本的BERT嵌入向量

        使用最后一层隐藏状态作为嵌入表示。

        参数：
            text: 输入文本

        返回：
            嵌入张量 [seq_len, hidden_dim]
        """
        with torch.no_grad():
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            outputs = self.model(**inputs)
            # 使用最后一层隐藏状态 [batch, seq_len, hidden_dim]
            embeddings = outputs.last_hidden_state

        return embeddings.squeeze(0)  # [seq_len, hidden_dim]

    def cosine_similarity_matrix(self, emb1: torch.Tensor, emb2: torch.Tensor) -> torch.Tensor:
        """
        计算两组嵌入之间的余弦相似度矩阵

        参数：
            emb1: [seq_len1, hidden_dim] 预测文本嵌入
            emb2: [seq_len2, hidden_dim] 参考文本嵌入

        返回：
            相似度矩阵 [seq_len1, seq_len2]
        """
        # L2归一化
        emb1_norm = F.normalize(emb1, dim=-1)
        emb2_norm = F.normalize(emb2, dim=-1)

        # 计算余弦相似度矩阵
        sim_matrix = torch.mm(emb1_norm, emb2_norm.t())

        return sim_matrix

    def calculate_bertscore(self, prediction: str, reference: str) -> Dict[str, float]:
        """
        计算单对文本的BERTScore

        公式：
        - Precision = (1/|pred|) * sum(max_sim(pred_i, ref))
        - Recall = (1/|ref|) * sum(max_sim(ref_j, pred))
        - F1 = 2 * P * R / (P + R)

        参数：
            prediction: 模型输出文本
            reference: 参考答案文本

        返回：
            {"precision": float, "recall": float, "f1": float}
        """
        if not prediction or not reference:
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

        # 获取嵌入
        pred_emb = self.get_embeddings(prediction)
        ref_emb = self.get_embeddings(reference)

        # 计算相似度矩阵
        sim_matrix = self.cosine_similarity_matrix(pred_emb, ref_emb)

        # 计算Precision: 对每个预测token，找最相似的参考token
        max_sim_for_pred = sim_matrix.max(dim=1).values
        precision = max_sim_for_pred.mean().item()

        # 计算Recall: 对每个参考token，找最相似的预测token
        max_sim_for_ref = sim_matrix.max(dim=0).values
        recall = max_sim_for_ref.mean().item()

        # 计算F1
        if precision + recall > 0:
            f1 = 2 * precision * recall / (precision + recall)
        else:
            f1 = 0.0

        return {
            "precision": precision,
            "recall": recall,
            "f1": f1
        }

    def calculate_corpus_bertscore(self, predictions: List[str],
                                    references: List[str]) -> Dict[str, float]:
        """
        计算语料级别的BERTScore（平均值）

        参数：
            predictions: 模型输出列表
            references: 参考答案列表

        返回：
            {
                "precision": float, "recall": float, "f1": float,
                "precision_std": float, "recall_std": float, "f1_std": float
            }
        """
        if len(predictions) != len(references):
            raise ValueError("predictions和references的长度必须相同")

        all_precision = []
        all_recall = []
        all_f1 = []

        for pred, ref in zip(predictions, references):
            scores = self.calculate_bertscore(pred, ref)
            all_precision.append(scores["precision"])
            all_recall.append(scores["recall"])
            all_f1.append(scores["f1"])

        return {
            "precision": float(np.mean(all_precision)),
            "recall": float(np.mean(all_recall)),
            "f1": float(np.mean(all_f1)),
            "precision_std": float(np.std(all_precision)),
            "recall_std": float(np.std(all_recall)),
            "f1_std": float(np.std(all_f1))
        }

    def calculate_bertscore_with_idf(self, predictions: List[str],
                                     references: List[str]) -> Dict[str, float]:
        """
        带IDF加权的BERTScore计算

        IDF权重可以降低常见词的影响，提升稀有词的重要性。
        对于地理空间问答，这能让专有名词（如地名）获得更高权重。

        参数：
            predictions: 模型输出列表
            references: 参考答案列表

        返回：
            {"precision": float, "recall": float, "f1": float}
        """
        if len(predictions) != len(references):
            raise ValueError("predictions和references的长度必须相同")

        # 计算IDF权重（基于所有参考答案）
        all_tokens = []
        for ref in references:
            tokens = self.tokenizer.tokenize(ref)
            all_tokens.extend(tokens)

        token_counts = Counter(all_tokens)
        total_docs = len(references)

        # IDF权重字典: log(N / (df + 1))
        idf_weights = {
            token: np.log(total_docs / (count + 1))
            for token, count in token_counts.items()
        }

        # 计算加权分数
        weighted_precision_sum = 0.0
        weighted_recall_sum = 0.0
        total_weight = 0.0

        for pred, ref in zip(predictions, references):
            pred_emb = self.get_embeddings(pred)
            ref_emb = self.get_embeddings(ref)

            sim_matrix = self.cosine_similarity_matrix(pred_emb, ref_emb)

            # 获取token对应的IDF权重
            pred_tokens = self.tokenizer.tokenize(pred)
            ref_tokens = self.tokenizer.tokenize(ref)

            pred_weights = [idf_weights.get(t, 0.0) for t in pred_tokens]
            ref_weights = [idf_weights.get(t, 0.0) for t in ref_tokens]

            # 加权precision
            max_sim_for_pred = sim_matrix.max(dim=1).values
            if len(pred_weights) > 0 and sim_matrix.size(0) > 0:
                # 确保维度匹配
                actual_len = min(len(pred_weights), sim_matrix.size(0))
                weighted_pred_sim = sum(
                    max_sim_for_pred[i].item() * pred_weights[i]
                    for i in range(actual_len)
                )
                total_pred_weight = sum(pred_weights[:actual_len])
                if total_pred_weight > 0:
                    weighted_precision_sum += weighted_pred_sim / total_pred_weight

            # 加权recall
            max_sim_for_ref = sim_matrix.max(dim=0).values
            if len(ref_weights) > 0 and sim_matrix.size(1) > 0:
                actual_len = min(len(ref_weights), sim_matrix.size(1))
                weighted_ref_sim = sum(
                    max_sim_for_ref[i].item() * ref_weights[i]
                    for i in range(actual_len)
                )
                total_ref_weight = sum(ref_weights[:actual_len])
                if total_ref_weight > 0:
                    weighted_recall_sum += weighted_ref_sim / total_ref_weight

            total_weight += 1.0

        # 计算平均值
        avg_precision = weighted_precision_sum / total_weight if total_weight > 0 else 0.0
        avg_recall = weighted_recall_sum / total_weight if total_weight > 0 else 0.0

        # 计算F1
        if avg_precision + avg_recall > 0:
            f1 = 2 * avg_precision * avg_recall / (avg_precision + avg_recall)
        else:
            f1 = 0.0

        return {
            "precision": avg_precision,
            "recall": avg_recall,
            "f1": f1
        }


def calculate_bertscore_with_idf(predictions: List[str],
                                  references: List[str],
                                  model_name: str = "bert-base-chinese",
                                  device: str = "cuda") -> Dict[str, float]:
    """
    带IDF加权的BERTScore计算（独立函数）

    这是一个便捷函数，内部创建BERTScoreCalculator实例并计算加权分数。

    参数：
        predictions: 模型输出列表
        references: 参考答案列表
        model_name: 预训练模型名称（默认：bert-base-chinese）
        device: 计算设备（"cuda" 或 "cpu"）

    返回：
        {"precision": float, "recall": float, "f1": float}
    """
    calculator = BERTScoreCalculator(model_name, device)
    return calculator.calculate_bertscore_with_idf(predictions, references)


def calculate_single_bertscore(prediction: str,
                               reference: str,
                               model_name: str = "bert-base-chinese",
                               device: str = "cuda") -> Dict[str, float]:
    """
    计算单对文本的BERTScore（独立函数）

    这是一个便捷函数，用于计算单对文本的BERTScore。

    参数：
        prediction: 模型输出文本
        reference: 参考答案文本
        model_name: 预训练模型名称（默认：bert-base-chinese）
        device: 计算设备（"cuda" 或 "cpu"）

    返回：
        {"precision": float, "recall": float, "f1": float}
    """
    calculator = BERTScoreCalculator(model_name, device)
    return calculator.calculate_bertscore(prediction, reference)


def calculate_corpus_bertscore(predictions: List[str],
                               references: List[str],
                               model_name: str = "bert-base-chinese",
                               device: str = "cuda") -> Dict[str, float]:
    """
    计算语料级别的BERTScore（独立函数）

    这是一个便捷函数，用于计算语料级别的BERTScore。

    参数：
        predictions: 模型输出列表
        references: 参考答案列表
        model_name: 预训练模型名称（默认：bert-base-chinese）
        device: 计算设备（"cuda" 或 "cpu"）

    返回：
        {
            "precision": float, "recall": float, "f1": float,
            "precision_std": float, "recall_std": float, "f1_std": float
        }
    """
    calculator = BERTScoreCalculator(model_name, device)
    return calculator.calculate_corpus_bertscore(predictions, references)
