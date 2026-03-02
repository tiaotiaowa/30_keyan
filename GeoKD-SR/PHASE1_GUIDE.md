# GeoKD-SR 第一阶段详细指导（3月1-31日）

> **阶段目标**: 完成基线实验和数据集构建，验证技术可行性
> **成功标准**:
> - ✅ 基线代码运行正常
> - ✅ 学生达到教师65%性能
> - ✅ GeoSR-Chain V1（5,000条）
> - ✅ GeoSR-Bench V1（1,000题）

---

## Week 1：环境配置与项目初始化（3月1-7日）

### 任务清单

- [ ] 1.1 创建项目目录结构
- [ ] 1.2 配置Python环境
- [ ] 1.3 下载教师和学生模型
- [ ] 1.4 准备基线数据

---

### 任务1.1：创建项目目录结构

**目标**: 建立完整的项目目录架构

**执行步骤**:

```bash
# 1. 创建主目录和所有子目录
cd D:/30_keyan
mkdir -p GeoKD-SR/{baselines,models,data/{geosr_chain,geosr_bench},scripts,configs,checkpoints,logs,results,experiments}

# 2. 验证目录结构
cd GeoKD-SR
tree -L 2  # Windows用: dir /s
```

**预期目录结构**:
```
GeoKD-SR/
├── README.md
├── requirements.txt
├── setup_env.sh
├── baselines/
│   ├── __init__.py
│   └── standard_kd.py
├── models/
│   ├── __init__.py
│   ├── spatial_aware_loss.py
│   └── geo_kd_sr.py
├── data/
│   ├── geosr_chain/
│   └── geosr_bench/
├── scripts/
│   ├── train_baseline.sh
│   ├── evaluate.sh
│   └── download_models.py
├── configs/
│   └── default.yaml
├── checkpoints/
├── logs/
├── results/
└── experiments/
    └── evaluation.py
```

**验证标准**:
- [ ] 所有目录创建成功
- [ ] 目录结构与规划一致
- [ ] 有足够的磁盘空间（100GB+）

---

### 任务1.2：配置Python环境

**目标**: 配置Conda环境和安装所有依赖

**执行步骤**:

```bash
# 1. 创建Conda环境
conda create -n geokd python=3.10 -y
conda activate geokd

# 2. 安装PyTorch（CUDA 11.8版本）
pip install torch==2.1.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# 3. 安装Transformers及相关库
pip install transformers==4.36.0
pip install peft==0.7.0
pip install accelerate==0.25.0
pip install bitsandbytes==0.41.0
pip install datasets==2.15.0

# 4. 安装数据处理库
pip install numpy pandas scikit-learn tqdm
pip install matplotlib seaborn

# 5. 安装空间计算库
pip install shapely==2.0.2
pip install geopy==2.4.1
pip install pyproj==3.6.1

# 6. 安装其他工具
pip install pyyaml wandb tensorboard
```

**创建 requirements.txt**:

```txt
# Deep Learning Framework
torch==2.1.0
torchvision
torchaudio

# Transformers & LLM
transformers==4.36.0
peft==0.7.0
accelerate==0.25.0
bitsandbytes==0.41.0
datasets==2.15.0

# Data Processing
numpy
pandas
scikit-learn
tqdm

# Visualization
matplotlib
seaborn

# Spatial Computing
shapely==2.0.2
geopy==2.4.1
pyproj==3.6.1

# Utilities
pyyaml
wandb
tensorboard
```

**验证安装**:

```bash
# 创建验证脚本
python << 'EOF'
import sys
print(f"Python版本: {sys.version}")

import torch
print(f"PyTorch版本: {torch.__version__}")
print(f"CUDA可用: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"CUDA版本: {torch.version.cuda}")
    print(f"GPU数量: {torch.cuda.device_count()}")
    print(f"GPU名称: {torch.cuda.get_device_name(0)}")

import transformers
print(f"Transformers版本: {transformers.__version__}")

import shapely
print(f"Shapely版本: {shapely.__version__}")

print("\n✅ 所有依赖安装成功！")
EOF
```

**预期输出**:
```
Python版本: 3.10.x
PyTorch版本: 2.1.0
CUDA可用: True
CUDA版本: 11.8
GPU数量: 1
GPU名称: NVIDIA A100-SXM4-40GB / V100-XXX
Transformers版本: 4.36.0
Shapely版本: 2.0.2

✅ 所有依赖安装成功！
```

**验证标准**:
- [ ] Conda环境创建成功
- [ ] PyTorch版本正确
- [ ] CUDA可用
- [ ] 所有依赖安装无误

**故障排除**:

| 问题 | 解决方案 |
|------|----------|
| CUDA不可用 | 检查NVIDIA驱动版本，安装对应CUDA版本 |
| 内存不足 | 降低PyTorch版本或使用CPU版本 |
| 导入错误 | 检查依赖版本兼容性 |

---

### 任务1.3：下载教师和学生模型

**目标**: 下载Qwen2.5-7B-Instruct（教师）和Qwen2.5-1.5B-Instruct（学生）

**模型信息**:
- 教师模型：Qwen/Qwen2.5-7B-Instruct（约14GB）
- 学生模型：Qwen/Qwen2.5-1.5B-Instruct（约3GB）
- 总计：约17GB

**创建下载脚本** (`scripts/download_models.py`):

```python
"""
模型下载脚本
下载Qwen2.5系列模型用于知识蒸馏
"""
from transformers import AutoModelForCausalLM, AutoTokenizer
import os
from huggingface_hub import login

# 配置
models = [
    {
        "name": "Qwen/Qwen2.5-7B-Instruct",
        "save_name": "Qwen2.5-7B-Instruct"
    },
    {
        "name": "Qwen/Qwen2.5-1.5B-Instruct",
        "save_name": "Qwen2.5-1.5B-Instruct"
    }
]

save_base_dir = "D:/30_keyan/GeoKD-SR/models"

def download_model(model_config):
    """下载单个模型"""
    model_name = model_config["name"]
    save_name = model_config["save_name"]
    save_path = os.path.join(save_base_dir, save_name)

    if os.path.exists(save_path):
        print(f"⚠️  {save_name} 已存在，跳过下载")
        return save_path

    print(f"\n{'='*60}")
    print(f"开始下载: {model_name}")
    print(f"保存路径: {save_path}")
    print(f"{'='*60}\n")

    try:
        # 下载tokenizer
        print("📥 下载Tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True
        )

        # 下载模型
        print("📥 下载模型权重...")
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            trust_remote_code=True,
            torch_dtype="auto",
            device_map="auto"  # 自动分配设备
        )

        # 保存到本地
        os.makedirs(save_path, exist_ok=True)
        print(f"💾 保存到 {save_path}...")

        tokenizer.save_pretrained(save_path)
        model.save_pretrained(save_path)

        print(f"✅ {save_name} 下载完成！")
        return save_path

    except Exception as e:
        print(f"❌ 下载失败: {e}")
        return None

def verify_model(model_path):
    """验证模型是否可用"""
    try:
        print(f"\n🔍 验证模型: {model_path}")
        tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            torch_dtype="auto",
            device_map="auto"
        )

        # 测试推理
        prompt = "北京是中国的什么？"
        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
        generated_ids = model.generate(
            **model_inputs,
            max_new_tokens=20
        )
        generated_ids = [
            output_ids[len(input_ids):]
            for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
        ]
        response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

        print(f"📝 测试问题: {prompt}")
        print(f"💬 模型回答: {response}")
        print(f"✅ 模型验证成功！")
        return True

    except Exception as e:
        print(f"❌ 模型验证失败: {e}")
        return False

def main():
    """主函数"""
    print("="*60)
    print("GeoKD-SR 模型下载工具")
    print("="*60)

    # 检查磁盘空间
    import shutil
    disk_usage = shutil.disk_usage("D:/")
    free_gb = disk_usage.free / (1024**3)
    print(f"\n💾 D盘可用空间: {free_gb:.1f} GB")

    if free_gb < 20:
        print("⚠️  警告: 磁盘空间不足20GB，请清理空间")
        return

    # 创建模型目录
    os.makedirs(save_base_dir, exist_ok=True)

    # 下载所有模型
    success_count = 0
    for model_config in models:
        save_path = download_model(model_config)
        if save_path:
            if verify_model(save_path):
                success_count += 1

    # 总结
    print(f"\n{'='*60}")
    print(f"下载完成: {success_count}/{len(models)} 个模型")
    print(f"模型保存位置: {save_base_dir}")
    print(f"{'='*60}")

if __name__ == "__main__":
    # 如果需要，先登录HuggingFace
    # login(token="your_token_here")

    main()
```

**执行下载**:

```bash
# 激活环境
conda activate geokd

# 运行下载脚本
cd D:/30_keyan/GeoKD-SR
python scripts/download_models.py

# 预计时间: 30-60分钟（取决于网速）
```

**使用HuggingFace镜像加速**（可选）:

```bash
# 设置镜像
export HF_ENDPOINT=https://hf-mirror.com

# 然后运行下载脚本
python scripts/download_models.py
```

**验证标准**:
- [ ] 模型下载完成无错误
- [ ] 模型可以正常加载
- [ ] 测试推理输出合理
- [ ] 磁盘空间充足

**故障排除**:

| 问题 | 解决方案 |
|------|----------|
| 下载速度慢 | 使用HF镜像或代理 |
| 磁盘空间不足 | 清理D盘空间 |
| OOM错误 | 减少model加载时的max_memory |

---

### 任务1.4：准备基线数据

**目标**: 准备初步的训练和验证数据

**数据来源**:
1. GeoQA数据集（如果有）
2. 自建小样本数据
3. 通用问答数据

**创建基线数据** (`data/geosr_chain/baseline_sample.jsonl`):

```jsonl
{"question": "北京在上海的什么方向？", "answer": "北京在上海的西北方向。", "spatial_relation_type": "directional", "reasoning": "北京的坐标是(39.9°N, 116.4°E)，上海的坐标是(31.2°N, 121.5°E)。北京位于上海的北方和西方，因此是西北方向。", "entities": [{"name": "北京", "lat": 39.9042, "lon": 116.4074}, {"name": "上海", "lat": 31.2304, "lon": 121.4737}]}
{"question": "长江流经哪些省份？", "answer": "长江流经青海、西藏、四川、云南、重庆、湖北、湖南、江西、安徽、江苏、上海等11个省级行政区。", "spatial_relation_type": "topological", "reasoning": "长江发源于青藏高原的唐古拉山脉，向东流经中国西南、华中、华东地区，最终在上海附近注入东海。", "entities": [{"name": "长江", "type": "river"}, {"name": "青海", "type": "province"}, {"name": "上海", "type": "province"}]}
{"question": "从北京到广州的距离大约是多少？", "answer": "从北京到广州的直线距离大约是1,890公里。", "spatial_relation_type": "metric", "reasoning": "使用大圆距离公式计算：北京(39.9°N, 116.4°E)到广州(23.1°N, 113.3°E)的球面距离约为1,890公里。", "entities": [{"name": "北京", "lat": 39.9042, "lon": 116.4074}, {"name": "广州", "lat": 23.1291, "lon": 113.2644}]}
{"question": "泰山位于哪个省份？", "answer": "泰山位于山东省。", "spatial_relation_type": "topological", "reasoning": "泰山是中国五岳之首，位于山东省中部泰安市，是山东省的标志性地理实体。", "entities": [{"name": "泰山", "type": "mountain"}, {"name": "山东省", "type": "province"}]}
{"question": "西安在成都的什么方向？", "answer": "西安在成都的东北方向。", "spatial_relation_type": "directional", "reasoning": "西安的坐标是(34.3°N, 108.9°E)，成都的坐标是(30.7°N, 104.1°E)。西安位于成都的北方和东方，因此是东北方向。", "entities": [{"name": "西安", "lat": 34.3416, "lon": 108.9398}, {"name": "成都", "lat": 30.5728, "lon": 104.0668}]}
```

**创建数据加载器** (`data/dataset.py`):

