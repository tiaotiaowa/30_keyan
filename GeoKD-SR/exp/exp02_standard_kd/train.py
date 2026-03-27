#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exp2: B2-Standard-KD 训练脚本

通用蒸馏基线：Hinton 2015经典KL蒸馏
损失函数: L_KD = α × L_soft + (1-α) × L_hard

改进:
1. 使用 json.loads() 替代 eval() 安全加载数据
2. 使用 ChatML 模板格式
3. 正确生成 labels（用户部分设为 -100）
4. 教师模型4-bit量化以节省显存
"""

import os
import sys
import json
import yaml
import argparse
import torch
import torch.nn.functional as F
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer,
    DataCollatorForSeq2Seq,
)
from peft import LoraConfig, get_peft_model, TaskType
from datasets import Dataset
import numpy as np


def set_seed(seed: int):
    """设置随机种子"""
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)


def load_config(config_path: str) -> dict:
    """加载配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_teacher_model(config: dict):
    """加载4-bit量化的教师模型 (Qwen2.5-7B-Instruct)"""
    model_name = config['model']['teacher']['name']

    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    teacher = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=quantization_config,
        device_map=config['model']['teacher']['device_map'],
        torch_dtype=torch.float16,
        trust_remote_code=True,
    )

    # 冻结教师参数
    for param in teacher.parameters():
        param.requires_grad = False
    teacher.eval()

    return teacher


def load_student_model(config: dict):
    """加载学生模型 (Qwen2.5-1.5B-Instruct) + LoRA"""
    model_name = config['model']['student']['name']

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=True,
    )

    # 确保tokenizer有pad_token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    lora_config = LoraConfig(
        r=config['model']['student']['lora']['r'],
        lora_alpha=config['model']['student']['lora']['lora_alpha'],
        lora_dropout=config['model']['student']['lora']['lora_dropout'],
        target_modules=config['model']['student']['lora']['target_modules'],
        bias=config['model']['student']['lora']['bias'],
        task_type=TaskType.CAUSAL_LM,
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    return model, tokenizer


def kl_divergence_loss(student_logits, teacher_logits, temperature=2.0):
    """
    计算KL散度蒸馏损失

    Forward KL: KL(P_T || P_S)
    """
    # 获取软标签分布
    p_teacher = F.softmax(teacher_logits / temperature, dim=-1)
    log_p_student = F.log_softmax(student_logits / temperature, dim=-1)

    # KL散度
    kl_loss = F.kl_div(log_p_student, p_teacher, reduction='batchmean')

    # 缩放因子
    return kl_loss * (temperature ** 2)


def load_dataset(data_path: str, tokenizer, max_length: int = 1024, system_prompt: str = ""):
    """
    加载数据集并使用 ChatML 格式处理

    改进：
    1. 使用 json.loads() 安全加载
    2. 使用 ChatML 模板
    3. 正确生成 labels（用户部分设为 -100）
    """
    data = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    # 使用 json.loads() 安全加载
                    item = json.loads(line)
                    data.append(item)
                except json.JSONDecodeError as e:
                    print(f"警告: 跳过无效JSON行: {e}")
                    continue

    print(f"加载了 {len(data)} 条数据")

    def prepare_sample(item):
        """准备单个样本"""
        question = item.get("question", "")
        answer = item.get("answer", "")

        if not question or not answer:
            return None

        # 构建 ChatML 格式消息
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer}
        ]

        # 使用 tokenizer 的 apply_chat_template 方法
        # 生成完整的对话文本
        full_text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False
        )

        # 生成用户部分文本（用于计算 labels）
        user_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]
        user_text = tokenizer.apply_chat_template(
            user_messages,
            tokenize=False,
            add_generation_prompt=True
        )

        # Tokenize
        full_encoding = tokenizer(
            full_text,
            truncation=True,
            max_length=max_length,
            padding=False,
            return_tensors=None,
        )

        user_encoding = tokenizer(
            user_text,
            truncation=True,
            max_length=max_length,
            padding=False,
            return_tensors=None,
        )

        input_ids = full_encoding["input_ids"]
        attention_mask = full_encoding["attention_mask"]

        # 计算用户部分长度
        user_len = len(user_encoding["input_ids"])

        # 生成 labels: 用户部分设为 -100，助手部分保留
        labels = [-100] * user_len + input_ids[user_len:]

        # 确保 labels 长度与 input_ids 一致
        if len(labels) < len(input_ids):
            labels = labels + [-100] * (len(input_ids) - len(labels))
        elif len(labels) > len(input_ids):
            labels = labels[:len(input_ids)]

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
        }

    # 处理所有样本
    processed_data = []
    for item in data:
        sample = prepare_sample(item)
        if sample is not None:
            processed_data.append(sample)

    print(f"成功处理 {len(processed_data)} 条数据")

    # 创建数据集
    dataset = Dataset.from_list(processed_data)

    return dataset


