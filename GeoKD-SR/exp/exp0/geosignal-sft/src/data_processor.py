# -*- coding: utf-8 -*-
"""
GeoSignal数据处理模块

处理K2论文的GeoSignal数据集，转换为适用于Qwen2.5-1.5B训练的格式
数据来源: https://github.com/davendw49/k2
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from datasets import Dataset
from transformers import PreTrainedTokenizer

logger = logging.getLogger(__name__)


@dataclass
class GeoSignalSample:
    """GeoSignal数据样本"""
    instruction: str
    input: str
    output: str
    task_type: Optional[str] = None  # 任务类型: NER, QA, Classification等
    signal_type: Optional[str] = None  # 信号类型: G1-G10


class GeoSignalDataProcessor:
    """
    GeoSignal数据处理器

    处理K2论文的GeoSignal数据集，支持:
    - JSON格式数据加载
    - 格式转换为ChatML
    - 数据集划分
    - HF Dataset创建
    """

    # 任务类型映射
    TASK_TYPE_MAP = {
        "命名实体识别": "NER",
        "推理": "Reasoning",
        "事实核查": "FactChecking",
        "摘要": "Summarization",
        "文本分类": "Classification",
        "词语义": "WordSemantics",
        "解释": "Explanation",
        "问答": "QA",
    }

    def __init__(
        self,
        tokenizer: PreTrainedTokenizer,
        max_length: int = 2048,
        system_prompt: str = "You are an expert in geoscience knowledge.",
    ):
        """
        初始化数据处理器

        Args:
            tokenizer: HuggingFace tokenizer
            max_length: 最大序列长度
            system_prompt: 系统提示
        """
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.system_prompt = system_prompt

    def load_geosignal_jsonl(self, file_path: str) -> List[GeoSignalSample]:
        """
        加载GeoSignal JSONL文件

        Args:
            file_path: 文件路径

        Returns:
            样本列表
        """
        samples = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    sample = self._parse_sample(data)
                    if sample:
                        samples.append(sample)
                except json.JSONDecodeError as e:
                    logger.warning(f"跳过无效JSON行 {line_num}: {e}")
                    continue

        logger.info(f"从 {file_path} 加载了 {len(samples)} 条样本")
        return samples

    def _parse_sample(self, data: Dict) -> Optional[GeoSignalSample]:
        """
        解析单个样本

        支持多种格式:
        1. 标准格式: {"instruction": ..., "input": ..., "output": ...}
        2. Alpaca格式: {"instruction": ..., "input": ..., "output": ...}
        3. QA格式: {"question": ..., "answer": ...}
        """
        # 标准格式
        if "instruction" in data:
            return GeoSignalSample(
                instruction=data.get("instruction", ""),
                input=data.get("input", ""),
                output=data.get("output", ""),
                task_type=data.get("task_type"),
                signal_type=data.get("signal_type"),
            )

        # QA格式
        if "question" in data:
            return GeoSignalSample(
                instruction=data.get("question", ""),
                input="",
                output=data.get("answer", ""),
                task_type="QA",
            )

        # prompt/response格式
        if "prompt" in data:
            return GeoSignalSample(
                instruction=data.get("prompt", ""),
                input="",
                output=data.get("response", data.get("completion", "")),
            )

        logger.warning(f"无法解析样本: {list(data.keys())}")
        return None

    def convert_to_chatml(
        self,
        sample: GeoSignalSample,
        tokenize: bool = True
    ) -> Dict:
        """
        将样本转换为ChatML格式

        Args:
            sample: GeoSignal样本
            tokenize: 是否进行tokenization

        Returns:
            处理后的样本字典
        """
        # 构建用户输入
        if sample.input:
            user_content = f"{sample.instruction}\n{sample.input}"
        else:
            user_content = sample.instruction

        # 构建ChatML消息
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": sample.output}
        ]

        # 使用tokenizer的chat template
        full_text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False
        )

        if not tokenize:
            return {"text": full_text}

        # Tokenize
        encoding = self.tokenizer(
            full_text,
            truncation=True,
            max_length=self.max_length,
            padding=False,
            return_tensors=None,
        )

        # 计算labels (用户部分设为-100)
        user_messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_content}
        ]
        user_text = self.tokenizer.apply_chat_template(
            user_messages,
            tokenize=False,
            add_generation_prompt=True
        )
        user_encoding = self.tokenizer(
            user_text,
            truncation=True,
            max_length=self.max_length,
            padding=False,
        )

        user_len = len(user_encoding["input_ids"])
        labels = [-100] * user_len + encoding["input_ids"][user_len:]

        # 确保labels长度一致
        if len(labels) < len(encoding["input_ids"]):
            labels = labels + [-100] * (len(encoding["input_ids"]) - len(labels))
        elif len(labels) > len(encoding["input_ids"]):
            labels = labels[:len(encoding["input_ids"])]

        return {
            "input_ids": encoding["input_ids"],
            "attention_mask": encoding["attention_mask"],
            "labels": labels,
        }

    def create_hf_dataset(
        self,
        samples: List[GeoSignalSample],
    ) -> Dataset:
        """
        创建HuggingFace Dataset

        Args:
            samples: 样本列表

        Returns:
            HF Dataset对象
        """
        processed_data = []
        for sample in samples:
            try:
                processed = self.convert_to_chatml(sample)
                processed_data.append(processed)
            except Exception as e:
                logger.warning(f"处理样本失败: {e}")
                continue

        logger.info(f"成功处理 {len(processed_data)} 条样本")
        return Dataset.from_list(processed_data)

    @staticmethod
    def split_dataset(
        samples: List[GeoSignalSample],
        train_ratio: float = 0.9,
        dev_ratio: float = 0.05,
        test_ratio: float = 0.05,
        seed: int = 42,
    ) -> Tuple[List[GeoSignalSample], List[GeoSignalSample], List[GeoSignalSample]]:
        """
        划分数据集

        Args:
            samples: 样本列表
            train_ratio: 训练集比例
            dev_ratio: 验证集比例
            test_ratio: 测试集比例
            seed: 随机种子

        Returns:
            (train_samples, dev_samples, test_samples)
        """
        import random
        random.seed(seed)

        shuffled = samples.copy()
        random.shuffle(shuffled)

        n = len(shuffled)
        train_end = int(n * train_ratio)
        dev_end = train_end + int(n * dev_ratio)

        train_samples = shuffled[:train_end]
        dev_samples = shuffled[train_end:dev_end]
        test_samples = shuffled[dev_end:]

        logger.info(f"数据集划分: train={len(train_samples)}, dev={len(dev_samples)}, test={len(test_samples)}")

        return train_samples, dev_samples, test_samples

    def save_jsonl(
        self,
        samples: List[GeoSignalSample],
        output_path: str,
    ):
        """
        保存为JSONL格式

        Args:
            samples: 样本列表
            output_path: 输出路径
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            for sample in samples:
                data = {
                    "instruction": sample.instruction,
                    "input": sample.input,
                    "output": sample.output,
                }
                if sample.task_type:
                    data["task_type"] = sample.task_type
                if sample.signal_type:
                    data["signal_type"] = sample.signal_type
                f.write(json.dumps(data, ensure_ascii=False) + '\n')

        logger.info(f"保存 {len(samples)} 条样本到 {output_path}")