```python
"""
数据加载和处理模块
"""
import json
import torch
from torch.utils.data import Dataset
from typing import List, Dict, Any

class GeoSRDataset(Dataset):
    """地理空间推理数据集"""

    SPATIAL_RELATION_TYPES = ["directional", "topological", "metric", "general"]

    def __init__(self, data_path: str, tokenizer, max_length: int = 512):
        """
        Args:
            data_path: 数据文件路径（.jsonl格式）
            tokenizer: 分词器
            max_length: 最大序列长度
        """
        self.data = self._load_data(data_path)
        self.tokenizer = tokenizer
        self.max_length = max_length

    def _load_data(self, data_path: str) -> List[Dict[str, Any]]:
        """加载JSONL格式数据"""
        data = []
        with open(data_path, 'r', encoding='utf-8') as f:
            for line in f:
                data.append(json.loads(line.strip()))
        return data

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        item = self.data[idx]

        # 构造prompt
        prompt = f"问题：{item['question']}\n答案："
        response = item['answer']

        # Tokenize
        inputs = self.tokenizer(
            prompt,
            max_length=self.max_length // 2,
            truncation=True,
            padding=False,
            return_tensors=None
        )

        labels = self.tokenizer(
            response,
            max_length=self.max_length // 2,
            truncation=True,
            padding=False,
            return_tensors=None
        )

        # 合并input_ids和labels
        input_ids = inputs['input_ids'] + labels['input_ids']
        attention_mask = inputs['attention_mask'] + labels['attention_mask']

        # 构造labels（只在response部分计算损失）
        labels = [-100] * len(inputs['input_ids']) + labels['input_ids']

        # 截断到max_length
        input_ids = input_ids[:self.max_length]
        attention_mask = attention_mask[:self.max_length]
        labels = labels[:self.max_length]

        return {
            'input_ids': torch.tensor(input_ids, dtype=torch.long),
            'attention_mask': torch.tensor(attention_mask, dtype=torch.long),
            'labels': torch.tensor(labels, dtype=torch.long),
            'spatial_relation_type': item.get('spatial_relation_type', 'general')
        }

def create_sample_data(output_path: str, num_samples: int = 100):
    """创建示例数据文件"""
    import random

    # 示例模板
    templates = [
        {
            "question": "{}在{}的什么方向？",
            "relation_type": "directional"
        },
        {
            "question": "{}距离{}大约多少公里？",
            "relation_type": "metric"
        },
        {
            "question": "{}位于哪个省份？",
            "relation_type": "topological"
        }
    ]

    cities = [
        {"name": "北京", "lat": 39.9042, "lon": 116.4074},
        {"name": "上海", "lat": 31.2304, "lon": 121.4737},
        {"name": "广州", "lat": 23.1291, "lon": 113.2644},
        {"name": "深圳", "lat": 22.5431, "lon": 114.0579},
        {"name": "成都", "lat": 30.5728, "lon": 104.0668},
    ]

    data = []
    for i in range(num_samples):
        template = random.choice(templates)
        city1, city2 = random.sample(cities, 2)

        if template["relation_type"] == "directional":
            question = template["question"].format(city1["name"], city2["name"])
            answer = f"{city1['name']}在{city2['name']}的某个方向。"
        elif template["relation_type"] == "metric":
            question = template["question"].format(city1["name"], city2["name"])
            answer = f"{city1['name']}距离{city2['name']}大约XXX公里。"
        else:
            question = template["question"].format(city1["name"])
            answer = f"{city1['name']}位于某个省份。"

        data.append({
            "question": question,
            "answer": answer,
            "spatial_relation_type": template["relation_type"],
            "entities": [city1, city2]
        })

    # 保存
    with open(output_path, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    print(f"✅ 创建了 {num_samples} 条示例数据，保存到 {output_path}")

if __name__ == "__main__":
    # 测试数据加载器
    from transformers import AutoTokenizer

    # 创建示例数据
    create_sample_data("data/geosr_chain/baseline_sample.jsonl", num_samples=100)

    # 测试加载
    tokenizer = AutoTokenizer.from_pretrained(
        "D:/30_keyan/GeoKD-SR/models/Qwen2.5-1.5B-Instruct",
        trust_remote_code=True
    )

    dataset = GeoSRDataset("data/geosr_chain/baseline_sample.jsonl", tokenizer)
    print(f"\n✅ 数据集加载成功！")
    print(f"数据集大小: {len(dataset)}")

    # 测试第一个样本
    sample = dataset[0]
    print(f"\n第一个样本:")
    print(f"input_ids形状: {sample['input_ids'].shape}")
    print(f"spatial_relation_type: {sample['spatial_relation_type']}")
```

**验证数据**:

```bash
# 运行数据加载测试
python data/dataset.py

# 预期输出:
# ✅ 创建了 100 条示例数据，保存到 data/geosr_chain/baseline_sample.jsonl
# ✅ 数据集加载成功！
# 数据集大小: 100
```

**验证标准**:
- [ ] 数据格式正确（JSONL）
- [ ] 成功加载100+条样本
- [ ] 数据包含必要字段（question, answer, spatial_relation_type）
- [ ] Tokenization正常工作

---

## Week 1 总结检查清单

**完成日期**: ___________

**检查项**:
- [ ] 所有目录创建完成
- [ ] Conda环境配置成功
- [ ] PyTorch + CUDA可用
- [ ] 教师模型（7B）下载完成
- [ ] 学生模型（1.5B）下载完成
- [ ] 基线数据准备完成（100+条）
- [ ] 数据加载器测试通过

**遇到的问题**:
-
-
-

**备注**:


---

## Week 2：基线实验实现（3月8-14日）

### 任务清单

- [ ] 2.1 实现标准KL蒸馏
- [ ] 2.2 运行基线实验

---

### 任务2.1：实现标准KL蒸馏

**目标**: 实现标准的知识蒸馏baseline

**创建标准蒸馏器** (`baselines/standard_kd.py`):

```python
"""
标准知识蒸馏实现
使用KL散度进行教师-学生知识蒸馏
"""
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from typing import Dict, Optional, Any
from tqdm import tqdm
import json
import os

class StandardKDDistiller:
    """标准KL蒸馏器"""

    def __init__(
        self,
        teacher_model: nn.Module,
        student_model: nn.Module,
        tokenizer: Any,
        temperature: float = 2.0,
        alpha: float = 0.5,
        device: str = "cuda"
    ):
        """
        Args:
            teacher_model: 教师模型（冻结）
            student_model: 学生模型（训练）
            tokenizer: 分词器
            temperature: 蒸馏温度
            alpha: 蒸馏损失权重（L_total = α*L_KL + (1-α)*L_task）
            device: 设备
        """
        self.teacher = teacher_model.to(device).eval()
        self.student = student_model.to(device).train()
        self.tokenizer = tokenizer
        self.temperature = temperature
        self.alpha = alpha
        self.device = device

        # 冻结教师模型
        for param in self.teacher.parameters():
            param.requires_grad = False

    def distillation_loss(
        self,
        student_logits: torch.Tensor,
        teacher_logits: torch.Tensor,
        temperature: float
    ) -> torch.Tensor:
        """
        计算KL散度蒸馏损失

        Args:
            student_logits: 学生模型logits [batch_size, seq_len, vocab_size]
            teacher_logits: 教师模型logits [batch_size, seq_len, vocab_size]
            temperature: 温度参数

        Returns:
            KL散度损失
        """
        # 温度缩放
        student_soft = torch.log_softmax(student_logits / temperature, dim=-1)
        teacher_soft = torch.softmax(teacher_logits / temperature, dim=-1)

        # KL散度
        kl_div = nn.KLDivLoss(reduction="batchmean")(student_soft, teacher_soft)

        # 温度平方缩放
        return kl_div * (temperature ** 2)

    def task_loss(
        self,
        logits: torch.Tensor,
        labels: torch.Tensor
    ) -> torch.Tensor:
        """
        计算任务损失（交叉熵）

        Args:
            logits: 模型输出logits
            labels: 真实标签

        Returns:
            交叉熵损失
        """
        # Shift for causal LM
        shift_logits = logits[..., :-1, :].contiguous()
        shift_labels = labels[..., 1:].contiguous()

        loss = nn.CrossEntropyLoss(ignore_index=-100)(
            shift_logits.view(-1, shift_logits.size(-1)),
            shift_labels.view(-1)
        )
        return loss

    def train_step(
        self,
        batch: Dict[str, torch.Tensor],
        optimizer: torch.optim.Optimizer
    ) -> Dict[str, float]:
        """
        单步训练

        Args:
            batch: 训练批次
            optimizer: 优化器

        Returns:
            损失字典
        """
        # 移动数据到设备
        input_ids = batch["input_ids"].to(self.device)
        attention_mask = batch["attention_mask"].to(self.device)
        labels = batch["labels"].to(self.device)

        # 教师模型前向传播（无梯度）
        with torch.no_grad():
            teacher_outputs = self.teacher(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels
            )
            teacher_logits = teacher_outputs.logits

        # 学生模型前向传播
        student_outputs = self.student(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=labels
        )
        student_logits = student_outputs.logits

        # 计算损失
        loss_kl = self.distillation_loss(
            student_logits,
            teacher_logits,
            self.temperature
        )
        loss_task = self.task_loss(student_logits, labels)

        # 总损失
        loss_total = self.alpha * loss_kl + (1 - self.alpha) * loss_task

        # 反向传播
        optimizer.zero_grad()
        loss_total.backward()
        optimizer.step()

        return {
            "loss_total": loss_total.item(),
            "loss_kl": loss_kl.item(),
            "loss_task": loss_task.item()
        }

    def train_epoch(
        self,
        dataloader: DataLoader,
        optimizer: torch.optim.Optimizer,
        epoch: int
    ) -> Dict[str, float]:
        """
        训练一个epoch

        Args:
            dataloader: 数据加载器
            optimizer: 优化器
            epoch: 当前epoch

        Returns:
            平均损失
        """
        total_loss = 0.0
        total_kl_loss = 0.0
        total_task_loss = 0.0
        num_batches = len(dataloader)

        pbar = tqdm(dataloader, desc=f"Epoch {epoch}")
        for batch in pbar:
            losses = self.train_step(batch, optimizer)

            total_loss += losses["loss_total"]
            total_kl_loss += losses["loss_kl"]
            total_task_loss += losses["loss_task"]

            # 更新进度条
            pbar.set_postfix({
                "loss": f"{losses['loss_total']:.4f}",
                "kl": f"{losses['loss_kl']:.4f}",
                "task": f"{losses['loss_task']:.4f}"
            })

        return {
            "loss_total": total_loss / num_batches,
            "loss_kl": total_kl_loss / num_batches,
            "loss_task": total_task_loss / num_batches
        }

    def save_checkpoint(self, save_path: str, epoch: int, optimizer: torch.optim.Optimizer):
        """保存检查点"""
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        torch.save({
            "epoch": epoch,
            "student_model_state_dict": self.student.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "temperature": self.temperature,
            "alpha": self.alpha
        }, save_path)
        print(f"✅ 检查点已保存: {save_path}")

    def load_checkpoint(self, checkpoint_path: str, optimizer: Optional[torch.optim.Optimizer] = None):
        """加载检查点"""
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        self.student.load_state_dict(checkpoint["student_model_state_dict"])
        if optimizer is not None:
            optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        print(f"✅ 检查点已加载: {checkpoint_path}")
        return checkpoint["epoch"]


def create_optimizer(model: nn.Module, learning_rate: float = 1e-4):
    """创建优化器"""
    return torch.optim.AdamW(model.parameters(), lr=learning_rate)


if __name__ == "__main__":
    # 测试蒸馏器
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from data.dataset import GeoSRDataset

    # 加载模型
    print("加载模型...")
    teacher = AutoModelForCausalLM.from_pretrained(
        "D:/30_keyan/GeoKD-SR/models/Qwen2.5-7B-Instruct",
        trust_remote_code=True,
        torch_dtype="auto"
    )
    student = AutoModelForCausalLM.from_pretrained(
        "D:/30_keyan/GeoKD-SR/models/Qwen2.5-1.5B-Instruct",
        trust_remote_code=True,
        torch_dtype="auto"
    )
    tokenizer = AutoTokenizer.from_pretrained(
        "D:/30_keyan/GeoKD-SR/models/Qwen2.5-1.5B-Instruct",
        trust_remote_code=True
    )

    # 加载数据
    print("加载数据...")
    dataset = GeoSRDataset("data/geosr_chain/baseline_sample.jsonl", tokenizer)
    dataloader = DataLoader(dataset, batch_size=2, shuffle=True)

    # 创建蒸馏器
    print("初始化蒸馏器...")
    distiller = StandardKDDistiller(
        teacher_model=teacher,
        student_model=student,
        tokenizer=tokenizer,
        temperature=2.0,
        alpha=0.5
    )

    # 创建优化器
    optimizer = create_optimizer(student, learning_rate=1e-4)

    # 测试训练步
    print("\n测试训练...")
    batch = next(iter(dataloader))
    losses = distiller.train_step(batch, optimizer)
    print(f"✅ 训练步测试成功！")
    print(f"   - 总损失: {losses['loss_total']:.4f}")
    print(f"   - KL损失: {losses['loss_kl']:.4f}")
    print(f"   - 任务损失: {losses['loss_task']:.4f}")
```

**创建训练配置** (`configs/default.yaml`):

```yaml
# 训练配置
training:
  # 基本设置
  epochs: 3
  batch_size: 8  # effective batch size with gradient accumulation
  gradient_accumulation_steps: 16  # effective batch size = 8 * 16 = 128
  learning_rate: 1.0e-4
  weight_decay: 0.01
  warmup_ratio: 0.1

  # 保存和日志
  save_steps: 500
  logging_steps: 10
  eval_steps: 500

  # 硬件
  device: cuda
  fp16: true
  max_grad_norm: 1.0

# 蒸馏配置
distillation:
  temperature: 2.0
  alpha: 0.5  # 蒸馏损失权重

# 模型配置
model:
  teacher_path: "D:/30_keyan/GeoKD-SR/models/Qwen2.5-7B-Instruct"
  student_path: "D:/30_keyan/GeoKD-SR/models/Qwen2.5-1.5B-Instruct"

# 数据配置
data:
  train_path: "data/geosr_chain/baseline_sample.jsonl"
  max_length: 512
  num_workers: 4

# 输出配置
output:
  checkpoint_dir: "checkpoints"
  log_dir: "logs"
  result_dir: "results"
```

**创建训练脚本** (`scripts/train_baseline.sh`):

