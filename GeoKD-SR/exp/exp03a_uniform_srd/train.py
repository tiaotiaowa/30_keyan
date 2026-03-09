#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exp3a: B2+C1(Uniform) 训练脚本

空间关系蒸馏等权重基线
所有关系类型使用相同权重 (w=1.0)
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
    )
    for param in teacher.parameters():
        param.requires_grad = False
    teacher.eval()
    return teacher


def load_student_model(config: dict):
    model_name = config['model']['student']['name']
    model = AutoModelForCausalLM.from_pretrained(
        model_name, torch_dtype=torch.float16, device_map="auto", trust_remote_code=True,
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


def get_relation_type(question: str) -> str:
    """根据问题内容判断空间关系类型"""
    directional_keywords = ["东", "西", "南", "北", "方向", "左侧", "右侧", "上方", "下方"]
    topological_keywords = ["相邻", "包含", "相交", "相离", "重叠", "邻接", "内部", "外部"]
    metric_keywords = ["距离", "多远", "米", "公里", "千米"]
    composite_keywords = ["之间", "经过", "路径", "最短"]

    question_lower = question.lower()
    for kw in composite_keywords:
        if kw in question_lower:
            return "composite"
    for kw in directional_keywords:
        if kw in question_lower:
            return "directional"
    for kw in topological_keywords:
        if kw in question_lower:
            return "topological"
    for kw in metric_keywords:
        if kw in question_lower:
            return "metric"
    return "composite"


def get_uniform_weights() -> dict:
    """获取等权重配置"""
    return {
        "directional": 1.0,
        "topological": 1.0,
        "metric": 1.0,
        "composite": 1.0,
    }


def spatial_relation_distillation_loss(
    student_logits, teacher_logits, relation_type, temperature=2.0
):
    """计算空间关系蒸馏损失（等权重版本）"""
    p_teacher = F.softmax(teacher_logits / temperature, dim=-1)
    p_student = F.log_softmax(student_logits / temperature, dim=-1)
    kl_loss = F.kl_div(p_student, p_teacher, reduction='batchmean')

    # 等权重
    weights = get_uniform_weights()
    weight = weights.get(relation_type, 1.0)

    return kl_loss * (temperature ** 2) * weight


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


class SpatialRelationDistillationTrainer(Trainer):
    """带有空间关系蒸馏的训练器（等权重）"""

    def __init__(self, teacher_model, temperature=2.0, alpha=0.5, raw_data=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.teacher_model = teacher_model
        self.temperature = temperature
        self.alpha = alpha
        self.raw_data = raw_data or []

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        student_outputs = model(**inputs)
        student_logits = student_outputs.logits

        with torch.no_grad():
            teacher_outputs = self.teacher_model(**inputs)
            teacher_logits = teacher_outputs.logits

        # 获取关系类型（简化处理，默认使用composite）
        relation_type = "composite"
        if self.raw_data and len(self.raw_data) > 0:
            idx = inputs.get("input_ids", []).argmax().item() if "input_ids" in inputs else 0
            if idx < len(self.raw_data):
                relation_type = get_relation_type(self.raw_data[idx].get("question", ""))

        soft_loss = spatial_relation_distillation_loss(
            student_logits, teacher_logits, relation_type, self.temperature
        )

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
    parser = argparse.ArgumentParser(description="Exp3a: B2+C1(Uniform) 训练")
    parser.add_argument("--config", type=str, default="config.yaml")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume", type=str, default=None)
    args = parser.parse_args()

    work_dir = Path(__file__).parent
    os.chdir(work_dir)
    config = load_config(args.config)
    set_seed(args.seed)

    print("=" * 60)
    print("Exp3a: B2+C1(Uniform)（空间关系蒸馏等权重基线）")
    print("=" * 60)
    print(f"配置文件: {args.config}")
    print(f"教师模型: {config['model']['teacher']['name']} (4-bit量化)")
    print(f"学生模型: {config['model']['student']['name']}")
    print(f"权重类型: 等权重 (uniform)")
    print("=" * 60)

    print("\n[1/4] 加载模型...")
    teacher_model = load_teacher_model(config)
    student_model, tokenizer = load_student_model(config)

    print("\n[2/4] 加载数据集...")
    train_dataset, train_data = load_dataset(
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

    trainer = SpatialRelationDistillationTrainer(
        teacher_model=teacher_model,
        temperature=config['distillation']['temperature'],
        alpha=config['distillation']['alpha'],
        raw_data=train_data,
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