class DistillationTrainer(Trainer):
    """带有知识蒸馏的训练器"""

    def __init__(self, teacher_model, temperature=2.0, alpha=0.5, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.teacher_model = teacher_model
        self.temperature = temperature
        self.alpha = alpha

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        """计算蒸馏损失"""
        # 提取标签
        labels = inputs.get("labels")

        # 学生模型前向传播
        student_outputs = model(**inputs)
        student_logits = student_outputs.logits

        # 教师模型前向传播（不计算梯度）
        with torch.no_grad():
            # 准备教师输入（不需要 labels）
            teacher_inputs = {
                "input_ids": inputs["input_ids"],
                "attention_mask": inputs["attention_mask"],
            }
            teacher_outputs = self.teacher_model(**teacher_inputs)
            teacher_logits = teacher_outputs.logits

        # 计算软标签损失（KL散度）
        # 只计算非 -100 的位置
        if labels is not None:
            # 创建有效位置的掩码
            valid_mask = labels[..., 1:] != -100

            # 获取有效的 logits
            shift_student_logits = student_logits[..., :-1, :].contiguous()
            shift_teacher_logits = teacher_logits[..., :-1, :].contiguous()

            # 应用掩码
            valid_student_logits = shift_student_logits[valid_mask]
            valid_teacher_logits = shift_teacher_logits[valid_mask]

            if valid_student_logits.numel() > 0:
                soft_loss = kl_divergence_loss(
                    valid_student_logits,
                    valid_teacher_logits,
                    self.temperature
                )
            else:
                soft_loss = torch.tensor(0.0, device=student_logits.device)

            # 计算硬标签损失（交叉熵）
            shift_labels = labels[..., 1:].contiguous()
            hard_loss = F.cross_entropy(
                shift_student_logits.view(-1, shift_student_logits.size(-1)),
                shift_labels.view(-1),
                ignore_index=-100
            )
        else:
            soft_loss = torch.tensor(0.0, device=student_logits.device)
            hard_loss = torch.tensor(0.0, device=student_logits.device)

        # 组合损失
        total_loss = self.alpha * soft_loss + (1 - self.alpha) * hard_loss

        # 记录损失详情
        if self.state.is_world_process_zero:
            if hasattr(self, '_step') is False:
                self._step = 0
            self._step += 1
            if self._step % 10 == 0:
                print(f"\n[Step {self._step}] soft_loss: {soft_loss.item():.4f}, "
                      f"hard_loss: {hard_loss.item():.4f}, "
                      f"total_loss: {total_loss.item():.4f}")

        return (total_loss, student_outputs) if return_outputs else total_loss


def main():
    parser = argparse.ArgumentParser(description="Exp2: B2-Standard-KD 训练")
    parser.add_argument("--config", type=str, default="config.yaml")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume", type=str, default=None)
    args = parser.parse_args()

    work_dir = Path(__file__).parent
    os.chdir(work_dir)

    config = load_config(args.config)
    set_seed(args.seed)

    # 获取系统提示
    system_prompt = config.get('chat_template', {}).get(
        'system_prompt',
        "你是一个地理空间推理专家，擅长分析和解决空间关系问题。"
    )

    print("=" * 60)
    print("Exp2: B2-Standard-KD（通用蒸馏基线）")
    print("=" * 60)
    print(f"配置文件: {args.config}")
    print(f"随机种子: {args.seed}")
    print(f"教师模型: {config['model']['teacher']['name']} (4-bit量化)")
    print(f"学生模型: {config['model']['student']['name']}")
    print(f"温度参数: {config['distillation']['temperature']}")
    print(f"蒸馏权重α: {config['distillation']['alpha']}")
    print(f"Batch Size: {config['training']['batch_size']}")
    print(f"Gradient Accumulation: {config['training']['gradient_accumulation_steps']}")
    print(f"有效 Batch Size: {config['training']['batch_size'] * config['training']['gradient_accumulation_steps']}")
    print("=" * 60)

    # 加载模型
    print("\n[1/4] 加载模型...")
    print("  - 加载教师模型 (4-bit量化)...")
    teacher_model = load_teacher_model(config)
    print("  - 加载学生模型...")
    student_model, tokenizer = load_student_model(config)

    # 加载数据集
    print("\n[2/4] 加载数据集...")
    train_dataset = load_dataset(
        config['data']['train_path'], tokenizer, config['data']['max_length'], system_prompt
    )
    eval_dataset = load_dataset(
        config['data']['dev_path'], tokenizer, config['data']['max_length'], system_prompt
    )

    # 训练参数
    print("\n[3/4] 配置训练参数...")
    training_args = TrainingArguments(
        output_dir=config['output']['checkpoint_dir'],
        num_train_epochs=config['training']['num_epochs'],
        per_device_train_batch_size=config['training']['batch_size'],
        per_device_eval_batch_size=config['training']['batch_size'],
        gradient_accumulation_steps=config['training']['gradient_accumulation_steps'],
        learning_rate=config['training']['learning_rate'],
        weight_decay=config['training']['weight_decay'],
        warmup_ratio=config['training']['warmup_ratio'],
        max_grad_norm=config['training']['max_grad_norm'],
        logging_dir=config['output']['log_dir'],
        logging_steps=config['training']['logging_steps'],
        save_steps=config['training']['save_steps'],
        eval_steps=config['training']['eval_steps'],
        evaluation_strategy="steps",
        save_strategy="steps",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        fp16=True,
        gradient_checkpointing=True,
        report_to="tensorboard",
        remove_unused_columns=False,  # 保留自定义列
    )

    # 数据整理器
    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        model=student_model,
        padding=True,
        pad_to_multiple_of=8,
    )

    # 训练器
    trainer = DistillationTrainer(
        teacher_model=teacher_model,
        temperature=config['distillation']['temperature'],
        alpha=config['distillation']['alpha'],
        model=student_model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        tokenizer=tokenizer,
        data_collator=data_collator,
    )

    # 开始训练
    print("\n[4/4] 开始训练...")
    print(f"训练开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if args.resume:
        trainer.train(resume_from_checkpoint=args.resume)
    else:
        trainer.train()

    # 保存最终模型
    final_model_path = Path(config['output']['checkpoint_dir']) / "final_model"
    trainer.save_model(str(final_model_path))
    tokenizer.save_pretrained(str(final_model_path))

    print(f"\n训练完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"最终模型保存至: {final_model_path}")


if __name__ == "__main__":
    main()