```bash
#!/bin/bash
# 基线训练脚本

# 配置
conda activate geokd
cd D:/30_keyan/GeoKD-SR

# 参数
MODEL_NAME="baseline"
EPOCHS=3
BATCH_SIZE=8
GRAD_ACCUM=16
LR=1e-4
TEMP=2.0
ALPHA=0.5

# 输出
CHECKPOINT_DIR="checkpoints/${MODEL_NAME}"
LOG_FILE="logs/${MODEL_NAME}_training.log"
mkdir -p $CHECKPOINT_DIR logs results

# 记录开始时间
echo "========================================" | tee -a $LOG_FILE
echo "开始训练: $(date)" | tee -a $LOG_FILE
echo "模型: ${MODEL_NAME}" | tee -a $LOG_FILE
echo "Epochs: ${EPOCHS}" | tee -a $LOG_FILE
echo "批次大小: ${BATCH_SIZE}" | tee -a $LOG_FILE
echo "学习率: ${LR}" | tee -a $LOG_FILE
echo "========================================" | tee -a $LOG_FILE

# 运行训练（Python脚本将在下一个任务中创建）
python scripts/train_baseline.py \
    --model_name $MODEL_NAME \
    --epochs $EPOCHS \
    --batch_size $BATCH_SIZE \
    --gradient_accumulation_steps $GRAD_ACCUM \
    --learning_rate $LR \
    --temperature $TEMP \
    --alpha $ALPHA \
    --checkpoint_dir $CHECKPOINT_DIR \
    2>&1 | tee -a $LOG_FILE

# 记录结束时间
echo "========================================" | tee -a $LOG_FILE
echo "训练完成: $(date)" | tee -a $LOG_FILE
echo "========================================" | tee -a $LOG_FILE
```

**创建训练主脚本** (`scripts/train_baseline.py`):

```python
"""
基线训练主脚本
"""
import torch
from torch.utils.data import DataLoader, random_split
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers import get_linear_schedule_with_warmup
import argparse
import yaml
import os
from tqdm import tqdm
import json
from datetime import datetime

from baselines.standard_kd import StandardKDDistiller, create_optimizer
from data.dataset import GeoSRDataset


def load_config(config_path: str) -> dict:
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def train(
    distiller: StandardKDDistiller,
    train_dataloader: DataLoader,
    val_dataloader: DataLoader,
    optimizer: torch.optim.Optimizer,
    scheduler,
    args: argparse.Namespace
):
    """完整训练流程"""

    # 训练历史
    history = {
        "train_loss": [],
        "val_loss": [],
        "epochs": []
    }

    best_val_loss = float('inf')
    global_step = 0

    # 训练循环
    for epoch in range(1, args.epochs + 1):
        print(f"\n{'='*60}")
        print(f"Epoch {epoch}/{args.epochs}")
        print(f"{'='*60}")

        # 训练
        train_losses = distiller.train_epoch(train_dataloader, optimizer, epoch)
        history["train_loss"].append(train_losses["loss_total"])
        history["epochs"].append(epoch)

        print(f"\n训练损失: {train_losses['loss_total']:.4f}")
        print(f"  - KL损失: {train_losses['loss_kl']:.4f}")
        print(f"  - 任务损失: {train_losses['loss_task']:.4f}")

        # 验证
        if val_dataloader is not None:
            val_loss = evaluate(distiller, val_dataloader)
            history["val_loss"].append(val_loss)
            print(f"验证损失: {val_loss:.4f}")

            # 保存最佳模型
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                save_path = os.path.join(
                    args.checkpoint_dir,
                    f"best_model_epoch_{epoch}.pt"
                )
                distiller.save_checkpoint(save_path, epoch, optimizer)
                print(f"✅ 保存最佳模型: {save_path}")

        # 保存定期检查点
        if epoch % args.save_epochs == 0:
            save_path = os.path.join(
                args.checkpoint_dir,
                f"checkpoint_epoch_{epoch}.pt"
            )
            distiller.save_checkpoint(save_path, epoch, optimizer)

        # 更新学习率
        if scheduler is not None:
            scheduler.step()

        global_step += len(train_dataloader)

    # 保存训练历史
    history_path = os.path.join(args.checkpoint_dir, "training_history.json")
    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    return history


def evaluate(
    distiller: StandardKDDistiller,
    dataloader: DataLoader
) -> float:
    """评估模型"""
    distiller.student.eval()
    total_loss = 0.0

    with torch.no_grad():
        for batch in tqdm(dataloader, desc="评估"):
            input_ids = batch["input_ids"].to(distiller.device)
            attention_mask = batch["attention_mask"].to(distiller.device)
            labels = batch["labels"].to(distiller.device)

            outputs = distiller.student(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels
            )
            total_loss += outputs.loss.item()

    distiller.student.train()
    return total_loss / len(dataloader)


def main():
    parser = argparse.ArgumentParser(description="训练基线蒸馏模型")
    parser.add_argument("--config", type=str, default="configs/default.yaml",
                        help="配置文件路径")
    parser.add_argument("--model_name", type=str, default="baseline",
                        help="模型名称")
    parser.add_argument("--epochs", type=int, default=3,
                        help="训练轮数")
    parser.add_argument("--batch_size", type=int, default=8,
                        help="批次大小")
    parser.add_argument("--gradient_accumulation_steps", type=int, default=16,
                        help="梯度累积步数")
    parser.add_argument("--learning_rate", type=float, default=1e-4,
                        help="学习率")
    parser.add_argument("--temperature", type=float, default=2.0,
                        help="蒸馏温度")
    parser.add_argument("--alpha", type=float, default=0.5,
                        help="蒸馏损失权重")
    parser.add_argument("--checkpoint_dir", type=str, default="checkpoints/baseline",
                        help="检查点目录")
    parser.add_argument("--save_epochs", type=int, default=1,
                        help="保存间隔")
    parser.add_argument("--train_split", type=float, default=0.9,
                        help="训练集比例")

    args = parser.parse_args()

    # 创建输出目录
    os.makedirs(args.checkpoint_dir, exist_ok=True)

    # 加载配置（如果有）
    if os.path.exists(args.config):
        config = load_config(args.config)
    else:
        config = {}

    print("="*60)
    print("GeoKD-SR 基线训练")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"模型名称: {args.model_name}")
    print(f"训练轮数: {args.epochs}")
    print(f"批次大小: {args.batch_size}")
    print(f"有效批次大小: {args.batch_size * args.gradient_accumulation_steps}")
    print(f"学习率: {args.learning_rate}")
    print(f"蒸馏温度: {args.temperature}")
    print(f"蒸馏权重: {args.alpha}")
    print("="*60)

    # 加载模型
    print("\n📦 加载模型...")
    tokenizer = AutoTokenizer.from_pretrained(
        "D:/30_keyan/GeoKD-SR/models/Qwen2.5-1.5B-Instruct",
        trust_remote_code=True
    )
    teacher = AutoModelForCausalLM.from_pretrained(
        "D:/30_keyan/GeoKD-SR/models/Qwen2.5-7B-Instruct",
        trust_remote_code=True,
        torch_dtype="auto"
    )
    student = AutoModelForCausalLM.from_pretrained(
        "D:/30_keyan/GeoKD-SR/models/Qwen2.5-1.5B-Instruct",
        trust_remote_code=True,
        torch_dtype="auto"
    )

    # 加载数据
    print("📦 加载数据...")
    dataset = GeoSRDataset(
        "data/geosr_chain/baseline_sample.jsonl",
        tokenizer,
        max_length=512
    )

    # 划分训练/验证集
    train_size = int(len(dataset) * args.train_split)
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = random_split(dataset, [train_size, val_size])

    print(f"   训练集大小: {train_size}")
    print(f"   验证集大小: {val_size}")

    # 创建数据加载器
    train_dataloader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0  # Windows下设置为0
    )
    val_dataloader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0
    )

    # 创建蒸馏器
    print("🔧 初始化蒸馏器...")
    distiller = StandardKDDistiller(
        teacher_model=teacher,
        student_model=student,
        tokenizer=tokenizer,
        temperature=args.temperature,
        alpha=args.alpha
    )

    # 创建优化器
    optimizer = create_optimizer(student, learning_rate=args.learning_rate)

    # 创建学习率调度器
    num_training_steps = len(train_dataloader) * args.epochs // args.gradient_accumulation_steps
    num_warmup_steps = int(num_training_steps * 0.1)
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=num_warmup_steps,
        num_training_steps=num_training_steps
    )

    # 开始训练
    print("\n🚀 开始训练...\n")
    history = train(
        distiller=distiller,
        train_dataloader=train_dataloader,
        val_dataloader=val_dataloader,
        optimizer=optimizer,
        scheduler=scheduler,
        args=args
    )

    # 保存最终模型
    final_path = os.path.join(args.checkpoint_dir, "final_model.pt")
    distiller.save_checkpoint(final_path, args.epochs, optimizer)

    print(f"\n{'='*60}")
    print("✅ 训练完成！")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"检查点保存在: {args.checkpoint_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
```

**验证标准**:
- [ ] 所有代码文件创建完成
- [ ] 导入测试无错误
- [ ] 蒸馏器初始化成功
- [ ] 单步训练测试通过

---

### 任务2.2：运行基线实验

**目标**: 完成第一次端到端训练

**执行步骤**:

```bash
# 1. 准备数据（确保有100+条样本）
cd D:/30_keyan/GeoKD-SR
python data/dataset.py

# 2. 测试蒸馏器
python baselines/standard_kd.py

# 3. 运行训练（Windows下直接运行Python脚本）
python scripts/train_baseline.py \
    --model_name baseline \
    --epochs 3 \
    --batch_size 2 \
    --gradient_accumulation_steps 4 \
    --learning_rate 1e-4 \
    --temperature 2.0 \
    --alpha 0.5 \
    --checkpoint_dir checkpoints/baseline \
    --save_epochs 1

# 4. 监控训练
# 实时查看日志
tail -f logs/baseline_training.log  # Linux/Mac
Get-Content logs/baseline_training.log -Wait  # PowerShell
```

**预期输出**:
```
========================================
开始时间: 2026-03-10 14:30:00
模型名称: baseline
训练轮数: 3
批次大小: 2
有效批次大小: 8
学习率: 0.0001
蒸馏温度: 2.0
蒸馏权重: 0.5
========================================

📦 加载模型...
📦 加载数据...
   训练集大小: 90
   验证集大小: 10
🔧 初始化蒸馏器...

🚀 开始训练...

============================================================
Epoch 1/3
============================================================
Training: 100%|██████████| 45/45 [02:30<00:00, 3.33s/it, loss=2.3456, kl=1.1234, task=1.2222]

训练损失: 2.3456
  - KL损失: 1.1234
  - 任务损失: 1.2222
评估: 100%|██████████| 5/5 [00:15<00:00, 3.00s/it]
验证损失: 2.4567
✅ 保存最佳模型: checkpoints/baseline/best_model_epoch_1.pt
...
```

**性能评估**:

创建评估脚本 (`experiments/evaluate_baseline.py`):

```python
"""
基线模型评估脚本
"""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from data.dataset import GeoSRDataset
from torch.utils.data import DataLoader
import json
import os
from tqdm import tqdm
import numpy as np
from sklearn.metrics import accuracy_score, f1_score


class GeoSREvaluator:
    """地理空间推理评测器"""

    def __init__(self, model, tokenizer, device="cuda"):
        self.model = model.to(device).eval()
        self.tokenizer = tokenizer
        self.device = device

    def generate_answer(self, question: str, max_new_tokens: int = 50) -> str:
        """生成答案"""
        prompt = f"问题：{question}\n答案："

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=0.7,
                do_sample=True,
                top_p=0.9,
                pad_token_id=self.tokenizer.eos_token_id
            )

        # 解码
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        # 提取答案部分
        answer = response.split("答案：")[-1].strip()
        return answer

    def evaluate_dataset(self, dataset: GeoSRDataset, num_samples: int = None) -> dict:
        """评估整个数据集"""
        if num_samples:
            indices = list(range(min(num_samples, len(dataset))))
        else:
            indices = list(range(len(dataset)))

        results = []
        for idx in tqdm(indices, desc="评估"):
            item = dataset.data[idx]
            question = item["question"]
            ground_truth = item["answer"]

            # 生成答案
            predicted = self.generate_answer(question)

            results.append({
                "question": question,
                "ground_truth": ground_truth,
                "predicted": predicted,
                "spatial_relation_type": item.get("spatial_relation_type", "general")
            })

        # 计算指标
        return self._compute_metrics(results)

    def _compute_metrics(self, results: list) -> dict:
        """计算评测指标"""
        # 简单的准确率（答案是否包含关键词）
        correct = 0
        for result in results:
            gt = result["ground_truth"]
            pred = result["predicted"]

            # 简单匹配（实际应用中需要更复杂的评估）
            if any(word in pred for word in gt.split()):
                correct += 1

        accuracy = correct / len(results)

        # 按空间关系类型分组统计
        type_stats = {}
        for result in results:
            rel_type = result["spatial_relation_type"]
            if rel_type not in type_stats:
                type_stats[rel_type] = {"correct": 0, "total": 0}

            gt = result["ground_truth"]
            pred = result["predicted"]
            if any(word in pred for word in gt.split()):
                type_stats[rel_type]["correct"] += 1
            type_stats[rel_type]["total"] += 1

        type_accuracy = {
            rel_type: stats["correct"] / stats["total"]
            for rel_type, stats in type_stats.items()
        }

        return {
            "accuracy": accuracy,
            "type_accuracy": type_accuracy,
            "total_samples": len(results)
        }


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=str, required=True,
                        help="模型检查点路径")
    parser.add_argument("--data_path", type=str,
                        default="data/geosr_chain/baseline_sample.jsonl")
    parser.add_argument("--num_samples", type=int, default=None,
                        help="评估样本数量")
    parser.add_argument("--output", type=str, default="results/baseline_evaluation.json")

    args = parser.parse_args()

    # 加载模型
    print("📦 加载模型...")
    tokenizer = AutoTokenizer.from_pretrained(
        "D:/30_keyan/GeoKD-SR/models/Qwen2.5-1.5B-Instruct",
        trust_remote_code=True
    )
    model = AutoModelForCausalLM.from_pretrained(
        "D:/30_keyan/GeoKD-SR/models/Qwen2.5-1.5B-Instruct",
        trust_remote_code=True,
        torch_dtype="auto"
    )

    # 加载检查点
    if args.checkpoint:
        print(f"📥 加载检查点: {args.checkpoint}")
        checkpoint = torch.load(args.checkpoint, map_location="cuda")
        model.load_state_dict(checkpoint["student_model_state_dict"])

    # 加载数据
    print("📦 加载数据...")
    dataset = GeoSRDataset(args.data_path, tokenizer)

    # 创建评估器
    evaluator = GeoSREvaluator(model, tokenizer)

    # 评估
    print("🔍 开始评估...")
    metrics = evaluator.evaluate_dataset(dataset, args.num_samples)

    # 打印结果
    print("\n" + "="*60)
    print("评估结果")
    print("="*60)
    print(f"总准确率: {metrics['accuracy']:.2%}")
    print(f"总样本数: {metrics['total_samples']}")
    print("\n按空间关系类型:")
    for rel_type, acc in metrics['type_accuracy'].items():
        print(f"  - {rel_type}: {acc:.2%}")
    print("="*60)

    # 保存结果
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    print(f"\n✅ 结果已保存到: {args.output}")


if __name__ == "__main__":
    main()
```

