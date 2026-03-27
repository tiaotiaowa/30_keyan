#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exp9: GeoKD-SR(Full) 训练脚本

完整方法：结合所有蒸馏组件
- C1: 空间关系蒸馏（可学习权重）
- C2: 思维链蒸馏
- C3: 逆向KL蒸馏
- C4: 自蒸馏
- C5: 注意力蒸馏
- C6: 渐进式蒸馏
"""

import os
import sys
import yaml
import argparse
import torch
import torch.nn.functional as F
import torch.nn as nn
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


class LearnableRelationWeights(nn.Module):
    """可学习的关系类型权重"""

    def __init__(self, initial_weights: dict):
        super().__init__()
        self.relation_types = ["directional", "topological", "metric", "composite"]
        init_values = torch.tensor([
            initial_weights.get(rt, 1.0) for rt in self.relation_types
        ], dtype=torch.float32)
        self.log_weights = nn.Parameter(torch.log(init_values))

    def forward(self):
        return F.softmax(self.log_weights, dim=0)

    def get_weight(self, relation_type: str) -> torch.Tensor:
        weights = self.forward()
        if relation_type in self.relation_types:
            return weights[self.relation_types.index(relation_type)]
        return weights.mean()


class EMA:
    """指数移动平均（用于自蒸馏）"""

    def __init__(self, model, decay=0.999):
        self.model = model
        self.decay = decay
        self.shadow = {}
        self.backup = {}
        for name, param in model.named_parameters():
            if param.requires_grad:
                self.shadow[name] = param.data.clone()

    def update(self):
        for name, param in self.model.named_parameters():
            if param.requires_grad:
                self.shadow[name] = self.decay * self.shadow[name] + (1 - self.decay) * param.data.clone()

    def apply_shadow(self):
        for name, param in self.model.named_parameters():
            if param.requires_grad:
                self.backup[name] = param.data.clone()
                param.data = self.shadow[name]

    def restore(self):
        for name, param in self.model.named_parameters():
            if param.requires_grad:
                param.data = self.backup[name]
        self.backup = {}


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
        output_attentions=True, output_hidden_states=True,
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
    directional_keywords = ["东", "西", "南", "北", "方向", "左侧", "右侧"]
    topological_keywords = ["相邻", "包含", "相交", "相离", "重叠", "邻接"]
    metric_keywords = ["距离", "多远", "米", "公里", "千米"]
    composite_keywords = ["之间", "经过", "路径", "最短"]

    for kw in composite_keywords:
        if kw in question: return "composite"
    for kw in directional_keywords:
        if kw in question: return "directional"
    for kw in topological_keywords:
        if kw in question: return "topological"
    for kw in metric_keywords:
        if kw in question: return "metric"
    return "composite"


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


class GeoKDSRTrainer(Trainer):
    """GeoKD-SR完整训练器"""

    def __init__(self, teacher_model, config, raw_data=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.teacher_model = teacher_model
        self.config = config
        self.raw_data = raw_data or []
        self.components = config['distillation']['components']

        # 初始化可学习权重
        if self.components['spatial_relation']['enabled']:
            self.relation_weights = LearnableRelationWeights(
                self.components['spatial_relation']['initial_weights']
            )
            self.weight_optimizer = torch.optim.Adam(
                [self.relation_weights.log_weights],
                lr=self.components['spatial_relation']['weight_lr']
            )

        # 初始化EMA
        if self.components['self_distillation']['enabled']:
            self.ema = EMA(self.model, decay=config['model']['teacher']['self_distillation']['ema_decay'])

        # 渐进式蒸馏状态
        self.current_stage_idx = 0

    def get_temperature_multiplier(self, epoch):
        """获取渐进式温度乘数"""
        if not self.components['progressive']['enabled']:
            return 1.0

        stages = self.components['progressive']['stages']
        for i, stage in enumerate(stages):
            if stage['epochs'][0] <= epoch < stage['epochs'][1]:
                self.current_stage_idx = i
                return stage['temperature_multiplier']
        return 1.0

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        # 获取当前epoch
        epoch = self.state.epoch if hasattr(self, 'state') and self.state else 0
        temp_multiplier = self.get_temperature_multiplier(epoch)
        base_temp = self.config['distillation']['temperature']
        temperature = base_temp * temp_multiplier

        # 学生模型前向传播
        student_outputs = model(**inputs, output_attentions=True, output_hidden_states=True)
        student_logits = student_outputs.logits

        # 教师模型前向传播
        with torch.no_grad():
            teacher_outputs = self.teacher_model(**inputs, output_attentions=True, output_hidden_states=True)
            teacher_logits = teacher_outputs.logits

        total_loss = torch.tensor(0.0, device=student_logits.device)

        # C1: 空间关系蒸馏
        if self.components['spatial_relation']['enabled']:
            relation_type = "composite"
            if self.raw_data:
                idx = 0
                if idx < len(self.raw_data):
                    relation_type = get_relation_type(self.raw_data[idx].get("question", ""))

            weight = self.relation_weights.get_weight(relation_type)
            p_teacher = F.softmax(teacher_logits / temperature, dim=-1)
            p_student = F.log_softmax(student_logits / temperature, dim=-1)
            srd_loss = F.kl_div(p_student, p_teacher, reduction='batchmean') * (temperature ** 2) * weight
            total_loss += self.components['spatial_relation']['loss_weight'] * srd_loss

        # C2: 思维链蒸馏（简化为整体KL）
        if self.components['chain_of_thought']['enabled']:
            cot_loss = F.kl_div(
                F.log_softmax(student_logits / temperature, dim=-1),
                F.softmax(teacher_logits / temperature, dim=-1),
                reduction='batchmean'
            ) * (temperature ** 2)
            total_loss += self.components['chain_of_thought']['loss_weight'] * cot_loss

        # C3: 逆向KL蒸馏
        if self.components['reverse_kl']['enabled']:
            fw = self.components['reverse_kl']['forward_weight']
            rw = self.components['reverse_kl']['reverse_weight']
            fkl = F.kl_div(
                F.log_softmax(student_logits / temperature, dim=-1),
                F.softmax(teacher_logits / temperature, dim=-1),
                reduction='batchmean'
            )
            rkl = F.kl_div(
                F.log_softmax(teacher_logits / temperature, dim=-1),
                F.softmax(student_logits / temperature, dim=-1),
                reduction='batchmean'
            )
            rkl_loss = (fw * fkl + rw * rkl) * (temperature ** 2)
            total_loss += self.components['reverse_kl']['loss_weight'] * rkl_loss

        # C4: 自蒸馏
        if self.components['self_distillation']['enabled']:
            self.ema.apply_shadow()
            ema_outputs = model(**inputs)
            ema_logits = ema_outputs.logits
            self.ema.restore()

            self_loss = F.kl_div(
                F.log_softmax(student_logits / temperature, dim=-1),
                F.softmax(ema_logits / temperature, dim=-1),
                reduction='batchmean'
            ) * (temperature ** 2)
            total_loss += self.components['self_distillation']['loss_weight'] * self_loss

        # C5: 注意力蒸馏
        if self.components['attention']['enabled']:
            s_attn = student_outputs.attentions[-1] if student_outputs.attentions else None
            t_attn = teacher_outputs.attentions[-1] if teacher_outputs.attentions else None
            if s_attn is not None and t_attn is not None:
                s_attn_norm = F.normalize(s_attn.float(), dim=-1)
                t_attn_norm = F.normalize(t_attn.float(), dim=-1)
                attn_loss = F.mse_loss(s_attn_norm, t_attn_norm)
                total_loss += self.components['attention']['loss_weight'] * attn_loss

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
            alpha = self.config['distillation']['alpha']
            total_loss = alpha * total_loss + (1 - alpha) * hard_loss

        return (total_loss, student_outputs) if return_outputs else total_loss

    def training_step(self, model, inputs):
        loss = super().training_step(model, inputs)

        # 更新可学习权重
        if self.components['spatial_relation']['enabled']:
            self.weight_optimizer.step()
            self.weight_optimizer.zero_grad()

        # 更新EMA
        if self.components['self_distillation']['enabled']:
            self.ema.update()

        return loss


def main():
    parser = argparse.ArgumentParser(description="Exp9: GeoKD-SR(Full) 训练")
    parser.add_argument("--config", type=str, default="config.yaml")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume", type=str, default=None)
    args = parser.parse_args()

    work_dir = Path(__file__).parent
    os.chdir(work_dir)
    config = load_config(args.config)
    set_seed(args.seed)

    print("=" * 60)
    print("Exp9: GeoKD-SR(Full)（完整方法）")
    print("=" * 60)
    print(f"配置文件: {args.config}")
    print(f"教师模型: {config['model']['teacher']['name']} (4-bit量化)")
    print(f"学生模型: {config['model']['student']['name']}")
    print("\n启用的组件:")
    for name, comp in config['distillation']['components'].items():
        status = "✓" if comp['enabled'] else "✗"
        print(f"  {status} {name}")
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

    trainer = GeoKDSRTrainer(
        teacher_model=teacher_model,
        config=config,
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

    # 保存最终模型和学习的权重
    final_model_path = Path(config['output']['checkpoint_dir']) / "final_model"
    trainer.save_model(str(final_model_path))
    tokenizer.save_pretrained(str(final_model_path))

    # 保存学习到的空间关系权重
    if config['distillation']['components']['spatial_relation']['enabled']:
        import json
        weights = trainer.relation_weights.forward()
        learned_weights = {
            "directional": weights[0].item(),
            "topological": weights[1].item(),
            "metric": weights[2].item(),
            "composite": weights[3].item(),
        }
        with open(final_model_path / "learned_weights.json", "w") as f:
            json.dump(learned_weights, f, indent=2)
        print(f"\n学习到的空间关系权重: {learned_weights}")

    print(f"\n训练完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"最终模型保存至: {final_model_path}")


if __name__ == "__main__":
    main()
