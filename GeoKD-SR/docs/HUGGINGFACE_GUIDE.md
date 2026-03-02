# HuggingFace 技术栈使用指南

## 📚 概述

本文档介绍如何使用HuggingFace技术栈下载和使用Qwen2.5模型进行GeoKD-SR项目。

---

## 🔧 环境配置

### 1. 安装HuggingFace依赖

```bash
pip install transformers>=4.36.0
pip install huggingface_hub>=0.20.0
pip install torch>=2.1.0
pip install accelerate
pip install datasets
```

或使用requirements文件：

```bash
pip install -r requirements.txt
```

### 2. 配置HuggingFace（可选）

如果需要访问私有模型或使用更多功能：

```bash
# 登录HuggingFace（访问私有模型时需要）
huggingface-cli login
```

或使用环境变量：

```bash
export HF_TOKEN=your_token_here
```

### 3. 配置镜像加速（国内用户）

```bash
# Linux/Mac
export HF_ENDPOINT=https://hf-mirror.com

# Windows PowerShell
$env:HF_ENDPOINT="https://hf-mirror.com"

# Windows CMD
set HF_ENDPOINT=https://hf-mirror.com
```

---

## 📥 下载模型

### 方法1: 使用下载脚本（推荐）

```bash
cd D:\30_keyan\GeoKD-SR\scripts
python download_with_hf.py
```

**功能特点**：
- 交互式选择模型
- 自动验证完整性
- 使用HF缓存系统
- 支持断点续传
- 详细的进度显示

### 方法2: 使用Python代码

```python
from huggingface_hub import snapshot_download

# 下载模型
model_path = snapshot_download(
    repo_id="Qwen/Qwen2.5-7B-Instruct",
    local_dir="./models/Qwen2.5-7B-Instruct",
    local_dir_use_symlinks=False,
    resume_download=True
)

print(f"模型已下载到: {model_path}")
```

### 方法3: 使用Transformers自动下载

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

# 首次使用时会自动下载
model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-7B-Instruct",
    trust_remote_code=True
)
tokenizer = AutoTokenizer.from_pretrained(
    "Qwen/Qwen2.5-7B-Instruct",
    trust_remote_code=True
)
```

---

## 💻 使用模型

### 基础使用

```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# 1. 加载模型
model_path = "D:/30_keyan/GeoKD-SR/models/Qwen2.5-7B-Instruct"

tokenizer = AutoTokenizer.from_pretrained(
    model_path,
    trust_remote_code=True
)

model = AutoModelForCausalLM.from_pretrained(
    model_path,
    torch_dtype=torch.float16,
    device_map="auto",
    trust_remote_code=True
)

# 2. 准备输入
messages = [
    {"role": "user", "content": "北京在上海的什么方向？"}
]

# 3. 应用聊天模板
text = tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True
)

# 4. 生成回答
model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

with torch.no_grad():
    outputs = model.generate(
        **model_inputs,
        max_new_tokens=200,
        do_sample=True,
        temperature=0.7,
        top_p=0.9
    )

# 5. 解码输出
response = tokenizer.decode(outputs[0], skip_special_tokens=True)
print(response)
```

### 知识蒸馏场景

```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# 加载教师模型
teacher_path = "models/Qwen2.5-7B-Instruct"
teacher_model = AutoModelForCausalLM.from_pretrained(
    teacher_path,
    torch_dtype=torch.float16,
    device_map="auto",
    trust_remote_code=True
)
teacher_tokenizer = AutoTokenizer.from_pretrained(
    teacher_path,
    trust_remote_code=True
)

# 加载学生模型
student_path = "models/Qwen2.5-1.5B-Instruct"
student_model = AutoModelForCausalLM.from_pretrained(
    student_path,
    torch_dtype=torch.float16,
    device_map="auto",
    trust_remote_code=True
)
student_tokenizer = AutoTokenizer.from_pretrained(
    student_path,
    trust_remote_code=True
)

# 准备输入
question = "北京在上海的什么方向？"
messages = [{"role": "user", "content": question}]
text = student_tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True
)
inputs = student_tokenizer([text], return_tensors="pt").to(student_model.device)

# 教师模型推理（生成软标签）
with torch.no_grad():
    teacher_outputs = teacher_model(**inputs)
    teacher_logits = teacher_outputs.logits

# 学生模型推理
with torch.no_grad():
    student_outputs = student_model(**inputs)
    student_logits = student_outputs.logits

# 计算KL散度损失
temperature = 2.0
kl_loss = torch.nn.KLDivLoss(reduction="batchmean")(
    torch.log_softmax(student_logits / temperature, dim=-1),
    torch.softmax(teacher_logits / temperature, dim=-1)
) * (temperature ** 2)