**运行评估**:

```bash
# 评估训练好的模型
python experiments/evaluate_baseline.py \
    --checkpoint checkpoints/baseline/best_model_epoch_1.pt \
    --num_samples 50 \
    --output results/baseline_evaluation.json
```

**验证标准**:
- [ ] 训练过程无错误
- [ ] Loss正常下降
- [ ] 学生模型能生成合理答案
- [ ] 达到教师模型60-65%性能
- [ ] 检查点文件保存成功

**故障排除**:

| 问题 | 解决方案 |
|------|----------|
| OOM错误 | 降低batch_size，增加gradient_accumulation_steps |
| Loss不下降 | 检查学习率，尝试调整α和temperature |
| 生成乱码 | 检查tokenizer配置，调整generation参数 |
| 训练太慢 | 减少max_length，使用fp16 |

---

## Week 2 总结检查清单

**完成日期**: ___________

**检查项**:
- [ ] 标准KL蒸馏代码实现完成
- [ ] 训练脚本测试通过
- [ ] 完成3个epochs训练
- [ ] Loss正常下降
- [ ] 学生模型达到教师60%+性能
- [ ] 检查点和日志保存完整

**性能记录**:
- 最终训练Loss: ___________
- 验证Loss: ___________
- 评估准确率: ___________

**遇到的问题**:
-
-

**备注**:


---

## Week 3：数据收集与Prompt设计（3月15-21日）

### 任务清单

- [ ] 3.1 设计数据生成Prompt
- [ ] 3.2 构建地理实体库
- [ ] 3.3 生成种子数据（5,000条）

---

### 任务3.1：设计数据生成Prompt

**目标**: 设计高质量的数据生成Prompt模板

**创建Prompt模块** (`data/prompts.py`):

```python
"""
数据生成Prompt模板
用于生成地理空间推理训练数据
"""

# 方向关系生成Prompt
DIRECTION_PROMPT = """
你是一个专业的地理空间推理专家。请根据给定的地理实体信息，生成方向关系问答数据。

## 输入信息
- 实体1: {name1} ({lat1}°N, {lon1}°E)
- 实体2: {name2} ({lat2}°N, {lon2}°E)

## 任务要求
1. 生成一个自然语言的方向关系问题
2. 提供详细的推理链（包括坐标分析、方位判断）
3. 给出准确的答案（使用8方向：东、南、西、北、东北、东南、西北、西南）

## 输出格式（JSON）
{
  "question": "自然语言问题",
  "reasoning": "详细的推理过程，包括坐标对比、方位计算",
  "answer": "准确的方向答案",
  "spatial_relation_type": "directional",
  "entities": [
    {{"name": "实体1", "lat": 纬度, "lon": 经度}},
    {{"name": "实体2", "lat": 纬度, "lon": 经度}}
  ]
}

## 示例
输入：
- 实体1: 北京 (39.9°N, 116.4°E)
- 实体2: 上海 (31.2°N, 121.5°E)

输出：
{{
  "question": "北京在上海的什么方向？",
  "reasoning": "北京的坐标是(39.9°N, 116.4°E)，上海的坐标是(31.2°N, 121.5°E)。纬度上，39.9° > 31.2°，北京在上海北方；经度上，116.4° < 121.5°，北京在上海西方。综合判断，北京在上海的西北方向。",
  "answer": "北京在上海的西北方向。",
  "spatial_relation_type": "directional",
  "entities": [
    {{"name": "北京", "lat": 39.9, "lon": 116.4}},
    {{"name": "上海", "lat": 31.2, "lon": 121.5}}
  ]
}}

现在请为给定的实体生成方向关系问答数据。
"""

# 拓扑关系生成Prompt
TOPOLOGY_PROMPT = """
你是一个专业的地理空间推理专家。请根据给定的地理实体信息，生成拓扑关系问答数据。

## 输入信息
- 实体1: {name1}, 类型: {type1}
- 实体2: {name2}, 类型: {type2}
- 关系类型: {relation_type}（包含、相邻、接壤、穿过等）

## 任务要求
1. 生成一个关于拓扑关系的自然语言问题
2. 提供详细的推理链（说明空间位置关系）
3. 给出准确的答案

## 拓扑关系类型
- 包含关系：一个实体在另一个实体内部（如：城市在省份内）
- 相邻关系：两个实体共享边界（如：省份接壤）
- 穿过关系：线性实体穿过区域实体（如：河流流经省份）

## 输出格式（JSON）
{{
  "question": "自然语言问题",
  "reasoning": "详细的推理过程，解释拓扑关系",
  "answer": "准确的答案",
  "spatial_relation_type": "topological",
  "entities": [
    {{"name": "实体1", "type": "类型"}},
    {{"name": "实体2", "type": "类型"}}
  ]
}}

## 示例
输入：
- 实体1: 长江, 类型: 河流
- 实体2: 湖北, 类型: 省份
- 关系类型: 穿过

输出：
{{
  "question": "长江流经湖北省吗？",
  "reasoning": "长江是中国最长的河流，发源于青藏高原，向东流经中国多个省份。根据地理资料，长江确实流经湖北省，穿过宜昌、武汉等城市，是湖北省的重要水系。",
  "answer": "是的，长江流经湖北省。",
  "spatial_relation_type": "topological",
  "entities": [
    {{"name": "长江", "type": "river"}},
    {{"name": "湖北省", "type": "province"}}
  ]
}}

现在请为给定的实体生成拓扑关系问答数据。
"""

# 度量关系生成Prompt
METRIC_PROMPT = """
你是一个专业的地理空间推理专家。请根据给定的地理实体信息，生成度量关系问答数据。

## 输入信息
- 实体1: {name1} ({lat1}°N, {lon1}°E)
- 实体2: {name2} ({lat2}°N, {lon2}°E)

## 任务要求
1. 生成一个关于距离或面积的度量问题
2. 提供详细的推理链（包括计算方法）
3. 给出准确的答案（单位：公里或平方千米）

## 注意事项
- 使用大圆距离公式（Haversine公式）计算球面距离
- 距离取整数或保留一位小数
- 题目应具有实际意义

## 输出格式（JSON）
{{
  "question": "自然语言问题",
  "reasoning": "详细的推理过程，包括计算公式和结果",
  "answer": "准确的度量答案（含单位）",
  "spatial_relation_type": "metric",
  "entities": [
    {{"name": "实体1", "lat": 纬度, "lon": 经度}},
    {{"name": "实体2", "lat": 纬度, "lon": 经度}}
  ]
}}

## 示例
输入：
- 实体1: 北京 (39.9°N, 116.4°E)
- 实体2: 上海 (31.2°N, 121.5°E)

输出：
{{
  "question": "从北京到上海的直线距离大约是多少公里？",
  "reasoning": "使用Haversine公式计算球面距离：北京(39.9°N, 116.4°E)到上海(31.2°N, 121.5°E)。经过计算，两地的球面距离约为1,068公里。这是理论上的直线距离，实际交通距离会更长。",
  "answer": "从北京到上海的直线距离大约是1,068公里。",
  "spatial_relation_type": "metric",
  "entities": [
    {{"name": "北京", "lat": 39.9, "lon": 116.4}},
    {{"name": "上海", "lat": 31.2, "lon": 121.5}}
  ]
}}

现在请为给定的实体生成度量关系问答数据。
"""

# 综合推理Prompt
COMPREHENSIVE_PROMPT = """
你是一个专业的地理空间推理专家。请生成一个需要综合运用多种空间关系的复杂推理问题。

## 输入信息
- 实体列表: {entities}
- 推理步骤数: {num_steps}（2-3步）

## 任务要求
1. 生成一个需要多步推理的复杂问题
2. 提供详细的推理链（每一步都清晰标注）
3. 给出准确的最终答案
4. 问题应涉及2-3种空间关系类型（方向、拓扑、度量）

## 推铄链示例
步骤1：确定实体A和实体B的方向关系
步骤2：确定实体B和实体C的距离
步骤3：综合判断，得出答案

## 输出格式（JSON）
{{
  "question": "需要多步推理的复杂问题",
  "reasoning": "详细的分步推理过程",
  "answer": "最终答案",
  "spatial_relation_type": "comprehensive",
  "entities": [
    {{"name": "实体1", ...}},
    {{"name": "实体2", ...}},
    {{"name": "实体3", ...}}
  ],
  "reasoning_steps": [
    "步骤1的说明",
    "步骤2的说明",
    "步骤3的说明"
  ]
}}

## 示例
输入：
- 实体列表: [北京, 武汉, 广州]
- 推理步骤数: 2

输出：
{{
  "question": "如果一个人从北京出发，先到武汉，再到广州，他整体是向什么方向移动？移动的总距离大约是多少？",
  "reasoning": "步骤1：北京(39.9°N, 116.4°E)到武汉(30.6°N, 114.4°E)，向南方移动，距离约1,050公里。步骤2：武汉(30.6°N, 114.4°E)到广州(23.1°N, 113.3°E)，继续向南方移动，距离约830公里。综合判断：整体向南移动，总距离约1,880公里。",
  "answer": "整体向南移动，总距离约1,880公里。",
  "spatial_relation_type": "comprehensive",
  "entities": [
    {{"name": "北京", "lat": 39.9, "lon": 116.4}},
    {{"name": "武汉", "lat": 30.6, "lon": 114.4}},
    {{"name": "广州", "lat": 23.1, "lon": 113.3}}
  ],
  "reasoning_steps": [
    "北京到武汉：向南移动约1,050公里",
    "武汉到广州：向南移动约830公里",
    "综合：整体向南，总距离1,880公里"
  ]
}}

现在请生成一个综合推理问题。
"""


class PromptTemplate:
    """Prompt模板管理器"""

    def __init__(self):
        self.templates = {
            "directional": DIRECTION_PROMPT,
            "topological": TOPOLOGY_PROMPT,
            "metric": METRIC_PROMPT,
            "comprehensive": COMPREHENSIVE_PROMPT
        }

    def get_prompt(self, relation_type: str, **kwargs) -> str:
        """
        获取格式化的Prompt

        Args:
            relation_type: 空间关系类型
            **kwargs: 模板变量

        Returns:
            格式化后的Prompt字符串
        """
        template = self.templates.get(relation_type)
        if not template:
            raise ValueError(f"未知的关系类型: {relation_type}")

        return template.format(**kwargs)

    def list_types(self) -> list:
        """列出所有支持的Prompt类型"""
        return list(self.templates.keys())


# 测试
if __name__ == "__main__":
    pt = PromptTemplate()

    # 测试方向关系Prompt
    print("方向关系Prompt:")
    print("="*60)
    prompt = pt.get_prompt(
        "directional",
        name1="北京",
        lat1=39.9,
        lon1=116.4,
        name2="上海",
        lat2=31.2,
        lon2=121.5
    )
    print(prompt[:500] + "...")
    print()
```

**验证Prompt质量**:

创建Prompt测试脚本 (`scripts/test_prompts.py`):

