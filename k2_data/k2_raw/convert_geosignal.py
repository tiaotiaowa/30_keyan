# -*- coding: utf-8 -*-
"""
GeoSignal数据转换脚本
将GeoSignal转换为ChatML格式的JSONL文件，用于SFT训练
"""

import os
import json
from pathlib import Path
from datasets import load_from_disk


def convert_geosignal_to_chatml(
    input_path: str,
    output_path: str,
    system_prompt: str = "你是一个地理空间推理专家，专门回答关于地球科学、地理、地质和环境科学的问题。请简洁准确地回答问题。",
    max_samples: int = None
):
    """
    将GeoSignal转换为ChatML格式的JSONL

    Args:
        input_path: GeoSignal数据集路径
        output_path: 输出JSONL文件路径
        system_prompt: 系统提示
        max_samples: 最大样本数（用于测试）
    """
    print(f"加载GeoSignal数据集: {input_path}")
    dataset = load_from_disk(input_path)

    print(f"数据集大小: {len(dataset['train'])}")

    # 确保输出目录存在
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 转换数据
    converted = []
    train_data = dataset['train']

    if max_samples:
        train_data = train_data.select(range(min(max_samples, len(train_data))))

    for sample in train_data:
        instruction = sample.get('instruction', '')
        input_text = sample.get('input', '')
        output = sample.get('output', '')

        # 构建用户消息
        if input_text:
            user_content = f"{instruction}\n{input_text}"
        else:
            user_content = instruction

        # ChatML格式
        chatml = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
                {"role": "assistant", "content": output}
            ]
        }

        converted.append(chatml)

    # 保存为JSONL
    with open(output_path, 'w', encoding='utf-8') as f:
        for item in converted:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    print(f"转换完成: {len(converted)} 条样本")
    print(f"保存到: {output_path}")

    # 统计任务类型
    if 'type' in dataset['train'].column_names:
        from collections import Counter
        types = Counter(dataset['train']['type'])
        print("\n任务类型分布:")
        for t, count in types.most_common():
            print(f"  {t}: {count}")

    return len(converted)


def split_train_dev(
    input_path: str,
    train_output: str,
    dev_output: str,
    dev_ratio: float = 0.05,
    seed: int = 42
):
    """
    将数据集分割为训练集和验证集

    Args:
        input_path: 输入JSONL文件
        train_output: 训练集输出路径
        dev_output: 验证集输出路径
        dev_ratio: 验证集比例
        seed: 随机种子
    """
    import random
    random.seed(seed)

    # 读取数据
    with open(input_path, 'r', encoding='utf-8') as f:
        data = [json.loads(line) for line in f]

    # 打乱数据
    random.shuffle(data)

    # 分割
    dev_size = int(len(data) * dev_ratio)
    dev_data = data[:dev_size]
    train_data = data[dev_size:]

    # 保存
    with open(train_output, 'w', encoding='utf-8') as f:
        for item in train_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    with open(dev_output, 'w', encoding='utf-8') as f:
        for item in dev_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    print(f"\n数据分割完成:")
    print(f"  训练集: {len(train_data)} 条 -> {train_output}")
    print(f"  验证集: {len(dev_data)} 条 -> {dev_output}")


def main():
    script_dir = Path(__file__).resolve().parent

    # 输入路径
    geosignal_path = script_dir / "geosignal"

    # 输出路径
    output_dir = script_dir / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 转换数据
    temp_output = output_dir / "geosignal_full.jsonl"
    convert_geosignal_to_chatml(
        input_path=str(geosignal_path),
        output_path=str(temp_output),
        system_prompt="You are a geography expert specializing in Earth science, geology, and environmental science. Please provide accurate and concise answers.",
    )

    # 分割训练/验证集
    split_train_dev(
        input_path=str(temp_output),
        train_output=str(output_dir / "geosignal_train.jsonl"),
        dev_output=str(output_dir / "geosignal_dev.jsonl"),
        dev_ratio=0.05,
        seed=42
    )

    # 删除临时文件
    temp_output.unlink()

    print("\n数据处理完成!")


if __name__ == "__main__":
    main()
