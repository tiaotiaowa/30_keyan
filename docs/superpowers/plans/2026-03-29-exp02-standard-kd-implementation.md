# Exp02 Standard-KD 蒸馏实验实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Qwen2.5-7B→1.5B 标准知识蒸馏实验，包含训练、生成、评测完整流水线

**Architecture:** 在线蒸馏（教师4bit量化+学生LoRA同时加载A10），复用exp0两阶段评测框架保证结果可比性

**Tech Stack:** PyTorch,2.x, Transformers 4.48+, PEFT/LoRA, bitsandbytes 4bit量化

---

## File Structure

```
exp/exp02_standard_kd/
├── config.yaml              # [MODIFY] 7项参数修正
├── train.py                 # [MODIFY] 移除system prompt, fp16→bf16
├── stage1_generate.py       # [CREATE] LoRA模型加载 + exp0生成逻辑
├── stage1_config.yaml       # [CREATE] 生成配置(复用exp0模板)
├── stage2_evaluate.py       # [CREATE] 调用exp0评测框架
├── run.sh                   # [CREATE] 一键运行脚本
├── evaluate.py              # [KEEP] 旧版备用
└── README.md                # [UPDATE]
```

---

### Task 1: 修改 config.yaml（7项参数修正）

**Files:**
- Modify: `exp/exp02_standard_kd/config.yaml`

- [ ] **Step 1: 替换 config.yaml 全部内容**

```yaml
# 实验配置 - Exp2: B2-Standard-KD（通用蒸馏基线）
# Hinton 2015 经典KL蒸馏（Forward KL）
# 针对24GB显存优化配置

experiment:
  name: "exp02_standard_kd"
  description: "通用蒸馏基线：Hinton 2015经典KL蒸馏"
  seed: 42

model:
  # 教师模型: Qwen2.5-7B-Instruct (4-bit量化)
  teacher:
    enabled: true
    name: "/mnt/workspace/models/Qwen2.5-7B-Instruct"
    quantization: "4bit"
    device_map: "auto"

  # 学生模型: Qwen2.5-1.5B-Instruct
  student:
    name: "/mnt/workspace/models/Qwen2.5-1.5B-Instruct"
    lora:
      r: 16
      lora_alpha: 32
      lora_dropout: 0.05
      target_modules: ["q_proj", "k_proj", "v_proj", "o_proj"]
      bias: "none"
      task_type: "CAUSAL_LM"

training:
  learning_rate: 1e-4
  batch_size: 2  # 教师+学生同时加载A10 24GB
  gradient_accumulation_steps: 64  # effective batch=128
  num_epochs: 3
  warmup_ratio: 0.1
  weight_decay: 0.01
  max_grad_norm: 1.0
  logging_steps: 10
  save_steps: 200
  eval_steps: 200
  max_length: 1024

distillation:
  enabled: true
  method: "standard_kd"
  temperature: 2.0
  alpha: 0.5  # L_KD = α × L_soft + (1-α) × L_hard

data:
  train_path: "../../data/splits/train.jsonl"
  dev_path: "../../data/splits/dev.jsonl"
  test_path: "../../data/splits/test.jsonl"
  max_length: 1024

output:
  checkpoint_dir: "checkpoints/"
  log_dir: "logs/"
  result_dir: "results/"
```

- [ ] **Step 2: 验证YAML语法**

Run: `cd D:/30_keyan/GeoKD-SR && python -c "import yaml; yaml.safe_load(open('exp/exp02_standard_kd/config.yaml')); print('YAML OK')"`

Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
cd D:/30_keyan/GeoKD-SR
git add exp/exp02_standard_kd/config.yaml
git commit -m "fix(exp02): 修正config.yaml 7项参数 - 数据路径/LoRA/accum/bf16/save_steps"
```

---

### Task 2: 修改 train.py（移除system prompt + fp16→bf16）

**Files:**
- Modify: `exp/exp02_standard_kd/train.py`

- [ ] **Step 1: 修改 load_dataset 函数签名和内部逻辑，**

在 `load_dataset` 函数中，移除 `system_prompt` 参数，将 messages 构建从三条改为两条（无system角色）。

Find the (line ~135-143):
```python
def load_dataset(data_path: str, tokenizer, max_length: int = 1024, system_prompt: str = ""):
```

Replace with:
```python
def load_dataset(data_path: str, tokenizer, max_length: int = 1024):
```

Then find inside `prepare_sample` (line ~168-172):
```python
        # 构建 ChatML 格式消息
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer}
        ]