print(f"KL散度损失: {kl_loss.item():.4f}")
```

### 批量处理

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from torch.utils.data import DataLoader
from tqdm import tqdm

# 加载模型
model_path = "models/Qwen2.5-1.5B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    device_map="auto",
    trust_remote_code=True
)

# 准备数据
questions = [
    "北京在上海的什么方向？",
    "长江流经哪些省份？",
    "从北京到广州的距离大约是多少？",
]

# 批量处理
batch_size = 4
dataloader = DataLoader(questions, batch_size=batch_size, shuffle=False)

model.eval()
responses = []

with torch.no_grad():
    for batch in dataloader:
        # 应用聊天模板
        messages_list = [[{"role": "user", "content": q}] for q in batch]
        texts = [
            tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            for messages in messages_list
        ]

        # Tokenize
        inputs = tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt"
        ).to(model.device)

        # 生成
        outputs = model.generate(
            **inputs,
            max_new_tokens=200,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id
        )

        # 解码
        batch_responses = tokenizer.batch_decode(
            outputs,
            skip_special_tokens=True
        )
        responses.extend(batch_responses)

# 打印结果
for question, response in zip(questions, responses):
    print(f"Q: {question}")
    print(f"A: {response}\n")
```

---

## 🎯 高级用法

### 1. 使用Accelerate进行分布式训练

```python
from accelerate import Accelerator
from transformers import AutoModelForCausalLM, AutoTokenizer, get_linear_schedule_with_warmup
from torch.utils.data import DataLoader
from torch.optim import AdamW

# 初始化accelerator
accelerator = Accelerator()
device = accelerator.device

# 加载模型
model = AutoModelForCausalLM.from_pretrained(
    "models/Qwen2.5-1.5B-Instruct",
    trust_remote_code=True
)
tokenizer = AutoTokenizer.from_pretrained(
    "models/Qwen2.5-1.5B-Instruct",
    trust_remote_code=True
)

# 准备数据和优化器
train_dataloader = DataLoader(train_dataset, batch_size=8, shuffle=True)
optimizer = AdamW(model.parameters(), lr=1e-4)

# 使用accelerator准备
model, optimizer, train_dataloader = accelerator.prepare(
    model, optimizer, train_dataloader
)

# 训练循环
model.train()
for epoch in range(num_epochs):
    for batch in train_dataloader:
        outputs = model(**batch)
        loss = outputs.loss

        accelerator.backward(loss)
        optimizer.step()
        optimizer.zero_grad()
```

### 2. 使用PEFT进行高效微调

```python
from peft import LoraConfig, get_peft_model, TaskType
from transformers import AutoModelForCausalLM

# 加载基础模型
model = AutoModelForCausalLM.from_pretrained(
    "models/Qwen2.5-1.5B-Instruct",
    trust_remote_code=True
)

# 配置LoRA
lora_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    inference_mode=False,
    r=8,
    lora_alpha=32,
    lora_dropout=0.1,
    target_modules=["q_proj", "v_proj"]
)

# 应用LoRA
model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

# 训练（只训练LoRA参数）
# ... 标准训练流程
```

### 3. 模型量化

```python
from transformers import AutoModelForCausalLM, BitsAndBytesConfig

# 配置4-bit量化
quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4"
)

# 加载量化模型
model = AutoModelForCausalLM.from_pretrained(
    "models/Qwen2.5-7B-Instruct",
    quantization_config=quantization_config,
    device_map="auto",
    trust_remote_code=True
)

# 使用方式相同，但显存占用大幅降低
```

---

## 📊 性能优化

### 1. 使用Flash Attention

```python
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    use_flash_attention_2=True,  # 需要安装flash-attn
    torch_dtype=torch.float16,
    device_map="auto",
    trust_remote_code=True
)
```

### 2. 混合精度训练

```python
from accelerate import Accelerator

accelerator = Accelerator(mixed_precision="fp16")
model, optimizer, dataloader = accelerator.prepare(model, optimizer, dataloader)
```

### 3. 梯度检查点

```python
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    gradient_checkpointing=True,
    use_cache=False,  # 推理时设为True
    trust_remote_code=True
)
```

---

## 🔍 故障排除

### 问题1: 下载速度慢

**解决方案**：
```bash
# 使用镜像
export HF_ENDPOINT=https://hf-mirror.com
python download_with_hf.py
```

### 问题2: OOM (内存不足)

**解决方案**：
```python
# 方案1: 使用量化
quantization_config = BitsAndBytesConfig(load_in_8bit=True)
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    quantization_config=quantization_config,
    device_map="auto"
)

# 方案2: 减小批次大小
batch_size = 1  # 或使用梯度累积

# 方案3: 使用CPU
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    torch_dtype=torch.float32,
    device_map="cpu"
)
```

### 问题3: 导入错误

**解决方案**：
```bash
# 重新安装transformers
pip install --upgrade transformers

# 清理缓存
pip cache purge
```

---

## 📚 参考资料

- **HuggingFace文档**: https://huggingface.co/docs
- **Transformers**: https://huggingface.co/docs/transformers/
- **Accelerate**: https://huggingface.co/docs/accelerate/
- **PEFT**: https://huggingface.co/docs/peft/
- **Qwen模型**: https://huggingface.co/Qwen

---

**更新日期**: 2026-03-01
**版本**: v1.0
