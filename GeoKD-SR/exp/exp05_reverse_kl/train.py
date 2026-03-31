#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exp05: B2+C3 逆向KL蒸馏

基于exp02 Standard-KD框架，将KL方向从Forward KL替换为Reverse KL
- Forward KL: KL(P_T || P_S) — mode-covering
- Reverse KL: KL(P_S || P_T) — mode-seeking

消融设计：与exp02仅KL方向不同，其他变量完全一致
参考: MiniLLM (Gu et al., ICLR 2024)
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
    """加载教师模型 (Qwen2.5-7B-Instruct)，支持全量bf16或4-bit量化"""
    model_name = config['model']['teacher']['name']
    quantization = config['model']['teacher'].get('quantization', '4bit')

    load_kwargs = {
        'device_map': config['model']['teacher']['device_map'],
        'dtype': torch.bfloat16,
        'trust_remote_code': True,
    }

    if quantization == "4bit":
        load_kwargs['quantization_config'] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
        print("  - 教师模型加载模式: 4-bit量化 (NF4)")
    else:
        print("  - 教师模型加载模式: 全量 bf16")

    teacher = AutoModelForCausalLM.from_pretrained(model_name, **load_kwargs)

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
        dtype=torch.bfloat16,
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
    model.enable_input_require_grads()
    model.config.use_cache = False
    model.print_trainable_parameters()

    return model, tokenizer


# ============================================================
# KL散度损失函数 — exp05核心差异：支持Reverse KL和混合KL
# ============================================================

def forward_kl_loss(student_logits, teacher_logits, temperature=2.0):
    """
    Forward KL: KL(P_T || P_S) = F.kl_div(log_P_S, P_T)
    Mode-covering：学生分布尽可能覆盖教师分布的所有模式
    与exp02完全一致
    """
    min_vocab = min(student_logits.size(-1), teacher_logits.size(-1))
    student_logits = student_logits[..., :min_vocab]
    teacher_logits = teacher_logits[..., :min_vocab]

    p_teacher = F.softmax(teacher_logits / temperature, dim=-1)
    log_p_student = F.log_softmax(student_logits / temperature, dim=-1)
    kl_loss = F.kl_div(log_p_student, p_teacher, reduction='batchmean')
    return kl_loss * (temperature ** 2)


def reverse_kl_loss(student_logits, teacher_logits, temperature=2.0):
    """
    Reverse KL: KL(P_S || P_T) = F.kl_div(log_P_T, P_S)
    Mode-seeking：学生聚焦于教师的高概率区域，减少幻觉

    数学验证：
    F.kl_div(input, target) = Σ target * (log(target) - input)
    input = log_P_T, target = P_S
    = Σ P_S * (log P_S - log P_T) = KL(P_S || P_T) ✓
    """
    min_vocab = min(student_logits.size(-1), teacher_logits.size(-1))
    student_logits = student_logits[..., :min_vocab]
    teacher_logits = teacher_logits[..., :min_vocab]

    p_student = F.softmax(student_logits / temperature, dim=-1)
    log_p_teacher = F.log_softmax(teacher_logits / temperature, dim=-1)
    kl_loss = F.kl_div(log_p_teacher, p_student, reduction='batchmean')
    return kl_loss * (temperature ** 2)


def mixed_kl_loss(student_logits, teacher_logits, temperature=2.0,
                  forward_weight=0.0, reverse_weight=1.0):
    """混合Forward KL和Reverse KL，支持灵活消融"""
    if forward_weight > 0 and reverse_weight > 0:
        fkl = forward_kl_loss(student_logits, teacher_logits, temperature)
        rkl = reverse_kl_loss(student_logits, teacher_logits, temperature)
        return forward_weight * fkl + reverse_weight * rkl
    elif forward_weight > 0:
        return forward_kl_loss(student_logits, teacher_logits, temperature)
    else:
        return reverse_kl_loss(student_logits, teacher_logits, temperature)


def load_dataset(data_path: str, tokenizer, max_length: int = 1024):
    """
    加载数据集并使用 ChatML 格式处理
    与exp02完全一致：json.loads + ChatML模板 + labels=-100
    """
    data = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
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

        # 构建 ChatML 格式消息（无system prompt，对齐SFT训练格式）
        messages = [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer}
        ]

        full_text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False
        )

        user_messages = [
            {"role": "user", "content": question}
        ]
        user_text = tokenizer.apply_chat_template(
            user_messages,
            tokenize=False,
            add_generation_prompt=True
        )

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
        user_len = len(user_encoding["input_ids"])

        # labels: 用户部分=-100，助手部分保留
        labels = [-100] * user_len + input_ids[user_len:]

        if len(labels) < len(input_ids):
            labels = labels + [-100] * (len(input_ids) - len(labels))
        elif len(labels) > len(input_ids):
            labels = labels[:len(input_ids)]

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
        }

    processed_data = []
    for item in data:
        sample = prepare_sample(item)
        if sample is not None:
            processed_data.append(sample)

    print(f"成功处理 {len(processed_data)} 条数据")

    dataset = Dataset.from_list(processed_data)
    return dataset