```

Replace with:
```python
        # 构建 ChatML 格式消息（无system prompt，对齐SFT训练格式）
        messages = [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer}
        ]
```

Then find user_messages construction (line ~183-186):
```python
        user_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]
```

Replace with:
```python
        user_messages = [
            {"role": "user", "content": question}
        ]
```

- [ ] **Step 2: 修改 main 函数 — 移除 system_prompt 获取逻辑**

Find (line ~337-341):
```python
    # 获取系统提示
    system_prompt = config.get('chat_template', {}).get(
        'system_prompt',
        "你是一个地理空间推理专家，擅长分析和解决空间关系问题。"
    )
```

Replace with:
```python
    # 不使用system prompt（对齐SFT训练格式）
```

Then find (line ~367):
```python
    train_dataset = load_dataset(
        config['data']['train_path'], tokenizer, config['data']['max_length'], system_prompt
    )
    eval_dataset = load_dataset(
        config['data']['dev_path'], tokenizer, config['data']['max_length'], system_prompt
    )
```

Replace with:
```python
    train_dataset = load_dataset(
        config['data']['train_path'], tokenizer, config['data']['max_length']
    )
    eval_dataset = load_dataset(
        config['data']['dev_path'], tokenizer, config['data']['max_length']
    )
```

- [ ] **Step 3: 修改 fp16→bf16**

Find (line ~393):
```python
        fp16=True,
```

Replace with:
```python
        bf16=True,