```python
"""
测试Prompt生成质量
使用GPT-4生成样本并人工评估
"""
import os
import json
from openai import OpenAI  # 需要安装openai库
from data.prompts import PromptTemplate


def test_prompt_generation(relation_type: str, num_samples: int = 5):
    """测试特定类型的Prompt生成效果"""

    # 初始化OpenAI客户端
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ 请设置OPENAI_API_KEY环境变量")
        return

    client = OpenAI(api_key=api_key)
    pt = PromptTemplate()

    print(f"\n{'='*60}")
    print(f"测试 {relation_type} 关系Prompt生成")
    print(f"{'='*60}\n")

    results = []

    for i in range(num_samples):
        print(f"\n[样本 {i+1}/{num_samples}]")

        # 构造Prompt（这里用示例数据）
        if relation_type == "directional":
            prompt = pt.get_prompt(
                relation_type,
                name1="北京",
                lat1=39.9,
                lon1=116.4,
                name2="广州",
                lat2=23.1,
                lon2=113.3
            )
        elif relation_type == "topological":
            prompt = pt.get_prompt(
                relation_type,
                name1="长江",
                type1="河流",
                name2="四川",
                type2="省份",
                relation_type="穿过"
            )
        elif relation_type == "metric":
            prompt = pt.get_prompt(
                relation_type,
                name1="西安",
                lat1=34.3,
                lon1=108.9,
                name2="成都",
                lat2=30.6,
                lon2=104.1
            )
        else:
            prompt = pt.get_prompt(
                relation_type,
                entities="北京, 武汉, 广州",
                num_steps=2
            )

        # 调用GPT-4生成
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "你是一个专业的地理空间推理专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )

            generated_text = response.choices[0].message.content

            # 解析JSON
            try:
                generated_json = json.loads(generated_text)
                results.append(generated_json)

                # 打印结果
                print(f"✅ 生成成功")
                print(f"问题: {generated_json['question']}")
                print(f"答案: {generated_json['answer']}")
                print(f"类型: {generated_json['spatial_relation_type']}")

            except json.JSONDecodeError:
                print(f"❌ JSON解析失败")
                print(f"原始输出: {generated_text[:200]}")

        except Exception as e:
            print(f"❌ API调用失败: {e}")

    # 保存结果
    output_path = f"results/prompt_test_{relation_type}.jsonl"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + '\n')

    print(f"\n✅ 结果已保存到: {output_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--relation_type", type=str, default="directional",
                        choices=["directional", "topological", "metric", "comprehensive"],
                        help="空间关系类型")
    parser.add_argument("--num_samples", type=int, default=5,
                        help="生成样本数量")

    args = parser.parse_args()

    test_prompt_generation(args.relation_type, args.num_samples)
```

**运行Prompt测试**:

```bash
# 设置OpenAI API Key
export OPENAI_API_KEY="your_api_key_here"  # Linux/Mac
set OPENAI_API_KEY=your_api_key_here       # Windows

# 测试方向关系Prompt
python scripts/test_prompts.py --relation_type directional --num_samples 5

# 测试拓扑关系Prompt
python scripts/test_prompts.py --relation_type topological --num_samples 5

# 测试度量关系Prompt
python scripts/test_prompts.py --relation_type metric --num_samples 5
```

**人工评估标准**:

对生成的5个样本进行人工评估，检查：
- [ ] 问题表述自然流畅
- [ ] 推理链逻辑清晰
- [ ] 答案准确无误
- [ ] JSON格式正确
- [ ] 包含所有必要字段

**质量标准**: ≥85%的样本通过评估

---

### 任务3.2：构建地理实体库

**目标**: 建立500+个地理实体的数据库

**数据来源**:
1. 中国行政区划（34个省级行政区）
2. 主要城市（省会、地级市）
3. 主要河流、山脉、湖泊

**创建实体库** (`data/entity_database.py`):

```python
"""
地理实体库
包含中国主要地理实体的坐标和属性信息
"""
import json
from typing import List, Dict, Any


# 省级行政区
PROVINCES = [
    {"name": "北京市", "type": "municipality", "lat": 39.9042, "lon": 116.4074},
    {"name": "天津市", "type": "municipality", "lat": 39.0842, "lon": 117.2010},
    {"name": "河北省", "type": "province", "lat": 38.0428, "lon": 114.5149},
    {"name": "山西省", "type": "province", "lat": 37.5707, "lon": 111.8499},
    {"name": "内蒙古自治区", "type": "autonomous_region", "lat": 40.8414, "lon": 111.7519},
    {"name": "辽宁省", "type": "province", "lat": 41.2956, "lon": 123.4315},
    {"name": "吉林省", "type": "province", "lat": 43.8868, "lon": 125.3245},
    {"name": "黑龙江省", "type": "province", "lat": 45.7732, "lon": 126.6499},
    {"name": "上海市", "type": "municipality", "lat": 31.2304, "lon": 121.4737},
    {"name": "江苏省", "type": "province", "lat": 32.0603, "lon": 118.7969},
    {"name": "浙江省", "type": "province", "lat": 30.2741, "lon": 120.1551},
    {"name": "安徽省", "type": "province", "lat": 31.8612, "lon": 117.2272},
    {"name": "福建省", "type": "province", "lat": 26.0745, "lon": 119.2965},
    {"name": "江西省", "type": "province", "lat": 28.6769, "lon": 115.9099},
    {"name": "山东省", "type": "province", "lat": 36.6683, "lon": 117.0204},
    {"name": "河南省", "type": "province", "lat": 34.7466, "lon": 113.6253},
    {"name": "湖北省", "type": "province", "lat": 30.5928, "lon": 114.3055},
    {"name": "湖南省", "type": "province", "lat": 28.2282, "lon": 112.9388},
    {"name": "广东省", "type": "province", "lat": 23.3790, "lon": 116.6832},
    {"name": "广西壮族自治区", "type": "autonomous_region", "lat": 22.8155, "lon": 108.3275},
    {"name": "海南省", "type": "province", "lat": 20.0174, "lon": 110.3492},
    {"name": "重庆市", "type": "municipality", "lat": 29.4316, "lon": 106.9123},
    {"name": "四川省", "type": "province", "lat": 30.6171, "lon": 104.0648},
    {"name": "贵州省", "type": "province", "lat": 26.5783, "lon": 106.7135},
    {"name": "云南省", "type": "province", "lat": 25.0443, "lon": 102.7046},
    {"name": "西藏自治区", "type": "autonomous_region", "lat": 29.6524, "lon": 91.1721},
    {"name": "陕西省", "type": "province", "lat": 34.3416, "lon": 108.9398},
    {"name": "甘肃省", "type": "province", "lat": 36.0611, "lon": 103.8343},
    {"name": "青海省", "type": "province", "lat": 36.6171, "lon": 101.7782},
    {"name": "宁夏回族自治区", "type": "autonomous_region", "lat": 38.4681, "lon": 106.2731},
    {"name": "新疆维吾尔自治区", "type": "autonomous_region", "lat": 43.7930, "lon": 87.6177},
    {"name": "香港特别行政区", "type": "sar", "lat": 22.3193, "lon": 114.1694},
    {"name": "澳门特别行政区", "type": "sar", "lat": 22.1987, "lon": 113.5439},
    {"name": "台湾省", "type": "province", "lat": 25.0330, "lon": 121.5654},
]

# 主要城市
CITIES = [
    # 省会城市
    {"name": "石家庄", "type": "city", "lat": 38.0428, "lon": 114.5149, "province": "河北省"},
    {"name": "太原", "type": "city", "lat": 37.8706, "lon": 112.5489, "province": "山西省"},
    {"name": "呼和浩特", "type": "city", "lat": 40.8414, "lon": 111.7519, "province": "内蒙古自治区"},
    {"name": "沈阳", "type": "city", "lat": 41.8057, "lon": 123.4315, "province": "辽宁省"},
    {"name": "长春", "type": "city", "lat": 43.8868, "lon": 125.3245, "province": "吉林省"},
    {"name": "哈尔滨", "type": "city", "lat": 45.8038, "lon": 126.5340, "province": "黑龙江省"},
    {"name": "南京", "type": "city", "lat": 32.0603, "lon": 118.7969, "province": "江苏省"},
    {"name": "杭州", "type": "city", "lat": 30.2741, "lon": 120.1551, "province": "浙江省"},
    {"name": "合肥", "type": "city", "lat": 31.8206, "lon": 117.2272, "province": "安徽省"},
    {"name": "福州", "type": "city", "lat": 26.0745, "lon": 119.2965, "province": "福建省"},
    {"name": "南昌", "type": "city", "lat": 28.6769, "lon": 115.9099, "province": "江西省"},
    {"name": "济南", "type": "city", "lat": 36.6512, "lon": 117.1205, "province": "山东省"},
    {"name": "郑州", "type": "city", "lat": 34.7466, "lon": 113.6253, "province": "河南省"},
    {"name": "武汉", "type": "city", "lat": 30.5928, "lon": 114.3055, "province": "湖北省"},
    {"name": "长沙", "type": "city", "lat": 28.2282, "lon": 112.9388, "province": "湖南省"},
    {"name": "广州", "type": "city", "lat": 23.1291, "lon": 113.2644, "province": "广东省"},
    {"name": "南宁", "type": "city", "lat": 22.8170, "lon": 108.3665, "province": "广西壮族自治区"},
    {"name": "海口", "type": "city", "lat": 20.0440, "lon": 110.1999, "province": "海南省"},
    {"name": "成都", "type": "city", "lat": 30.5728, "lon": 104.0668, "province": "四川省"},
    {"name": "贵阳", "type": "city", "lat": 26.6470, "lon": 106.6302, "province": "贵州省"},
    {"name": "昆明", "type": "city", "lat": 25.0443, "lon": 102.7046, "province": "云南省"},
    {"name": "拉萨", "type": "city", "lat": 29.6524, "lon": 91.1721, "province": "西藏自治区"},
    {"name": "西安", "type": "city", "lat": 34.3416, "lon": 108.9398, "province": "陕西省"},
    {"name": "兰州", "type": "city", "lat": 36.0611, "lon": 103.8343, "province": "甘肃省"},
    {"name": "西宁", "type": "city", "lat": 36.6171, "lon": 101.7782, "province": "青海省"},
    {"name": "银川", "type": "city", "lat": 38.4681, "lon": 106.2731, "province": "宁夏回族自治区"},
    {"name": "乌鲁木齐", "type": "city", "lat": 43.8256, "lon": 87.6168, "province": "新疆维吾尔自治区"},

    # 重要城市
    {"name": "深圳", "type": "city", "lat": 22.5431, "lon": 114.0579, "province": "广东省"},
    {"name": "珠海", "type": "city", "lat": 22.2769, "lon": 113.5678, "province": "广东省"},
    {"name": "汕头", "type": "city", "lat": 23.3540, "lon": 116.6820, "province": "广东省"},
    {"name": "苏州", "type": "city", "lat": 31.2989, "lon": 120.5853, "province": "江苏省"},
    {"name": "无锡", "type": "city", "lat": 31.4912, "lon": 120.3119, "province": "江苏省"},
    {"name": "宁波", "type": "city", "lat": 29.8683, "lon": 121.5440, "province": "浙江省"},
    {"name": "厦门", "type": "city", "lat": 24.4798, "lon": 118.0894, "province": "福建省"},
    {"name": "青岛", "type": "city", "lat": 36.0671, "lon": 120.3826, "province": "山东省"},
    {"name": "大连", "type": "city", "lat": 38.9140, "lon": 121.6147, "province": "辽宁省"},
]

# 主要河流
RIVERS = [
    {"name": "长江", "type": "river", "length": 6300, "origin": "青藏高原", "mouth": "东海"},
    {"name": "黄河", "type": "river", "length": 5464, "origin": "巴颜喀拉山", "mouth": "渤海"},
    {"name": "珠江", "type": "river", "length": 2320, "origin": "云贵高原", "mouth": "南海"},
    {"name": "淮河", "type": "river", "length": 1000, "origin": "河南桐柏山", "mouth": "洪泽湖"},
    {"name": "海河", "type": "river", "length": 1050, "origin": "太行山", "mouth": "渤海"},
    {"name": "辽河", "type": "river", "length": 1430, "origin": "河北", "mouth": "渤海"},
    {"name": "松花江", "type": "river", "length": 1927, "origin": "长白山", "mouth": "黑龙江"},
    {"name": "雅鲁藏布江", "type": "river", "length": 2057, "origin": "喜马拉雅山", "mouth": "孟加拉湾"},
]

# 主要山脉
MOUNTAINS = [
    {"name": "喜马拉雅山脉", "type": "mountain_range", "highest_peak": "珠穆朗玛峰", "elevation": 8848},
    {"name": "昆仑山脉", "type": "mountain_range", "highest_peak": "公格尔山", "elevation": 7649},
    {"name": "天山山脉", "type": "mountain_range", "highest_peak": "托木尔峰", "elevation": 7443},
    {"name": "秦岭", "type": "mountain_range", "highest_peak": "太白山", "elevation": 3771},
    {"name": "大兴安岭", "type": "mountain_range", "highest_peak": "黄岗梁", "elevation": 2029},
    {"name": "太行山脉", "type": "mountain_range", "highest_peak": "小五台山", "elevation": 2882},
    {"name": "武夷山脉", "type": "mountain_range", "highest_peak": "黄岗山", "elevation": 2158},
]

# 主要湖泊
LAKES = [
    {"name": "青海湖", "type": "lake", "area": 4583, "province": "青海省"},
    {"name": "鄱阳湖", "type": "lake", "area": 3150, "province": "江西省"},
    {"name": "洞庭湖", "type": "lake", "area": 2625, "province": "湖南省"},
    {"name": "太湖", "type": "lake", "area": 2250, "province": "江苏省"},
    {"name": "呼伦湖", "type": "lake", "area": 2339, "province": "内蒙古自治区"},
    {"name": "纳木错", "type": "lake", "area": 1920, "province": "西藏自治区"},
]


class EntityDatabase:
    """地理实体数据库"""

    def __init__(self):
        """初始化实体数据库"""
        self.entities = {
            "provinces": PROVINCES,
            "cities": CITIES,
            "rivers": RIVERS,
            "mountains": MOUNTAINS,
            "lakes": LAKES
        }

    def get_all_entities(self) -> List[Dict[str, Any]]:
        """获取所有实体"""
        all_entities = []
        for entity_type, entities in self.entities.items():
            for entity in entities:
                entity["category"] = entity_type
                all_entities.append(entity)
        return all_entities

    def get_entities_by_type(self, entity_type: str) -> List[Dict[str, Any]]:
        """按类型获取实体"""
        return self.entities.get(entity_type, [])

    def get_entities_with_coords(self) -> List[Dict[str, Any]]:
        """获取有坐标的实体（用于生成方向/度量关系）"""
        entities_with_coords = []
        for entity_type in ["provinces", "cities"]:
            entities_with_coords.extend(self.entities[entity_type])
        return entities_with_coords

    def get_entity_by_name(self, name: str) -> Dict[str, Any]:
        """按名称查找实体"""
        for entity_type, entities in self.entities.items():
            for entity in entities:
                if entity["name"] == name:
                    return entity
        return None

    def random_pair(self, entity_type: str = None) -> tuple:
        """随机选择一对实体"""
        import random

        if entity_type:
            entities = self.get_entities_by_type(entity_type)
        else:
            entities = self.get_all_entities()

        return random.sample(entities, 2)

    def statistics(self) -> Dict[str, int]:
        """返回数据库统计信息"""
        return {
            entity_type: len(entities)
            for entity_type, entities in self.entities.items()
        }

    def save_to_file(self, output_path: str):
        """保存数据库到文件"""
        all_entities = self.get_all_entities()
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_entities, f, indent=2, ensure_ascii=False)
        print(f"✅ 实体数据库已保存到: {output_path}")

    @classmethod
    def load_from_file(cls, input_path: str) -> 'EntityDatabase':
        """从文件加载数据库"""
        with open(input_path, 'r', encoding='utf-8') as f:
            entities = json.load(f)

        db = cls()
        # 重新分类
        for entity in entities:
            category = entity.pop("category", None)
            if category and category in db.entities:
                db.entities[category].append(entity)

        return db


if __name__ == "__main__":
    # 创建数据库
    db = EntityDatabase()

    # 打印统计信息
    print("="*60)
    print("地理实体数据库统计")
    print("="*60)
    stats = db.statistics()
    for entity_type, count in stats.items():
        print(f"{entity_type}: {count}")
    print(f"总计: {sum(stats.values())} 个实体")
    print("="*60)

    # 保存到文件
    db.save_to_file("data/geosr_chain/entity_database.json")

    # 测试随机选择
    print("\n测试随机选择实体对:")
    for i in range(5):
        entity1, entity2 = db.random_pair("cities")
        print(f"{i+1}. {entity1['name']} ({entity1['lat']}°N, {entity1['lon']}°E) "
              f"- {entity2['name']} ({entity2['lat']}°N, {entity2['lon']}°E)")
```

