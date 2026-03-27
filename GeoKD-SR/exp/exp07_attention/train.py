#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exp7: B2+C5 训练脚本

空间关系注意力蒸馏
蒸馏注意力模式以传递空间关系推理能力
L_attn = MSE(A_S, A_T) + MSE(H_S, H_T)
"""

import os
import sys
import yaml
import argparse
import torch
import torch.nn.functional as F
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer,
)
from peft import LoraConfig, get_peft_model, TaskType
from datasets import Dataset
import numpy as np


def set_seed(seed: int):
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_teacher_model(config: dict):
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
        output_attentions=True,
        output_hidden_states=True,
    )
    for param in teacher.parameters():
        param.requires_grad = False
    teacher.eval()
    return teacher


def load_student_model(config: dict):
    model_name = config['model']['student']['name']
    model = AutoModelForCausalLM.from_pretrained(
        model_name, torch_dtype=torch.float16, device_map="auto", trust_remote_code=True,
        output_attentions=True,
        output_hidden_states=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
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


def attention_distillation_loss(student_attentions, teacher_attentions):
    """
    注意力蒸馏损失
    计算学生和教师注意力矩阵的MSE
    """
    total_loss = 0.0
    num_layers = min(len(student_attentions), len(teacher_attentions))

    for i in range(num_layers):
        s_attn = student_attentions[i]
        t_attn = teacher_attentions[i]

        # 归一化注意力
        s_attn = F.normalize(s_attn.float(), dim=-1)
        t_attn = F.normalize(t_attn.float(), dim=-1)

        # MSE损失
        loss = F.mse_loss(s_attn, t_attn)
        total_loss += loss

    return total_loss / num_layers if num_layers > 0 else torch.tensor(0.0)


def hidden_state_loss(student_hidden, teacher_hidden):
    """
    隐藏状态蒸馏损失
    """
    total_loss = 0.0
    num_layers = min(len(student_hidden), len(teacher_hidden))

    for i in range(num_layers):
        s_hidden = student_hidden[i]
        t_hidden = teacher_hidden[i]

        # 处理维度不匹配
        if s_hidden.size(-1) != t_hidden.size(-1):
            # 投影到相同维度
            t_hidden = F.linear(t_hidden, torch.randn(s_hidden.size(-1), t_hidden.size(-1)).to(t_hidden.device))

        loss = F.mse_loss(s_hidden.float(), t_hidden.float())
        total_loss += loss

    return total_loss / num_layers if num_layers > 0 else torch.tensor(0.0)


def load_dataset(data_path: str, tokenizer, max_length: int = 2048):
    data = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = eval(line.strip()) if line.strip().startswith("{") else {"text": line.strip()}
                data.append(item)

    def tokenize_function(example):
        question = example.get("question", "")
        answer = example.get("answer", "")
        text = f"问题：{question}\n答案：{answer}"
        return tokenizer(text, truncation=True, max_length=max_length, padding="max_length", return_tensors="pt")

    dataset = Dataset.from_list(data)
    tokenized_dataset = dataset.map(tokenize_function, batched=False)
    return tokenized_dataset, data


class AttentionDistillationTrainer(Trainer):
    """带有注意力蒸馏的训练器"""

    def __init__(self, teacher_model, temperature=2.0, alpha=0.5,
                 attention_weight=0.3, hidden_weight=0.2, logit_weight=0.5, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.teacher_model = teacher_model
        self.temperature = temperature
        self.alpha = alpha
        self.attention_weight = attention_weight
        self.hidden_weight = hidden_weight
        self.logit_weight = logit_weight

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        # 学生模型前向传播（带注意力输出）
        student_outputs = model(**inputs, output_attentions=True, output_hidden_states=True)
        student_logits = student_outputs.logits
        student_attentions = student_outputs.attentions
        student_hidden = student_outputs.hidden_states

        # 教师模型前向传播
        with torch.no_grad():
            teacher_outputs = self.teacher_model(**inputs, output_attentions=True, output_hidden_states=True)
            teacher_logits = teacher_outputs.logits
            teacher_attentions = teacher_outputs.attentions
            teacher_hidden = teacher_outputs.hidden_states

        # 1. Logits蒸馏损失
        p_teacher = F.softmax(teacher_logits / self.temperature, dim=-1)
        p_student = F.log_softmax(student_logits / self.temperature, dim=-1)
        logit_loss = F.kl_div(p_student, p_teacher, reduction='batchmean') * (self.temperature ** 2)

        # 2. 注意力蒸馏损失
        attn_loss = attention_distillation_loss(student_attentions, teacher_attentions)

        # 3. 隐藏状态蒸馏损失
        hidden_loss = hidden_state_loss(student_hidden, teacher_hidden)

        # 组合蒸馏损失
        soft_loss = (
            self.logit_weight * logit_loss +
            self.attention_weight * attn_loss +
            self.hidden_weight * hidden_loss
        )

        # 硬标签损失
        labels = inputs.get("labels")
        if labels is not None:
            shift_logits = student_logits[..., :-1, :].contiguous()
            shift_labels = labels[..., 1:].contiguous()
            hard_loss = F.cross_entropy(
                shift_logits.view(-1, shift_logits.size(-1)),
                shift_labels.view(-1),
                ignore_index=-100
            )
        else:
            hard_loss = torch.tensor(0.0, device=student_logits.device)

        total_loss = self.alpha * soft_loss + (1 - self.alpha) * hard_loss
        return (total_loss, student_outputs) if return_outputs else total_loss


def main():
    parser = argparse.ArgumentParser(description="Exp7: B2+C5（注意力蒸馏）训练")
    parser.add_argument("--config", type=str, default="config.yaml")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume", type=str, default=None)
    args = parser.parse_args()

    work_dir = Path(__file__).parent
    os.chdir(work_dir)
    config = load_config(args.config)
    set_seed(args.seed)

    print("=" * 60)
    print("Exp7: B2+C5（空间关系注意力蒸馏）")
    print("=" * 60)
    print(f"配置文件: {args.config}")
    print(f"教师模型: {config['model']['teacher']['name']} (4-bit量化)")
    print(f"学生模型: {config['model']['student']['name']}")
    print(f"注意力权重: {config['distillation']['attention']['attention_weight']}")
    print(f"隐藏状态权重: {config['distillation']['attention']['hidden_weight']}")
    print("=" * 60)

    print("\n[1/4] 加载模型...")
    teacher_model = load_teacher_model(config)
    student_model, tokenizer = load_student_model(config)

    print("\n[2/4] 加载数据集...")
    train_dataset, _ = load_dataset(
        config['data']['train_path'], tokenizer, config['data']['max_length']
    )
    eval_dataset, _ = load_dataset(
        config['data']['dev_path'], tokenizer, config['data']['max_length']
    )

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
    )

    trainer = AttentionDistillationTrainer(
        teacher_model=teacher_model,
        temperature=config['distillation']['temperature'],
        alpha=config['distillation']['alpha'],
        attention_weight=config['distillation']['attention']['attention_weight'],
        hidden_weight=config['distillation']['attention']['hidden_weight'],
        logit_weight=config['distillation']['attention']['logit_weight'],
        model=student_model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        tokenizer=tokenizer,
    )

    print("\n[4/4] 开始训练...")
    print(f"训练开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if args.resume:
        trainer.train(resume_from_checkpoint=args.resume)
    else:
        trainer.train()

    final_model_path = Path(config['output']['checkpoint_dir']) / "final_model"
    trainer.save_model(str(final_model_path))
    tokenizer.save_pretrained(str(final_model_path))

    print(f"\n训练完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"最终模型保存至: {final_model_path}")


if __name__ == "__main__":
    main()