```

- [ ] **Step 4: 验证语法正确**

Run: `cd D:/30_keyan/GeoKD-SR && python -c "import py_compile; py_compile.compile('exp/exp02_standard_kd/train.py', doraise=True); print('Syntax OK')"`

Expected: `Syntax OK`

- [ ] **Step 5: Commit**

```bash
cd D:/30_keyan/GeoKD-SR
git add exp/exp02_standard_kd/train.py
git commit -m "fix(exp02): 移除system prompt，fp16改bf16，对齐SFT训练格式"
```

---

### Task 3: 创建 stage1_generate.py（LoRA模型生成脚本）

**Files:**
- Create: `exp/exp02_standard_kd/stage1_generate.py`

- [ ] **Step 1: 创建 stage1_generate.py**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exp02 Stage1: 加载LoRA微调后的模型，使用与exp0完全相同的prompt模板和生成参数生成预测结果
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

import torch
from tqdm import tqdm
import yaml

# 添加exp0生成模块路径
EXP0_STAGE1 = Path(__file__).parent.parent / "exp0" / "exp0" / "stage1_generation"
sys.path.insert(0, str(EXP0_STAGE1))

from model_loader import ModelLoader


def load_config(config_path: str) -> dict:
    """加载配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def generate_predictions(config: dict, checkpoint_path: str) -> List[Dict]:
    """
    加载base模型 + LoRA adapter，生成预测结果

    使用与exp0完全相同的prompt模板和生成参数
    """
    # 加载base模型
    model_config = config.get("model", {})
    base_name = model_config.get("base_name", model_config.get("name", ""))
    device = model_config.get("device", "cuda")
    dtype_str = model_config.get("dtype", "float16")
    dtype = torch.float16 if dtype_str == "float16" else torch.bfloat16

    print(f"加载base模型: {base_name}")
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(base_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        base_name,
        torch_dtype=dtype,
        device_map=device,
        trust_remote_code=True,
    )

    # 加载LoRA adapter并合并
    if checkpoint_path:
        print(f"加载LoRA adapter: {checkpoint_path}")
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, checkpoint_path)
        model = model.merge_and_unload()
        print("LoRA权重已合并")

    model.eval()

    # 加载测试数据
    data_config = config.get("data", {})
    test_path = data_config.get("input_file", data_config.get("test_file", ""))
    print(f"加载测试数据: {test_path}")

    test_data = []
    with open(test_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                test_data.append(json.loads(line))
    print(f"共 {len(test_data)} 条测试数据")

    # 获取prompt模板（与exp0完全一致）
    prompt_template = config.get("prompt_template",
        config.get("prompt_template", "问题：{question}\n答案："))

    # 生成参数
    gen_config = config.get("generation", {})

    predictions = []
    save_interval = config.get("logging", {}).get("save_interval", 50)
    output_file = data_config.get("output_file", "./outputs/predictions.jsonl")

    print("开始生成预测...")
    for i, item in enumerate(tqdm(test_data, desc="生成中")):
        question = item.get("question", "")
        reference = item.get("answer", "")

        if not question:
            continue

        # 使用与exp0相同的prompt格式
        prompt = prompt_template.format(question=question)

        # ChatML格式
        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        inputs = tokenizer(text, return_tensors="pt").to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=gen_config.get("max_new_tokens", 256),
                temperature=gen_config.get("temperature", 0.1),
                top_p=gen_config.get("top_p", 0.9),
                top_k=gen_config.get("top_k", 50),
                do_sample=gen_config.get("do_sample", True),
                repetition_penalty=gen_config.get("repetition_penalty", 1.1),
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )

        generated = tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True
        )

        result = {
            "id": item.get("id", f"item_{i}"),
            "question": item.get("question", ""),
            "reference": reference,
            "prediction": generated.strip(),
            "spatial_type": item.get("spatial_relation_type", "unknown"),
            "difficulty": item.get("difficulty", "unknown"),
        }
        predictions.append(result)

        if (i + 1) % save_interval == 0:
            _save_predictions(predictions, output_file)
            print(f"已处理 {i + 1}/{len(test_data)} 条")

    _save_predictions(predictions, output_file)
    print(f"生成完成！共 {len(predictions)} 条，保存至: {output_file}")
    return predictions


def _save_predictions(predictions: List[Dict], output_file: str):
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        for item in predictions:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Exp02 Stage1: 生成预测结果")
    parser.add_argument("--config", type=str, default="stage1_config.yaml")
    parser.add_argument("--checkpoint", type=str, required=True,
                        help="LoRA checkpoint路径")
    args = parser.parse_args()

    config = load_config(args.config)

    print("=" * 60)
    print("Exp02 Stage1: 生成预测结果")
    print("=" * 60)
    print(f"配置文件: {args.config}")
    print(f"LoRA checkpoint: {args.checkpoint}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    generate_predictions(config, args.checkpoint)

    print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证语法**

Run: `cd D:/30_keyan/GeoKD-SR && python -c "import py_compile; py_compile.compile('exp/exp02_standard_kd/stage1_generate.py', doraise=True); print('Syntax OK')"`

Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```bash
cd D:/30_keyan/GeoKD-SR
git add exp/exp02_standard_kd/stage1_generate.py
git commit -m "feat(exp02): 创建stage1_generate.py - LoRA模型加载+exp0生成框架"
```

---

### Task 4: 创建 stage1_config.yaml（生成配置）

**Files:**
- Create: `exp/exp02_standard_kd/stage1_config.yaml`

- [ ] **Step 1: 创建 stage1_config.yaml**

复用exp0的prompt模板和生成参数，添加LoRA路径配置：

```yaml
# Exp02 Stage1: 生成配置
# 复用exp0的prompt模板，确保评测完全可比

model:
  base_name: "/mnt/workspace/models/Qwen2.5-1.5B-Instruct"
  device: "cuda"
  dtype: "float16"

generation:
  max_new_tokens: 256
  temperature: 0.1
  top_p: 0.9
  top_k: 50
  do_sample: true
  repetition_penalty: 1.1

data:
  input_file: "../../data/splits/test.jsonl"
  output_file: "./outputs/predictions.jsonl"

# 与exp0完全相同的prompt模板
prompt_template: |
  你是一个地理空间推理专家。请根据问题给出准确、简洁的答案。

  问题: {question}

  请直接给出答案，不需要解释过程。答案格式要求：
  - 方向问题：直接说明方向，如"东南方向"
  - 距离问题：给出具体数值，如"约1200公里"
  - 拓扑问题：明确说明关系，如"是的，XX位于YY内部"
  - 复合问题：同时给出最终结果

  答案:

logging:
  save_interval: 50
```

- [ ] **Step 2: 验证YAML语法**

Run: `cd D:/30_keyan/GeoKD-SR && python -c "import yaml; yaml.safe_load(open('exp/exp02_standard_kd/stage1_config.yaml')); print('YAML OK')"`

Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
cd D:/30_keyan/GeoKD-SR
git add exp/exp02_standard_kd/stage1_config.yaml
git commit -m "feat(exp02): 创建stage1_config.yaml - 复用exp0生成配置"
```