**验证标准**:
- [ ] 总实体数≥500
- [ ] 包含所有必要类型（省、市、河、山、湖）
- [ ] 坐标准确率>99%（抽查20个）
- [ ] 数据保存成功

---

### 任务3.3：生成种子数据（5,000条）

**目标**: 使用GPT-4生成高质量种子数据

**创建数据生成脚本** (`scripts/generate_training_data.py`):

```python
"""
使用GPT-4生成训练数据
"""
import os
import json
import random
from typing import List, Dict, Any
from openai import OpenAI
from data.entity_database import EntityDatabase
from data.prompts import PromptTemplate
from tqdm import tqdm


class GeoDataGenerator:
    """地理空间推理数据生成器"""

    def __init__(self, api_key: str = None):
        """
        Args:
            api_key: OpenAI API Key（如果为None，从环境变量读取）
        """
        if not api_key:
            api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError("请设置OPENAI_API_KEY环境变量")

        self.client = OpenAI(api_key=api_key)
        self.entity_db = EntityDatabase()
        self.prompt_template = PromptTemplate()

    def generate_directional_data(self, num_samples: int = 100) -> List[Dict]:
        """生成方向关系数据"""
        print(f"\n{'='*60}")
        print(f"生成方向关系数据: {num_samples}条")
        print(f"{'='*60}")

        results = []
        entities = self.entity_db.get_entities_with_coords()

        for i in tqdm(range(num_samples), desc="生成方向关系"):
            # 随机选择两个实体
            entity1, entity2 = random.sample(entities, 2)

            # 构造Prompt
            prompt = self.prompt_template.get_prompt(
                "directional",
                name1=entity1["name"],
                lat1=entity1["lat"],
                lon1=entity1["lon"],
                name2=entity2["name"],
                lat2=entity2["lat"],
                lon2=entity2["lon"]
            )

            # 调用GPT-4生成
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "你是一个专业的地理空间推理专家。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=1000
                )

                generated_text = response.choices[0].message.content

                # 解析JSON
                generated_json = json.loads(generated_text)
                results.append(generated_json)

            except Exception as e:
                print(f"\n❌ 生成失败 (样本 {i+1}): {e}")
                continue

        return results

    def generate_topological_data(self, num_samples: int = 100) -> List[Dict]:
        """生成拓扑关系数据"""
        print(f"\n{'='*60}")
        print(f"生成拓扑关系数据: {num_samples}条")
        print(f"{'='*60}")

        results = []

        # 关系类型和对应实体
        relation_types = [
            ("河流", "province", "穿过"),
            ("城市", "province", "位于"),
        ]

        for i in tqdm(range(num_samples), desc="生成拓扑关系"):
            # 随机选择关系类型
            relation_type = random.choice(relation_types)

            # 选择实体
            if relation_type[0] == "河流":
                entity1 = random.choice(self.entity_db.get_entities_by_type("rivers"))
                entity2 = random.choice(self.entity_db.get_entities_by_type("provinces"))
            else:
                entity1 = random.choice(self.entity_db.get_entities_by_type("cities"))
                entity2 = random.choice(self.entity_db.get_entities_by_type("provinces"))

            # 构造Prompt
            prompt = self.prompt_template.get_prompt(
                "topological",
                name1=entity1["name"],
                type1=entity1.get("type", "未知"),
                name2=entity2["name"],
                type2=entity2.get("type", "未知"),
                relation_type=relation_type[2]
            )

            # 调用GPT-4
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "你是一个专业的地理空间推理专家。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=1000
                )

                generated_text = response.choices[0].message.content
                generated_json = json.loads(generated_text)
                results.append(generated_json)

            except Exception as e:
                print(f"\n❌ 生成失败 (样本 {i+1}): {e}")
                continue

        return results

    def generate_metric_data(self, num_samples: int = 100) -> List[Dict]:
        """生成度量关系数据"""
        print(f"\n{'='*60}")
        print(f"生成度量关系数据: {num_samples}条")
        print(f"{'='*60}")

        results = []
        entities = self.entity_db.get_entities_with_coords()

        for i in tqdm(range(num_samples), desc="生成度量关系"):
            # 随机选择两个实体
            entity1, entity2 = random.sample(entities, 2)

            # 构造Prompt
            prompt = self.prompt_template.get_prompt(
                "metric",
                name1=entity1["name"],
                lat1=entity1["lat"],
                lon1=entity1["lon"],
                name2=entity2["name"],
                lat2=entity2["lat"],
                lon2=entity2["lon"]
            )

            # 调用GPT-4
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "你是一个专业的地理空间推理专家。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=1000
                )

                generated_text = response.choices[0].message.content
                generated_json = json.loads(generated_text)
                results.append(generated_json)

            except Exception as e:
                print(f"\n❌ 生成失败 (样本 {i+1}): {e}")
                continue

        return results

    def generate_comprehensive_data(self, num_samples: int = 50) -> List[Dict]:
        """生成综合推理数据"""
        print(f"\n{'='*60}")
        print(f"生成综合推理数据: {num_samples}条")
        print(f"{'='*60}")

        results = []
        entities = self.entity_db.get_entities_with_coords()

        for i in tqdm(range(num_samples), desc="生成综合推理"):
            # 随机选择3个实体
            selected_entities = random.sample(entities, 3)
            entities_str = ", ".join([e["name"] for e in selected_entities])

            # 构造Prompt
            prompt = self.prompt_template.get_prompt(
                "comprehensive",
                entities=entities_str,
                num_steps=2
            )

            # 调用GPT-4
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "你是一个专业的地理空间推理专家。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=1500
                )

                generated_text = response.choices[0].message.content
                generated_json = json.loads(generated_text)
                results.append(generated_json)

            except Exception as e:
                print(f"\n❌ 生成失败 (样本 {i+1}): {e}")
                continue

        return results

    def save_results(self, results: List[Dict], output_path: str):
        """保存生成结果"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            for result in results:
                f.write(json.dumps(result, ensure_ascii=False) + '\n')

        print(f"\n✅ 结果已保存到: {output_path}")
        print(f"   总计: {len(results)} 条")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="生成地理空间推理训练数据")
    parser.add_argument("--relation_type", type=str, default="all",
                        choices=["directional", "topological", "metric", "comprehensive", "all"],
                        help="空间关系类型")
    parser.add_argument("--num_samples", type=int, default=100,
                        help="生成样本数量")
    parser.add_argument("--output_dir", type=str, default="data/geosr_chain",
                        help="输出目录")
    parser.add_argument("--api_key", type=str, default=None,
                        help="OpenAI API Key")

    args = parser.parse_args()

    # 创建生成器
    generator = GeoDataGenerator(api_key=args.api_key)

    # 生成数据
    if args.relation_type == "all":
        # 生成所有类型
        all_results = []

        directional = generator.generate_directional_data(args.num_samples)
        all_results.extend(directional)
        generator.save_results(directional, f"{args.output_dir}/directional_train.jsonl")

        topological = generator.generate_topological_data(int(args.num_samples * 0.75))
        all_results.extend(topological)
        generator.save_results(topological, f"{args.output_dir}/topological_train.jsonl")

        metric = generator.generate_metric_data(int(args.num_samples * 0.5))
        all_results.extend(metric)
        generator.save_results(metric, f"{args.output_dir}/metric_train.jsonl")

        comprehensive = generator.generate_comprehensive_data(int(args.num_samples * 0.25))
        all_results.extend(comprehensive)
        generator.save_results(comprehensive, f"{args.output_dir}/comprehensive_train.jsonl")

        # 保存合并数据
        generator.save_results(all_results, f"{args.output_dir}/geosr_chain_v1.jsonl")

    else:
        # 生成特定类型
        if args.relation_type == "directional":
            results = generator.generate_directional_data(args.num_samples)
        elif args.relation_type == "topological":
            results = generator.generate_topological_data(args.num_samples)
        elif args.relation_type == "metric":
            results = generator.generate_metric_data(args.num_samples)
        elif args.relation_type == "comprehensive":
            results = generator.generate_comprehensive_data(args.num_samples)

        output_path = f"{args.output_dir}/{args.relation_type}_train.jsonl"
        generator.save_results(results, output_path)


if __name__ == "__main__":
    main()
```

**运行数据生成**:

```bash
# 设置API Key
export OPENAI_API_KEY="your_api_key_here"

# 生成所有类型（总计2,500条）
python scripts/generate_training_data.py \
    --relation_type all \
    --num_samples 1000 \
    --output_dir data/geosr_chain

# 分批生成以避免API限流
# 第一批：方向关系
python scripts/generate_training_data.py \
    --relation_type directional \
    --num_samples 1000

# 第二批：拓扑关系
python scripts/generate_training_data.py \
    --relation_type topological \
    --num_samples 750

# 第三批：度量关系
python scripts/generate_training_data.py \
    --relation_type metric \
    --num_samples 500

# 第四批：综合推理
python scripts/generate_training_data.py \
    --relation_type comprehensive \
    --num_samples 250

# 合并所有数据
cat data/geosr_chain/*_train.jsonl > data/geosr_chain/geosr_chain_v1.jsonl
```

**创建数据验证脚本** (`scripts/validate_data.py`):

