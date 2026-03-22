"""
GeoKD-SR 数据处理模块
=====================

将 GeoKD-SR 原始数据转换为 Qwen2.5 ChatML 格式用于 SFT 训练。

主要功能:
1. 将原始 JSONL 数据转换为 ChatML 格式
2. 使用 Qwen2.5 tokenizer 的 apply_chat_template 方法
3. 正确构造 labels (system 和 user 段设为 -100)
4. 支持 splits 和 split_coords 两种数据版本

作者: GeoKD-SR Project
日期: 2026-03-21
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass

import torch
from torch.utils.data import Dataset
from transformers import PreTrainedTokenizer, AutoTokenizer
from datasets import Dataset as HFDataset


@dataclass
class DataConfig:
    """数据配置类"""
    data_dir: str = "D:/30_keyan/GeoKD-SR/data"
    data_version: str = "splits"  # "splits" 或 "split_coords"
    max_length: int = 2048
    train_file: str = "train.jsonl"
    dev_file: str = "dev.jsonl"
    test_file: str = "test.jsonl"
    system_prompt: str = "你是一个专业的地理空间推理助手，擅长回答关于地理位置、方向、距离和拓扑关系的问题。"


class ChatMLConverter:
    """
    ChatML 格式转换器

    将 GeoKD-SR 数据转换为 Qwen2.5 的 ChatML 格式
    """

    # 系统提示词
    DEFAULT_SYSTEM_PROMPT = "你是一个专业的地理空间推理助手，擅长回答关于地理位置、方向、距离和拓扑关系的问题。"

    def __init__(
        self,
        tokenizer: PreTrainedTokenizer,
        system_prompt: Optional[str] = None,
        max_length: int = 2048
    ):
        """
        初始化转换器

        Args:
            tokenizer: 预训练的 tokenizer
            system_prompt: 系统提示词，默认使用地理推理专用提示词
            max_length: 最大序列长度
        """
        self.tokenizer = tokenizer
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        self.max_length = max_length

        # 确保 tokenizer 有 pad_token
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

    def convert_to_messages(
        self,
        question: str,
        answer: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, str]]:
        """
        将问题和答案转换为 ChatML 消息格式

        Args:
            question: 问题文本
            answer: 答案文本
            metadata: 可选的元数据（如 spatial_relation_type, difficulty 等）

        Returns:
            ChatML 格式的消息列表
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer}
        ]
        return messages

    def tokenize_with_labels(
        self,
        messages: List[Dict[str, str]]
    ) -> Dict[str, torch.Tensor]:
        """
        对消息进行分词并构造 labels

        关键点:
        - 使用 apply_chat_template 生成 input_ids
        - system 和 user 段的 labels 设为 -100
        - 只有 assistant 段计算损失

        Args:
            messages: ChatML 格式的消息列表

        Returns:
            包含 input_ids, attention_mask, labels 的字典
        """
        # 使用 Qwen2.5 的 apply_chat_template
        # tokenize=True 返回 input_ids
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False
        )

        # 分词
        tokenized = self.tokenizer(
            text,
            max_length=self.max_length,
            truncation=True,
            padding=False,
            return_tensors=None
        )

        input_ids = tokenized["input_ids"]
        attention_mask = tokenized["attention_mask"]

        # 构造 labels: 需要识别 assistant 段的位置
        labels = self._construct_labels(input_ids, messages)

        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long)
        }

    def _construct_labels(
        self,
        input_ids: List[int],
        messages: List[Dict[str, str]]
    ) -> List[int]:
        """
        构造 labels tensor

        核心逻辑:
        1. 初始化所有位置为 -100
        2. 找到 assistant 回复的起始和结束位置
        3. 只将 assistant 段设为对应的 token id

        Args:
            input_ids: 输入 token ids
            messages: 原始消息列表

        Returns:
            labels 列表
        """
        # 初始化: 所有位置设为 -100
        labels = [-100] * len(input_ids)

        # 方法1: 通过特殊 token 定位 assistant 段
        # Qwen2.5 使用 <|im_start|> 和 <|im_end|> 标记不同角色

        # 获取特殊 token
        im_start = self.tokenizer.encode("<|im_start|>", add_special_tokens=False)
        im_end = self.tokenizer.encode("<|im_end|>", add_special_tokens=False)
        assistant_token = self.tokenizer.encode("assistant\n", add_special_tokens=False)

        # 在 input_ids 中查找 assistant 段
        input_ids_list = list(input_ids)

        # 查找所有 <|im_start|>assistant 的位置
        assistant_starts = self._find_pattern_positions(
            input_ids_list,
            im_start + assistant_token
        )

        if assistant_starts:
            # 获取 assistant 段内容
            assistant_content = messages[-1]["content"]  # 最后一条消息是 assistant
            assistant_tokens = self.tokenizer.encode(
                assistant_content,
                add_special_tokens=False
            )

            # 找到 assistant 内容的结束位置 (下一个 <|im_end|>)
            for start_pos in assistant_starts:
                # 计算内容实际开始位置
                content_start = start_pos + len(im_start) + len(assistant_token)

                # 查找结束位置
                end_positions = self._find_pattern_positions(
                    input_ids_list[content_start:],
                    im_end
                )

                if end_positions:
                    content_end = content_start + end_positions[0]

                    # 确保 content_end 不超过 assistant 内容长度
                    actual_end = min(content_end, content_start + len(assistant_tokens))

                    # 设置 labels
                    for i in range(content_start, actual_end):
                        if i < len(labels):
                            labels[i] = input_ids[i]

                    break  # 只处理第一个 assistant 段

        # 方法2: 备用方案 - 直接定位 assistant 内容
        if all(l == -100 for l in labels):
            labels = self._construct_labels_fallback(input_ids_list, messages)

        return labels

    def _find_pattern_positions(
        self,
        sequence: List[int],
        pattern: List[int]
    ) -> List[int]:
        """
        在序列中查找模式出现的所有位置

        Args:
            sequence: 要搜索的序列
            pattern: 要查找的模式

        Returns:
            所有匹配位置的列表
        """
        positions = []
        pattern_len = len(pattern)

        for i in range(len(sequence) - pattern_len + 1):
            if sequence[i:i + pattern_len] == pattern:
                positions.append(i)

        return positions

    def _construct_labels_fallback(
        self,
        input_ids: List[int],
        messages: List[Dict[str, str]]
    ) -> List[int]:
        """
        备用 label 构造方法

        通过直接编码 assistant 内容来定位
        """
        labels = [-100] * len(input_ids)

        # 获取 assistant 内容
        assistant_content = messages[-1]["content"]
        assistant_tokens = self.tokenizer.encode(
            assistant_content,
            add_special_tokens=False
        )

        if not assistant_tokens:
            return labels

        # 在 input_ids 末尾查找 assistant tokens
        # 通常 assistant 回复在序列末尾
        for i in range(len(input_ids) - len(assistant_tokens) + 1):
            match = True
            for j, token in enumerate(assistant_tokens):
                if input_ids[i + j] != token:
                    match = False
                    break

            if match:
                # 找到匹配,设置 labels
                for j in range(len(assistant_tokens)):
                    if i + j < len(labels):
                        labels[i + j] = input_ids[i + j]
                break

        return labels

    def process_single_example(
        self,
        example: Dict[str, Any]
    ) -> Dict[str, torch.Tensor]:
        """
        处理单个样本

        Args:
            example: 包含 question, answer 等字段的字典

        Returns:
            包含 input_ids, attention_mask, labels 的字典
        """
        question = example.get("question", "")
        answer = example.get("answer", "")

        # 转换为消息格式
        messages = self.convert_to_messages(question, answer, example)

        # 分词并构造 labels
        return self.tokenize_with_labels(messages)