---

### Task 5: 创建 stage2_evaluate.py（评测脚本）

**Files:**
- Create: `exp/exp02_standard_kd/stage2_evaluate.py`

- [ ] **Step 1: 创建 stage2_evaluate.py**

直接调用exp0的评测模块，确保评测完全一致：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exp02 Stage2: 调用exp0统一评测框架计算指标
确保与基线(23.16%)和SFT(22.06%)完全可比
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

import yaml

# 添加exp0评测模块路径
EXP0_STAGE2 = Path(__file__).parent.parent / "exp0" / "exp0" / "stage2_evaluation"
sys.path.insert(0, str(EXP0_STAGE2))

from evaluate import Evaluator


def main():
    parser = argparse.ArgumentParser(description="Exp02 Stage2: 评测")
    parser.add_argument("--predictions", type=str, default="./outputs/predictions.jsonl",
                        help="predictions.jsonl路径")
    parser.add_argument("--eval-config", type=str, default=None,
                        help="评测配置文件（默认使用exp0的eval_config.yaml）")
    parser.add_argument("--output", type=str, default="./results/", help="输出目录")
    args = parser.parse_args()

    # 加载评测配置（使用exp0的统一配置）
    if args.eval_config is None:
        args.eval_config = str(EXP0_STAGE2 / "config" / "eval_config.yaml")

    with open(args.eval_config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 覆盖路径
    config["data"]["predictions_file"] = args.predictions
    config["data"]["output_dir"] = args.output

    print("=" * 60)
    print("Exp02 Stage2: 评测")
    print("=" * 60)
    print(f"预测文件: {args.predictions}")
    print(f"评测配置: {args.eval_config}")
    print(f"输出目录: {args.output}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 创建评测器并运行
    evaluator = Evaluator(config)
    evaluator.load_predictions(args.predictions)
    results = evaluator.run_evaluation()
    json_path, report_path = evaluator.save_results(results, args.output)

    print(f"\n评测完成！")
    print(f"JSON结果: {json_path}")
    print(f"报告: {report_path}")
    print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 打印关键指标
    det = results.get("deterministic", {})
    acc = det.get("accuracy", {}).get("overall", 0)
    print(f"\nOverall Accuracy: {acc:.4f} ({acc*100:.2f}%)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证语法**

Run: `cd D:/30_keyan/GeoKD-SR && python -c "import py_compile; py_compile.compile('exp/exp02_standard_kd/stage2_evaluate.py', doraise=True); print('Syntax OK')"`

Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```bash
cd D:/30_keyan/GeoKD-SR
git add exp/exp02_standard_kd/stage2_evaluate.py
git commit -m "feat(exp02): 创建stage2_evaluate.py - 调用exp0统一评测框架"
```

---

### Task 6: 创建 run.sh（一键运行脚本）

**Files:**
- Create: `exp/exp02_standard_kd/run.sh`

- [ ] **Step 1: 创建 run.sh**

```bash
#!/bin/bash
set -e

echo "=========================================="
echo "  Exp02: Standard-KD（标准知识蒸馏基线）"
echo "=========================================="
echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 配置
SEED=${1:-42}
CHECKPOINT_DIR="checkpoints"
OUTPUT_DIR="outputs"
RESULT_DIR="results"

# Step 1: 训练
echo "[1/3] 开始蒸馏训练 (seed=${SEED})..."
python train.py --config config.yaml --seed ${SEED}
echo "训练完成: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Step 2: 生成预测
echo "[2/3] 生成预测结果..."
python stage1_generate.py --config stage1_config.yaml \
    --checkpoint ${CHECKPOINT_DIR}/final_model
echo "生成完成: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Step 3: 评测
echo "[3/3] 评测..."
python stage2_evaluate.py \
    --predictions ${OUTPUT_DIR}/predictions.jsonl \
    --output ${RESULT_DIR}/
echo ""

echo "=========================================="
echo "  全部完成！"
echo "  训练checkpoint: ${CHECKPOINT_DIR}/"
echo "  预测结果: ${OUTPUT_DIR}/predictions.jsonl"
echo "  评测报告: ${RESULT_DIR}/report.md"
echo "  完成时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
```

- [ ] **Step 2: 添加执行权限**

Run: `chmod +x D:/30_keyan/GeoKD-SR/exp/exp02_standard_kd/run.sh`

- [ ] **Step 3: Commit**

```bash
cd D:/30_keyan/GeoKD-SR
git add exp/exp02_standard_kd/run.sh
git commit -m "feat(exp02): 创建run.sh一键运行脚本"
```

---

### Task 7: Dry-run 验证（本地语法和导入检查）

**Files:** 无修改，仅验证

- [ ] **Step 1: 验证所有Python文件语法**

Run:
```bash
cd D:/30_keyan/GeoKD-SR
python -c "
import py_compile
files = [
    'exp/exp02_standard_kd/train.py',
    'exp/exp02_standard_kd/stage1_generate.py',
    'exp/exp02_standard_kd/stage2_evaluate.py',
]
for f in files:
    py_compile.compile(f, doraise=True)
    print(f'  OK: {f}')
print('All syntax checks passed')
"
```

Expected: 所有文件显示OK

- [ ] **Step 2: 验证关键导入链**

```bash
cd D:/30_keyan/GeoKD-SR
python -c "
import yaml, json, torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer, DataCollatorForSeq2Seq
from peft import LoraConfig, get_peft_model, TaskType, PeftModel
from datasets import Dataset
import torch.nn.functional as F
print('All imports OK')
"
```

Expected: `All imports OK`

- [ ] **Step 3: 验证数据加载**

```bash
cd D:/30_keyan/GeoKD-SR/exp/exp02_standard_kd
python -c "
import json
for split in ['train', 'dev', 'test']:
    path = f'../../data/splits/{split}.jsonl'
    with open(path, 'r', encoding='utf-8') as f:
        data = [json.loads(l) for l in f if l.strip()]
    # 验证字段
    item = data[0]
    assert 'question' in item, f'{split}: missing question'
    assert 'answer' in item, f'{split}: missing answer'
    assert 'spatial_relation_type' in item, f'{split}: missing spatial_relation_type'
    print(f'{split}: {len(data)} samples, fields OK')
print('Data validation passed')
"
```

Expected: train: 9463, dev: 1124, test: 1183, all fields OK

- [ ] **Step 4: 验证config.yaml中的路径解析**

```bash
cd D:/30_keyan/GeoKD-SR/exp/exp02_standard_kd
python -c "
import yaml
config = yaml.safe_load(open('config.yaml'))
import os
for key in ['train_path', 'dev_path', 'test_path']:
    path = config['data'][key]
    assert os.path.exists(path), f'Path not found: {path}'
    print(f'  {key}: {path} -> EXISTS')
print('Config paths OK')
"
```

Expected: 所有路径EXISTS

- [ ] **Step 5: 提交最终验证**

```bash
cd D:/30_keyan/GeoKD-SR
git status
```

确认所有文件已提交，无遗漏修改。

---

## 自检清单

**1. 设计文档覆盖检查：**
- config.yaml 7项修改 → Task 1 ✓
- train.py system prompt移除 → Task 2 ✓
- train.py fp16→bf16 → Task 2 ✓
- stage1_generate.py 新建 → Task 3 ✓
- stage1_config.yaml 新建 → Task 4 ✓
- stage2_evaluate.py 新建 → Task 5 ✓
- run.sh 新建 → Task 6 ✓
- 验证方案 → Task 7 ✓

**2. 占位符检查：** 无 TBD/TODO/待定项，所有步骤包含完整代码。

**3. 类型一致性：**
- `load_dataset` 签名统一无 system_prompt ✓
- config.yaml 中 LoRA 参数名 (r, lora_alpha, lora_dropout) 与 train.py 引用一致 ✓
- stage1_generate.py 输出的 predictions.jsonl 字段与 stage2_evaluate.py 读取格式一致 ✓

**4. 潜在风险提示：**
- Task 3 stage1_generate.py 中需要 peft 库（PAI环境已安装）
- Task 5 stage2_evaluate.py 依赖 exp0 评测模块路径正确（已通过 sys.path.insert 配置）
- 数据量 9463/128=74步/epoch × 3=222步，每步含教师推理约5-8秒，总训练时间15-30分钟