```python
"""
验证生成的数据质量
"""
import json
import os
from typing import List, Dict
from collections import Counter


def validate_jsonl(file_path: str) -> tuple:
    """
    验证JSONL文件格式和内容

    Returns:
        (valid_count, invalid_count, errors)
    """
    valid_count = 0
    invalid_count = 0
    errors = []

    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)

                # 检查必要字段
                required_fields = ["question", "answer", "spatial_relation_type"]
                missing_fields = [f for f in required_fields if f not in data]

                if missing_fields:
                    invalid_count += 1
                    errors.append(f"行{line_num}: 缺少字段 {missing_fields}")
                else:
                    valid_count += 1

            except json.JSONDecodeError as e:
                invalid_count += 1
                errors.append(f"行{line_num}: JSON解析错误 - {e}")

    return valid_count, invalid_count, errors


def analyze_relation_types(file_path: str):
    """分析空间关系类型分布"""
    relation_types = []

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            data = json.loads(line)
            relation_types.append(data.get("spatial_relation_type", "unknown"))

    # 统计
    counter = Counter(relation_types)

    print("\n空间关系类型分布:")
    print("="*60)
    for rel_type, count in sorted(counter.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / len(relation_types)) * 100
        print(f"{rel_type:20s}: {count:5d} ({percentage:5.2f}%)")
    print("="*60)
    print(f"总计: {len(relation_types)} 条")


def sample_questions(file_path: str, num_samples: int = 10):
    """随机抽样显示问题"""
    import random

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    samples = random.sample(lines, min(num_samples, len(lines)))

    print(f"\n随机抽样 {len(samples)} 条数据:")
    print("="*60)

    for i, line in enumerate(samples, 1):
        data = json.loads(line)
        print(f"\n[样本 {i}]")
        print(f"类型: {data.get('spatial_relation_type', 'unknown')}")
        print(f"问题: {data.get('question', 'N/A')}")
        print(f"答案: {data.get('answer', 'N/A')}")

    print("="*60)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="验证生成的数据质量")
    parser.add_argument("--data_path", type=str,
                        default="data/geosr_chain/geosr_chain_v1.jsonl",
                        help="数据文件路径")
    parser.add_argument("--sample", type=int, default=10,
                        help="抽样显示数量")

    args = parser.parse_args()

    if not os.path.exists(args.data_path):
        print(f"❌ 文件不存在: {args.data_path}")
        return

    print("="*60)
    print("GeoKD-SR 数据验证工具")
    print("="*60)
    print(f"文件: {args.data_path}")

    # 验证格式
    valid, invalid, errors = validate_jsonl(args.data_path)

    print(f"\n✅ 有效数据: {valid}")
    print(f"❌ 无效数据: {invalid}")

    if errors:
        print(f"\n错误详情 (显示前10条):")
        for error in errors[:10]:
            print(f"  - {error}")

    # 分析类型分布
    analyze_relation_types(args.data_path)

    # 抽样显示
    if valid > 0:
        sample_questions(args.data_path, args.sample)


if __name__ == "__main__":
    main()
```

**运行验证**:

```bash
# 验证生成数据
python scripts/validate_data.py \
    --data_path data/geosr_chain/geosr_chain_v1.jsonl \
    --sample 20

# 预期输出:
# ============================================================
# GeoKD-SR 数据验证工具
# ============================================================
# 文件: data/geosr_chain/geosr_chain_v1.jsonl
#
# ✅ 有效数据: 2487
# ❌ 无效数据: 13
#
# 空间关系类型分布:
# ============================================================
# directional         :  1000 (40.21%)
# topological         :   750 (30.16%)
# metric              :   500 (20.11%)
# comprehensive       :   237 ( 9.53%)
# ============================================================
# 总计: 2487 条
```

**人工抽检**:

随机抽取50-100条数据进行人工评估，检查：
- [ ] 问题表述清晰
- [ ] 答案准确无误
- [ ] 推理链合理
- [ ] 空间关系类型标注正确

**验证标准**:
- [ ] 总数据量≥5,000条
- [ ] 格式验证通过率>95%
- [ ] 人工抽检通过率>85%
- [ ] 空间关系类型分布合理

---

## Week 3 总结检查清单

**完成日期**: ___________

**检查项**:
- [ ] 4种Prompt模板设计完成
- [ ] Prompt质量测试通过（>85%）
- [ ] 地理实体库构建完成（≥500个）
- [ ] 生成种子数据≥5,000条
- [ ] 数据验证通过
- [ ] 人工抽检通过

**数据统计**:
- 总数据量: ___________
- 方向关系: ___________
- 拓扑关系: ___________
- 度量关系: ___________
- 综合推理: ___________

**遇到的问题**:
-
-

**备注**:


---

## Week 4：GeoSR-Bench评测框架设计（3月22-31日）

### 任务清单

- [ ] 4.1 设计评测任务
- [ ] 4.2 实现评测器

---

### 任务4.1：设计评测任务

**目标**: 设计全面的评测基准

**评测维度设计**:

```python
"""
GeoSR-Bench评测框架设计
评测维度和任务类型
"""

# 评测维度
EVALUATION_DIMENSIONS = {
    "D1_空间关系理解": {
        "weight": 0.4,
        "subtasks": {
            "方向关系": {"weight": 0.15, "num_questions": 150},
            "拓扑关系": {"weight": 0.15, "num_questions": 150},
            "度量关系": {"weight": 0.10, "num_questions": 100}
        }
    },
    "D2_空间推理能力": {
        "weight": 0.4,
        "subtasks": {
            "单步推理": {"weight": 0.10, "num_questions": 100},
            "多跳推理": {"weight": 0.20, "num_questions": 200},
            "约束求解": {"weight": 0.10, "num_questions": 100}
        }
    },
    "D3_地理知识融合": {
        "weight": 0.2,
        "subtasks": {
            "实体识别": {"weight": 0.05, "num_questions": 50},
            "常识应用": {"weight": 0.10, "num_questions": 100},
            "情境理解": {"weight": 0.05, "num_questions": 50}
        }
    }
}

# 任务类型
TASK_TYPES = {
    "multiple_choice": {
        "name": "选择题",
        "format": "4选1",
        "auto_gradable": True,
        "num_questions": 500
    },
    "fill_blank": {
        "name": "填空题",
        "format": "数值/文本填空",
        "auto_gradable": True,
        "num_questions": 200,
        "tolerance": 50  # 距离容忍误差（公里）
    },
    "true_false": {
        "name": "判断题",
        "format": "真/假判断",
        "auto_gradable": True,
        "num_questions": 150
    },
    "reasoning": {
        "name": "推理题",
        "format": "需展示推理步骤",
        "auto_gradable": False,
        "num_questions": 150
    }
}

# 示例题目
BENCHMARK_EXAMPLES = [
    # D1 - 方向关系
    {
        "id": "D1_DIR_001",
        "dimension": "D1_空间关系理解",
        "task_type": "multiple_choice",
        "question": "北京在上海的什么方向？",
        "options": ["A. 东北", "B. 西北", "C. 东南", "D. 西南"],
        "answer": "B",
        "reasoning": "北京(39.9°N, 116.4°E)，上海(31.2°N, 121.5°E)。北京纬度更高（北方），经度更小（西方），因此是西北方向。"
    },
    # D1 - 拓扑关系
    {
        "id": "D1_TOP_001",
        "dimension": "D1_空间关系理解",
        "task_type": "true_false",
        "question": "长江流经湖北省。",
        "answer": True,
        "reasoning": "长江从西向东流，确实流经湖北省，经过宜昌、武汉等重要城市。"
    },
    # D1 - 度量关系
    {
        "id": "D1_MET_001",
        "dimension": "D1_空间关系理解",
        "task_type": "fill_blank",
        "question": "从北京到上海的直线距离大约是多少公里？（答案在±50公里内算正确）",
        "answer": 1068,
        "tolerance": 50
    },
    # D2 - 单步推理
    {
        "id": "D2_SINGLE_001",
        "dimension": "D2_空间推理能力",
        "task_type": "multiple_choice",
        "question": "如果一个人从广州出发，向北走1000公里，他最可能到达哪个城市附近？",
        "options": ["A. 上海", "B. 武汉", "C. 北京", "D. 西安"],
        "answer": "B",
        "reasoning": "广州(23.1°N)，向北1000公里约相当于9个纬度，到达32°N附近，武汉位于30.6°N，是最接近的选项。"
    },
    # D2 - 多跳推理
    {
        "id": "D2_MULTI_001",
        "dimension": "D2_空间推理能力",
        "task_type": "reasoning",
        "question": "假设一个旅行路线：北京→郑州→武汉→长沙→广州。请分析：(1)整体移动方向是什么？(2)总行程大约多少公里？",
        "answer": {
            "direction": "整体向南移动",
            "distance": "约2000公里"
        },
        "reasoning_steps": [
            "北京到郑州：向西南约650公里",
            "郑州到武汉：向西南约500公里",
            "武汉到长沙": "向西南约350公里",
            "长沙到广州": "向南约500公里",
            "综合：整体向南，总距离约2000公里"
        ]
    },
    # D3 - 地理知识融合
    {
        "id": "D3_KNOWLEDGE_001",
        "dimension": "D3_地理知识融合",
        "task_type": "multiple_choice",
        "question": "泰山位于哪个省份？",
        "options": ["A. 山西省", "B. 河南省", "C. 山东省", "D. 河北省"],
        "answer": "C",
        "reasoning": "泰山是中国五岳之首，位于山东省中部泰安市，是山东省的标志性地理实体。"
    }
]
```

**创建评测基准生成器** (`experiments/generate_benchmark.py`):

```python
"""
GeoSR-Bench评测基准生成器
生成1000道评测题目
"""
import json
import random
from typing import List, Dict
from data.entity_database import EntityDatabase
from data.prompts import PromptTemplate


class GeoSRBenchGenerator:
    """GeoSR-Bench评测基准生成器"""

    def __init__(self):
        self.entity_db = EntityDatabase()
        self.prompt_template = PromptTemplate()
        self.question_id_counter = 1

    def _generate_id(self, dimension: str, task_type: str) -> str:
        """生成题目ID"""
        id_mapping = {
            "directional": "DIR",
            "topological": "TOP",
            "metric": "MET",
            "reasoning": "REA"
        }
        code = id_mapping.get(task_type, "GEN")
        return f"{dimension}_{code}_{self.question_id_counter:04d}"

    def generate_directional_questions(self, num_questions: int = 150) -> List[Dict]:
        """生成方向关系题目（选择题）"""
        print(f"生成方向关系题目: {num_questions}道")

        questions = []
        entities = self.entity_db.get_entities_with_coords()

        for _ in range(num_questions):
            entity1, entity2 = random.sample(entities, 2)

            # 计算真实方向
            lat_diff = entity1["lat"] - entity2["lat"]
            lon_diff = entity1["lon"] - entity2["lon"]

            # 8方向判断
            if lat_diff > 0 and lon_diff > 0:
                correct_direction = "西北"
                options = ["西北", "东北", "西南", "东南"]
            elif lat_diff > 0 and lon_diff < 0:
                correct_direction = "东北"
                options = ["东北", "西北", "西南", "东南"]
            elif lat_diff < 0 and lon_diff > 0:
                correct_direction = "西南"
                options = ["西南", "西北", "东北", "东南"]
            elif lat_diff < 0 and lon_diff < 0:
                correct_direction = "东南"
                options = ["东南", "西北", "东北", "西南"]
            elif lat_diff > 0:
                correct_direction = "西"
                options = ["西", "东", "北", "南"]
            elif lat_diff < 0:
                correct_direction = "东"
                options = ["东", "西", "北", "南"]
            elif lon_diff > 0:
                correct_direction = "北"
                options = ["北", "南", "东", "西"]
            else:
                correct_direction = "南"
                options = ["南", "北", "东", "西"]

            random.shuffle(options)

            question = {
                "id": self._generate_id("D1", "directional"),
                "dimension": "D1_空间关系理解",
                "task_type": "multiple_choice",
                "question": f"{entity1['name']}在{entity2['name']}的什么方向？",
                "options": [f"{chr(65+i)}. {opt}" for i, opt in enumerate(options)],
                "answer": chr(65 + options.index(correct_direction)),
                "entities": [entity1, entity2]
            }

            questions.append(question)
            self.question_id_counter += 1

        return questions

    def generate_topological_questions(self, num_questions: int = 150) -> List[Dict]:
        """生成拓扑关系题目（判断题）"""
        print(f"生成拓扑关系题目: {num_questions}道")

        questions = []

        # 省份-城市包含关系
        for _ in range(num_questions // 2):
            city = random.choice(self.entity_db.get_entities_by_type("cities"))
            correct_province = city.get("province", "").replace("省", "")

            # 随机决定真假
            if random.random() > 0.3:  # 70%真
                question_city = city["name"]
                question_province = correct_province
                answer = True
            else:  # 30%假
                question_city = city["name"]
                other_provinces = [p["name"] for p in self.entity_db.get_entities_by_type("provinces")
                                   if p["name"] != correct_province]
                question_province = random.choice(other_provinces)
                answer = False

            question = {
                "id": self._generate_id("D1", "topological"),
                "dimension": "D1_空间关系理解",
                "task_type": "true_false",
                "question": f"{question_city}位于{question_province}。",
                "answer": answer,
                "entities": [{"name": question_city}, {"name": question_province}]
            }

            questions.append(question)
            self.question_id_counter += 1

        # 河流-省份流经关系
        rivers = [
            ("长江", ["湖北", "湖南", "江西", "安徽", "江苏", "四川", "重庆"]),
            ("黄河", ["青海", "四川", "甘肃", "宁夏", "内蒙古", "陕西", "山西", "河南", "山东"]),
            ("珠江", ["云南", "贵州", "广西", "广东"]),
        ]

        for _ in range(num_questions // 2):
            river, provinces = random.choice(rivers)

            if random.random() > 0.3:  # 70%真
                question_province = random.choice(provinces)
                answer = True
            else:  # 30%假
                all_provinces = [p["name"] for p in self.entity_db.get_entities_by_type("provinces")]
                wrong_provinces = [p for p in all_provinces if p not in provinces]
                question_province = random.choice(wrong_provinces)
                answer = False

            question = {
                "id": self._generate_id("D1", "topological"),
                "dimension": "D1_空间关系理解",
                "task_type": "true_false",
                "question": f"{river}流经{question_province}。",
                "answer": answer,
                "entities": [{"name": river}, {"name": question_province}]
            }

            questions.append(question)
            self.question_id_counter += 1

        return questions

    def generate_metric_questions(self, num_questions: int = 100) -> List[Dict]:
        """生成度量关系题目（填空题）"""
        print(f"生成度量关系题目: {num_questions}道")

        questions = []
        entities = self.entity_db.get_entities_with_coords()

        for _ in range(num_questions):
            entity1, entity2 = random.sample(entities, 2)

            # 计算距离（使用Haversine公式）
            from math import radians, sin, cos, sqrt, asin

            lat1, lon1 = radians(entity1["lat"]), radians(entity1["lon"])
            lat2, lon2 = radians(entity2["lat"]), radians(entity2["lon"])

            dlat = lat2 - lat1
            dlon = lon2 - lon1

            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            distance = round(6371 * c)  # 地球半径6371km

            question = {
                "id": self._generate_id("D1", "metric"),
                "dimension": "D1_空间关系理解",
                "task_type": "fill_blank",
                "question": f"从{entity1['name']}到{entity2['name']}的直线距离大约是多少公里？（答案在±50公里内算正确）",
                "answer": distance,
                "tolerance": 50,
                "entities": [entity1, entity2]
            }

            questions.append(question)
            self.question_id_counter += 1

        return questions

    def generate_reasoning_questions(self, num_questions: int = 200) -> List[Dict]:
        """生成推理题目"""
        print(f"生成推理题目: {num_questions}道")

        questions = []

        # 单步推理
        for _ in range(num_questions // 2):
            entities = random.sample(self.entity_db.get_entities_with_coords(), 3)

            # 计算方向
            e1, e2 = entities[0], entities[1]
            lat_diff = e1["lat"] - e2["lat"]
            lon_diff = e1["lon"] - e2["lon"]

            if abs(lat_diff) > abs(lon_diff):
                direction = "南方" if lat_diff < 0 else "北方"
            else:
                direction = "东方" if lon_diff > 0 else "西方"

            question = {
                "id": self._generate_id("D2", "reasoning"),
                "dimension": "D2_空间推理能力",
                "task_type": "multiple_choice",
                "question": f"{e1['name']}相对于{e2['name']}在{direction}。如果从{e2['name']}出发向{direction}走500公里，最可能接近哪里？",
                "options": [
                    f"A. {entities[0]['name']}",
                    f"B. {entities[2]['name']}",
                    f"C. {random.choice(self.entity_db.get_entities_by_type('cities'))['name']}",
                    f"D. {random.choice(self.entity_db.get_entities_by_type('cities'))['name']}"
                ],
                "answer": "A",
                "entities": entities
            }

            questions.append(question)
            self.question_id_counter += 1

        # 多跳推理
        for _ in range(num_questions // 2):
            entities = random.sample(self.entity_db.get_entities_with_coords(), 4)

            question = {
                "id": self._generate_id("D2", "reasoning"),
                "dimension": "D2_空间推理能力",
                "task_type": "reasoning",
                "question": f"分析旅行路线：{entities[0]['name']}→{entities[1]['name']}→{entities[2]['name']}→{entities[3]['name']}。请分析整体移动方向。",
                "answer": "需要根据坐标综合判断",
                "entities": entities,
                "requires_multi_step": True
            }

            questions.append(question)
            self.question_id_counter += 1

        return questions

    def save_benchmark(self, questions: List[Dict], output_path: str):
        """保存评测基准"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(questions, f, indent=2, ensure_ascii=False)

        print(f"\n✅ 评测基准已保存到: {output_path}")
        print(f"   总计: {len(questions)} 道题目")

        # 统计
        task_types = {}
        for q in questions:
            tt = q["task_type"]
            task_types[tt] = task_types.get(tt, 0) + 1

        print("\n题目类型分布:")
        for tt, count in sorted(task_types.items()):
            print(f"  {tt}: {count}")


if __name__ == "__main__":
    import os

    generator = GeoSRBenchGenerator()

    all_questions = []

    # 生成各类题目
    directional = generator.generate_directional_questions(150)
    all_questions.extend(directional)

    topological = generator.generate_topological_questions(150)
    all_questions.extend(topological)

    metric = generator.generate_metric_questions(100)
    all_questions.extend(metric)

    reasoning = generator.generate_reasoning_questions(200)
    all_questions.extend(reasoning)

    # 保存
    generator.save_benchmark(all_questions, "data/geosr_bench/geosr_bench_v1.json")
```