class ReverseKLDistillationTrainer(Trainer):
    """带有逆向KL蒸馏的训练器，支持混合KL权重"""

    def __init__(self, teacher_model, temperature=2.0, alpha=0.5,
                 forward_weight=0.0, reverse_weight=1.0, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.teacher_model = teacher_model
        self.temperature = float(temperature)
        self.alpha = float(alpha)
        self.forward_weight = float(forward_weight)
        self.reverse_weight = float(reverse_weight)

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        """计算蒸馏损失 — 与exp02框架一致，仅KL方向不同"""
        labels = inputs.get("labels")

        # 学生模型前向传播
        student_outputs = model(**inputs)
        student_logits = student_outputs.logits

        # 教师模型前向传播（不计算梯度）
        with torch.no_grad():
            teacher_inputs = {
                "input_ids": inputs["input_ids"],
                "attention_mask": inputs["attention_mask"],
            }
            teacher_outputs = self.teacher_model(**teacher_inputs)
            teacher_logits = teacher_outputs.logits

        # 计算软标签损失（混合KL — 默认纯Reverse KL）
        if labels is not None:
            valid_mask = labels[..., 1:] != -100

            shift_student_logits = student_logits[..., :-1, :].contiguous()
            shift_teacher_logits = teacher_logits[..., :-1, :].contiguous()

            valid_student_logits = shift_student_logits[valid_mask]
            valid_teacher_logits = shift_teacher_logits[valid_mask]

            if valid_student_logits.numel() > 0:
                soft_loss = mixed_kl_loss(
                    valid_student_logits,
                    valid_teacher_logits,
                    self.temperature,
                    self.forward_weight,
                    self.reverse_weight
                )
            else:
                soft_loss = torch.tensor(0.0, device=student_logits.device)

            # 硬标签损失（交叉熵）
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
            step = self.state.global_step
            if step % 10 == 0:
                print(f"\n[Step {step}] soft_loss: {soft_loss.item():.4f}, "
                      f"hard_loss: {hard_loss.item():.4f}, "
                      f"total_loss: {total_loss.item():.4f}")

        return (total_loss, student_outputs) if return_outputs else total_loss


def main():
    parser = argparse.ArgumentParser(description="Exp05: B2+C3（逆向KL蒸馏）训练")
    parser.add_argument("--config", type=str, default="config.yaml")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume", type=str, default=None)
    args = parser.parse_args()

    work_dir = Path(__file__).parent
    os.chdir(work_dir)

    config = load_config(args.config)
    set_seed(args.seed)

    rkl_config = config['distillation']['reverse_kl']
    fw = rkl_config['forward_weight']
    rw = rkl_config['reverse_weight']

    print("=" * 60)
    print("Exp05: B2+C3（逆向KL蒸馏）")
    print("=" * 60)
    print(f"配置文件: {args.config}")
    print(f"随机种子: {args.seed}")
    print(f"教师模型: {config['model']['teacher']['name']} ({config['model']['teacher'].get('quantization', '4bit')})")
    print(f"学生模型: {config['model']['student']['name']}")
    print(f"温度参数: {config['distillation']['temperature']}")
    print(f"蒸馏权重α: {config['distillation']['alpha']}")
    print(f"KL方向: Forward KL权重={fw}, Reverse KL权重={rw}")
    if fw == 0.0 and rw == 1.0:
        print(f"  → 纯Reverse KL: KL(P_S || P_T) [mode-seeking]")
    elif fw == 1.0 and rw == 0.0:
        print(f"  → 纯Forward KL: KL(P_T || P_S) [mode-covering]")
    else:
        print(f"  → 混合KL: {fw:.1f}×FKL + {rw:.1f}×RKL")
    print(f"Batch Size: {config['training']['batch_size']}")
    print(f"Gradient Accumulation: {config['training']['gradient_accumulation_steps']}")
    print(f"有效 Batch Size: {config['training']['batch_size'] * config['training']['gradient_accumulation_steps']}")
    print("=" * 60)

    # 加载模型
    print("\n[1/4] 加载模型...")
    print("  - 加载教师模型...")
    teacher_model = load_teacher_model(config)
    print("  - 加载学生模型...")
    student_model, tokenizer = load_student_model(config)

    # 加载数据集
    print("\n[2/4] 加载数据集...")
    train_dataset = load_dataset(
        config['data']['train_path'], tokenizer, config['data']['max_length']
    )
    eval_dataset = load_dataset(
        config['data']['dev_path'], tokenizer, config['data']['max_length']
    )

    # 训练参数
    print("\n[3/4] 配置训练参数...")
    training_args = TrainingArguments(
        output_dir=config['output']['checkpoint_dir'],
        num_train_epochs=int(config['training']['num_epochs']),
        per_device_train_batch_size=int(config['training']['batch_size']),
        per_device_eval_batch_size=int(config['training']['batch_size']),
        gradient_accumulation_steps=int(config['training']['gradient_accumulation_steps']),
        learning_rate=float(config['training']['learning_rate']),
        weight_decay=float(config['training']['weight_decay']),
        warmup_ratio=float(config['training']['warmup_ratio']),
        max_grad_norm=float(config['training']['max_grad_norm']),
        logging_dir=config['output']['log_dir'],
        logging_steps=int(config['training']['logging_steps']),
        save_steps=int(config['training']['save_steps']),
        eval_steps=int(config['training']['eval_steps']),
        eval_strategy="steps",
        save_strategy="steps",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        bf16=True,
        gradient_checkpointing=True,
        report_to="tensorboard",
        remove_unused_columns=False,
    )

    # 数据整理器
    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        padding=True,
        pad_to_multiple_of=8,
        label_pad_token_id=-100,
    )

    # 训练器
    trainer = ReverseKLDistillationTrainer(
        teacher_model=teacher_model,
        temperature=config['distillation']['temperature'],
        alpha=config['distillation']['alpha'],
        forward_weight=fw,
        reverse_weight=rw,
        model=student_model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        processing_class=tokenizer,
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