def process_geosignal_raw_data(
    input_path: str,
    output_dir: str,
    train_ratio: float = 0.9,
    dev_ratio: float = 0.05,
    seed: int = 42,
):
    """
    处理原始GeoSignal数据

    将原始GeoSignal数据划分为train/dev/test集

    Args:
        input_path: 原始数据路径
        output_dir: 输出目录
        train_ratio: 训练集比例
        dev_ratio: 验证集比例
        seed: 随机种子
    """
    # 加载数据
    samples = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                sample = GeoSignalSample(
                    instruction=data.get("instruction", data.get("question", "")),
                    input=data.get("input", ""),
                    output=data.get("output", data.get("answer", "")),
                )
                if sample.instruction and sample.output:
                    samples.append(sample)

    logger.info(f"加载了 {len(samples)} 条原始样本")

    # 划分数据集
    train, dev, test = GeoSignalDataProcessor.split_dataset(
        samples, train_ratio, dev_ratio, 1 - train_ratio - dev_ratio, seed
    )

    # 保存
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    def save_samples(samples_list, filename):
        with open(output_dir / filename, 'w', encoding='utf-8') as f:
            for s in samples_list:
                f.write(json.dumps({
                    "instruction": s.instruction,
                    "input": s.input,
                    "output": s.output,
                }, ensure_ascii=False) + '\n')

    save_samples(train, "train.jsonl")
    save_samples(dev, "dev.jsonl")
    save_samples(test, "test.jsonl")

    logger.info(f"数据处理完成，保存到 {output_dir}")


if __name__ == "__main__":
    # 示例用法
    import argparse

    parser = argparse.ArgumentParser(description="处理GeoSignal数据")
    parser.add_argument("--input", type=str, required=True, help="输入文件路径")
    parser.add_argument("--output", type=str, required=True, help="输出目录")
    parser.add_argument("--train-ratio", type=float, default=0.9)
    parser.add_argument("--dev-ratio", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    process_geosignal_raw_data(
        args.input,
        args.output,
        args.train_ratio,
        args.dev_ratio,
        args.seed,
    )