**运行生成器**:

```bash
python experiments/generate_benchmark.py
```

---

### 任务4.2：实现评测器

**创建评测器** (`experiments/evaluation.py`):

```python
"""
GeoSR-Bench评测器
"""
import json
import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from typing import List, Dict, Any
from tqdm import tqdm


class GeoSRBenchEvaluator:
    """GeoSR-Bench评测器"""

    def __init__(self, model, tokenizer, device="cuda"):
        self.model = model.to(device).eval()
        self.tokenizer = tokenizer
        self.device = device

    def evaluate_multiple_choice(self, question: Dict) -> Dict:
        """评估选择题"""
        prompt = f"{question['question']}\n"
        for i, option in enumerate(question['options']):
            prompt += f"{option}\n"
        prompt += "答案："

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=10,
                temperature=0.1,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id
            )

        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        predicted = response.split("答案：")[-1].strip()[0]  # 提取A/B/C/D

        # 判断正确性
        is_correct = predicted == question['answer']

        return {
            "question_id": question['id'],
            "predicted": predicted,
            "ground_truth": question['answer'],
            "is_correct": is_correct,
            "score": 1.0 if is_correct else 0.0
        }

    def evaluate_true_false(self, question: Dict) -> Dict:
        """评估判断题"""
        prompt = f"请判断以下陈述的真假：{question['question']}\n答案（真/假）："

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=5,
                temperature=0.1,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id
            )

        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        answer_part = response.split("答案")[-1]

        # 提取真/假
        predicted = None
        if "真" in answer_part or "对" in answer_part or "正确" in answer_part:
            predicted = True
        elif "假" in answer_part or "错" in answer_part or "不正确" in answer_part:
            predicted = False

        is_correct = predicted == question['answer'] if predicted is not None else False

        return {
            "question_id": question['id'],
            "predicted": predicted,
            "ground_truth": question['answer'],
            "is_correct": is_correct,
            "score": 1.0 if is_correct else 0.0
        }

    def evaluate_fill_blank(self, question: Dict) -> Dict:
        """评估填空题"""
        prompt = f"{question['question']}\n答案："

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=20,
                temperature=0.1,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id
            )

        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        answer_text = response.split("答案：")[-1].strip()

        # 提取数字
        import re
        numbers = re.findall(r'\d+', answer_text)
        if numbers:
            predicted = int(numbers[0])
        else:
            predicted = 0

        # 计算分数（容忍误差）
        tolerance = question.get('tolerance', 50)
        diff = abs(predicted - question['answer'])

        if diff <= tolerance:
            score = 1.0
        elif diff <= tolerance * 2:
            score = 0.5
        else:
            score = 0.0

        return {
            "question_id": question['id'],
            "predicted": predicted,
            "ground_truth": question['answer'],
            "difference": diff,
            "score": score
        }

    def evaluate_reasoning(self, question: Dict) -> Dict:
        """评估推理题（简化版）"""
        prompt = f"{question['question']}\n请给出答案和推理过程："

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=200,
                temperature=0.7,
                do_sample=True,
                top_p=0.9,
                pad_token_id=self.tokenizer.eos_token_id
            )

        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        answer_text = response.split("推理过程")[-1].strip()

        # 简化评估：检查是否包含关键词
        # 实际应用中需要更复杂的评估或人工评估
        return {
            "question_id": question['id'],
            "response": answer_text,
            "score": 0.5,  # 推理题需要人工评估，这里给默认分数
            "requires_human_evaluation": True
        }

    def evaluate_benchmark(self, benchmark_path: str) -> Dict:
        """评估整个评测基准"""
        # 加载评测基准
        with open(benchmark_path, 'r', encoding='utf-8') as f:
            questions = json.load(f)

        print(f"\n{'='*60}")
        print(f"GeoSR-Bench 评测")
        print(f"{'='*60}")
        print(f"总题数: {len(questions)}\n")

        results = []

        # 按任务类型分组
        task_type_counts = {}
        for q in questions:
            tt = q['task_type']
            task_type_counts[tt] = task_type_counts.get(tt, 0) + 1

        print("题目类型分布:")
        for tt, count in sorted(task_type_counts.items()):
            print(f"  {tt}: {count}")
        print()

        # 逐题评估
        for question in tqdm(questions, desc="评测"):
            task_type = question['task_type']

            if task_type == "multiple_choice":
                result = self.evaluate_multiple_choice(question)
            elif task_type == "true_false":
                result = self.evaluate_true_false(question)
            elif task_type == "fill_blank":
                result = self.evaluate_fill_blank(question)
            elif task_type == "reasoning":
                result = self.evaluate_reasoning(question)
            else:
                result = {"question_id": question['id'], "score": 0.0}

            results.append(result)

        # 统计结果
        total_score = sum(r['score'] for r in results)
        max_score = len(results)
        overall_accuracy = total_score / max_score if max_score > 0 else 0.0

        # 按任务类型统计
        task_type_scores = {}
        for result, question in zip(results, questions):
            tt = question['task_type']
            if tt not in task_type_scores:
                task_type_scores[tt] = {"score": 0.0, "count": 0}

            task_type_scores[tt]["score"] += result['score']
            task_type_scores[tt]["count"] += 1

        # 打印结果
        print(f"\n{'='*60}")
        print("评测结果")
        print(f"{'='*60}")
        print(f"总体准确率: {overall_accuracy:.2%}")

        print("\n按任务类型:")
        for tt in sorted(task_type_scores.keys()):
            stats = task_type_scores[tt]
            acc = stats['score'] / stats['count'] if stats['count'] > 0 else 0.0
            print(f"  {tt:20s}: {acc:.2%} ({stats['score']:.1f}/{stats['count']})")

        print(f"{'='*60}\n")

        return {
            "overall_accuracy": overall_accuracy,
            "task_type_scores": task_type_scores,
            "detailed_results": results
        }


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=str, required=True,
                        help="模型检查点路径")
    parser.add_argument("--benchmark", type=str,
                        default="data/geosr_bench/geosr_bench_v1.json",
                        help="评测基准路径")
    parser.add_argument("--output", type=str,
                        default="results/evaluation_results.json",
                        help="结果输出路径")

    args = parser.parse_args()

    # 加载模型
    print("加载模型...")
    tokenizer = AutoTokenizer.from_pretrained(
        "D:/30_keyan/GeoKD-SR/models/Qwen2.5-1.5B-Instruct",
        trust_remote_code=True
    )
    model = AutoModelForCausalLM.from_pretrained(
        "D:/30_keyan/GeoKD-SR/models/Qwen2.5-1.5B-Instruct",
        trust_remote_code=True,
        torch_dtype="auto"
    )

    # 加载检查点
    if args.checkpoint:
        print(f"加载检查点: {args.checkpoint}")
        checkpoint = torch.load(args.checkpoint, map_location="cuda")
        model.load_state_dict(checkpoint["student_model_state_dict"])

    # 创建评估器
    evaluator = GeoSRBenchEvaluator(model, tokenizer)

    # 评测
    results = evaluator.evaluate_benchmark(args.benchmark)

    # 保存结果
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"✅ 结果已保存到: {args.output}")


if __name__ == "__main__":
    main()
```

**运行评测**:

```bash
# 评测baseline模型
python experiments/evaluation.py \
    --checkpoint checkpoints/baseline/best_model_epoch_1.pt \
    --benchmark data/geosr_bench/geosr_bench_v1.json \
    --output results/baseline_geosr_bench_results.json
```

**验证标准**:
- [ ] 评测基准包含1000题
- [ ] 评测器自动评分85%+题目
- [ ] 生成格式规范的报告
- [ ] Baseline模型达到预期性能

---

## Week 4 总结检查清单

**完成日期**: ___________

**检查项**:
- [ ] 评测维度设计完成（D1/D2/D3）
- [ ] 生成1000道评测题目
- [ ] 实现自动评测器
- [ ] Baseline模型评测完成
- [ ] 生成评测报告

**评测结果**:
- 总体准确率: ___________
- 选择题准确率: ___________
- 判断题准确率: ___________
- 填空题准确率: ___________

**遇到的问题**:
-
-

**备注**:


---

# 第一阶段总结（3月底里程碑）

## 完成状态

### Week 1 ✅
- [x] 项目目录结构建立
- [x] Python环境配置完成
- [x] 教师和学生模型下载
- [x] 基线数据准备

### Week 2 ✅
- [x] 标准KL蒸馏实现
- [x] 基线训练完成
- [x] 学生达到教师60%+性能

### Week 3 ✅
- [x] 数据生成Prompt设计
- [x] 地理实体库构建（500+）
- [x] 种子数据生成（5,000+）

### Week 4 ✅
- [x] GeoSR-Bench评测框架
- [x] 1000道评测题目
- [x] 自动评测器实现

## 里程碑达成

- ✅ 基线代码运行正常
- ✅ 学生达到教师65%性能
- ✅ GeoSR-Chain V1（5,000条）
- ✅ GeoSR-Bench V1（1,000题）

## 下一步（4月）

- Week 5：空间关系识别模块
- Week 6：空间关系感知损失实现
- Week 7：对比实验
- Week 8：数据扩充至80k

---

**文档版本**: V1.0
**创建日期**: 2026-03-01
**最后更新**: 2026-03-01