class GeoSRDataProcessor(Dataset):
    """
    GeoKD-SR 数据处理器

    继承自 torch.utils.data.Dataset,处理数据加载和预处理
    """

    def __init__(
        self,
        data_path: str,
        tokenizer: PreTrainedTokenizer,
        max_length: int = 2048,
        system_prompt: Optional[str] = None,
        data_version: str = "splits",
        split: str = "train"
    ):
        """
        初始化数据处理器

        Args:
            data_path: 数据目录路径
            tokenizer: 预训练的 tokenizer
            max_length: 最大序列长度
            system_prompt: 系统提示词
            data_version: 数据版本 ("splits" 或 "split_coords")
            split: 数据分割 ("train", "dev", "test")
        """
        self.data_path = Path(data_path)
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.data_version = data_version
        self.split = split

        # 初始化转换器
        self.converter = ChatMLConverter(
            tokenizer=tokenizer,
            system_prompt=system_prompt,
            max_length=max_length
        )

        # 加载数据
        self.data = self._load_data()

        print(f"[GeoSRDataProcessor] 加载 {split} 数据: {len(self.data)} 条样本")
        print(f"[GeoSRDataProcessor] 数据版本: {data_version}")
        print(f"[GeoSRDataProcessor] 最大长度: {max_length}")

    def _load_data(self) -> List[Dict[str, Any]]:
        """
        加载 JSONL 数据文件

        Returns:
            数据列表
        """
        # 构建数据文件路径
        version_dir = self.data_path / self.data_version

        # 根据分割选择文件
        file_map = {
            "train": "train.jsonl",
            "dev": "dev.jsonl",
            "test": "test.jsonl"
        }

        file_path = version_dir / file_map.get(self.split, "train.jsonl")

        if not file_path.exists():
            raise FileNotFoundError(f"数据文件不存在: {file_path}")

        # 加载 JSONL
        data = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data.append(json.loads(line))

        return data

    def __len__(self) -> int:
        """返回数据集大小"""
        return len(self.data)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        """
        获取单个样本

        Args:
            idx: 样本索引

        Returns:
            包含 input_ids, attention_mask, labels 的字典
        """
        example = self.data[idx]
        return self.converter.process_single_example(example)

    def get_raw_example(self, idx: int) -> Dict[str, Any]:
        """
        获取原始样本(未处理)

        Args:
            idx: 样本索引

        Returns:
            原始数据字典
        """
        return self.data[idx]

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取数据集统计信息

        Returns:
            统计信息字典
        """
        stats = {
            "total_samples": len(self.data),
            "data_version": self.data_version,
            "split": self.split,
            "spatial_types": {},
            "difficulty_distribution": {"easy": 0, "medium": 0, "hard": 0},
            "avg_question_length": 0,
            "avg_answer_length": 0
        }

        total_q_len = 0
        total_a_len = 0

        for example in self.data:
            # 统计空间关系类型
            spatial_type = example.get("spatial_relation_type", "unknown")
            stats["spatial_types"][spatial_type] = \
                stats["spatial_types"].get(spatial_type, 0) + 1

            # 统计难度分布
            difficulty = example.get("difficulty", "unknown")
            if difficulty in stats["difficulty_distribution"]:
                stats["difficulty_distribution"][difficulty] += 1

            # 统计长度
            total_q_len += len(example.get("question", ""))
            total_a_len += len(example.get("answer", ""))

        if len(self.data) > 0:
            stats["avg_question_length"] = total_q_len / len(self.data)
            stats["avg_answer_length"] = total_a_len / len(self.data)

        return stats

    def to_hf_dataset(self) -> HFDataset:
        """
        将数据转换为 Hugging Face Dataset 格式

        TRL 的 SFTTrainer 需要 HF Dataset 格式，包含 column_names 属性。
        此方法将内部数据转换为 messages 格式的 HF Dataset。

        Returns:
            Hugging Face Dataset 对象，包含 'messages' 列
        """
        # 构建 messages 格式的数据
        messages_data = []
        for example in self.data:
            messages = [
                {"role": "system", "content": self.converter.system_prompt},
                {"role": "user", "content": example.get("question", "")},
                {"role": "assistant", "content": example.get("answer", "")}
            ]
            messages_data.append({"messages": messages})

        # 创建 Hugging Face Dataset
        hf_dataset = HFDataset.from_list(messages_data)
        return hf_dataset

    @staticmethod
    def create_hf_dataset(
        data_path: str,
        tokenizer: PreTrainedTokenizer,
        max_length: int = 2048,
        system_prompt: Optional[str] = None,
        data_version: str = "splits",
        split: str = "train"
    ) -> HFDataset:
        """
        静态方法：直接创建 Hugging Face Dataset

        这是推荐的创建方式，避免了中间的 torch Dataset 转换。

        Args:
            data_path: 数据目录路径
            tokenizer: 预训练的 tokenizer
            max_length: 最大序列长度
            system_prompt: 系统提示词
            data_version: 数据版本 ("splits" 或 "split_coords")
            split: 数据分割 ("train", "dev", "test")

        Returns:
            Hugging Face Dataset 对象
        """
        processor = GeoSRDataProcessor(
            data_path=data_path,
            tokenizer=tokenizer,
            max_length=max_length,
            system_prompt=system_prompt,
            data_version=data_version,
            split=split
        )
        return processor.to_hf_dataset()


class DataCollatorForGeoSR:
    """
    GeoKD-SR 数据整理器

    处理 batch 内的 padding 和 tensor 堆叠
    """

    def __init__(
        self,
        tokenizer: PreTrainedTokenizer,
        max_length: int = 2048,
        pad_to_multiple_of: Optional[int] = None
    ):
        """
        初始化数据整理器

        Args:
            tokenizer: tokenizer
            max_length: 最大长度
            pad_to_multiple_of: padding 到该数的倍数
        """
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.pad_to_multiple_of = pad_to_multiple_of

    def __call__(
        self,
        batch: List[Dict[str, torch.Tensor]]
    ) -> Dict[str, torch.Tensor]:
        """
        整理 batch

        Args:
            batch: 样本列表

        Returns:
            整理后的 batch 字典
        """
        # 收集所有字段
        input_ids_list = [item["input_ids"] for item in batch]
        attention_mask_list = [item["attention_mask"] for item in batch]
        labels_list = [item["labels"] for item in batch]

        # Padding
        max_len = max(len(ids) for ids in input_ids_list)
        max_len = min(max_len, self.max_length)

        if self.pad_to_multiple_of:
            max_len = ((max_len + self.pad_to_multiple_of - 1) //
                      self.pad_to_multiple_of * self.pad_to_multiple_of)

        # Pad sequences
        input_ids = self._pad_sequence(input_ids_list, max_len, self.tokenizer.pad_token_id)
        attention_mask = self._pad_sequence(attention_mask_list, max_len, 0)
        labels = self._pad_sequence(labels_list, max_len, -100)

        return {
            "input_ids": torch.stack(input_ids),
            "attention_mask": torch.stack(attention_mask),
            "labels": torch.stack(labels)
        }

    def _pad_sequence(
        self,
        sequences: List[torch.Tensor],
        max_len: int,
        pad_value: int
    ) -> List[torch.Tensor]:
        """
        Padding 序列列表

        Args:
            sequences: 序列列表
            max_len: 目标长度
            pad_value: padding 值

        Returns:
            Padding 后的序列列表
        """
        result = []
        for seq in sequences:
            if len(seq) < max_len:
                # Right padding
                padding = torch.full(
                    (max_len - len(seq),),
                    pad_value,
                    dtype=seq.dtype
                )
                seq = torch.cat([seq, padding])
            else:
                seq = seq[:max_len]
            result.append(seq)
        return result


def create_dataloaders(
    data_dir: str,
    tokenizer: PreTrainedTokenizer,
    data_version: str = "splits",
    max_length: int = 2048,
    batch_size: int = 8,
    num_workers: int = 4,
    system_prompt: Optional[str] = None
) -> Tuple[torch.utils.data.DataLoader, ...]:
    """
    创建训练、验证和测试数据加载器

    Args:
        data_dir: 数据目录
        tokenizer: tokenizer
        data_version: 数据版本
        max_length: 最大长度
        batch_size: batch 大小
        num_workers: 数据加载线程数
        system_prompt: 系统提示词

    Returns:
        (train_loader, dev_loader, test_loader)
    """
    from torch.utils.data import DataLoader

    # 创建数据集
    train_dataset = GeoSRDataProcessor(
        data_path=data_dir,
        tokenizer=tokenizer,
        max_length=max_length,
        system_prompt=system_prompt,
        data_version=data_version,
        split="train"
    )

    dev_dataset = GeoSRDataProcessor(
        data_path=data_dir,
        tokenizer=tokenizer,
        max_length=max_length,
        system_prompt=system_prompt,
        data_version=data_version,
        split="dev"
    )

    test_dataset = GeoSRDataProcessor(
        data_path=data_dir,
        tokenizer=tokenizer,
        max_length=max_length,
        system_prompt=system_prompt,
        data_version=data_version,
        split="test"
    )

    # 创建数据整理器
    collator = DataCollatorForGeoSR(
        tokenizer=tokenizer,
        max_length=max_length
    )

    # 创建数据加载器
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        collate_fn=collator,
        pin_memory=True
    )

    dev_loader = DataLoader(
        dev_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        collate_fn=collator,
        pin_memory=True
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        collate_fn=collator,
        pin_memory=True
    )

    return train_loader, dev_loader, test_loader


def test_data_processor():
    """
    测试数据处理器
    """
    print("=" * 60)
    print("测试 GeoKD-SR 数据处理器")
    print("=" * 60)

    # 初始化 tokenizer
    model_path = "D:/30_keyan/GeoKD-SR/models/Qwen2.5-1.5B-Instruct"
    print(f"\n加载 tokenizer: {model_path}")

    try:
        tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True,
            use_fast=False
        )
        print("Tokenizer 加载成功")
    except Exception as e:
        print(f"Tokenizer 加载失败: {e}")
        print("使用在线 tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(
            "Qwen/Qwen2.5-1.5B-Instruct",
            trust_remote_code=True
        )

    # 测试 ChatML 转换器
    print("\n" + "-" * 60)
    print("测试 ChatMLConverter")
    print("-" * 60)

    converter = ChatMLConverter(tokenizer)

    test_example = {
        "question": "从北京看，上海位于什么方向？",
        "answer": "从北京看，上海位于东南方向。"
    }

    messages = converter.convert_to_messages(
        test_example["question"],
        test_example["answer"]
    )

    print("\n转换后的消息:")
    for msg in messages:
        print(f"  [{msg['role']}]: {msg['content'][:50]}...")

    # 测试分词和 label 构造
    result = converter.tokenize_with_labels(messages)

    print(f"\n分词结果:")
    print(f"  input_ids shape: {result['input_ids'].shape}")
    print(f"  attention_mask shape: {result['attention_mask'].shape}")
    print(f"  labels shape: {result['labels'].shape}")

    # 统计 labels
    valid_labels = (result['labels'] != -100).sum().item()
    print(f"  有效 label 数量: {valid_labels}")

    # 测试数据集
    print("\n" + "-" * 60)
    print("测试 GeoSRDataProcessor")
    print("-" * 60)

    data_dir = "D:/30_keyan/GeoKD-SR/data"

    try:
        # 测试 splits 版本
        print("\n测试 splits 版本:")
        dataset = GeoSRDataProcessor(
            data_path=data_dir,
            tokenizer=tokenizer,
            max_length=2048,
            data_version="splits",
            split="train"
        )

        # 获取统计信息
        stats = dataset.get_statistics()
        print(f"\n数据集统计:")
        print(f"  总样本数: {stats['total_samples']}")
        print(f"  空间关系类型: {stats['spatial_types']}")
        print(f"  难度分布: {stats['difficulty_distribution']}")
        print(f"  平均问题长度: {stats['avg_question_length']:.2f}")
        print(f"  平均答案长度: {stats['avg_answer_length']:.2f}")

        # 测试获取样本
        sample = dataset[0]
        print(f"\n样本 0:")
        print(f"  input_ids shape: {sample['input_ids'].shape}")
        print(f"  labels 有效数量: {(sample['labels'] != -100).sum().item()}")

        # 测试 split_coords 版本
        print("\n测试 split_coords 版本:")
        dataset_coords = GeoSRDataProcessor(
            data_path=data_dir,
            tokenizer=tokenizer,
            max_length=2048,
            data_version="split_coords",
            split="train"
        )

        sample_coords = dataset_coords[0]
        print(f"样本 0 (带坐标):")
        print(f"  input_ids shape: {sample_coords['input_ids'].shape}")

        # 对比两个版本
        raw_normal = dataset.get_raw_example(0)
        raw_coords = dataset_coords.get_raw_example(0)

        print(f"\n问题对比:")
        print(f"  splits: {raw_normal['question'][:60]}...")
        print(f"  split_coords: {raw_coords['question'][:60]}...")

    except Exception as e:
        print(f"数据集测试失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_data_processor()
