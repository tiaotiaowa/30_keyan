# GeoKD-SR 阿里云PAI环境配置文档

**最后更新**: 2026年3月1日
**平台**: 阿里云PAI-DSW

---

## 1. 硬件配置

| 项目 | 配置 |
|------|------|
| GPU | NVIDIA A10 (24GB VRAM) |
| CUDA | 12.4 |
| CPU | Intel Xeon Platinum 8369B (8核) |
| 内存 | 29GB |
| 磁盘 | 98GB (可用94GB) |
| OS | Ubuntu 22.04.4 LTS |

---

## 2. 软件环境

| 组件 | 版本 | 状态 |
|------|------|------|
| Python | 3.12.12 | ✅ |
| PyTorch | 2.6.0+cu124 | ✅ CUDA支持正常 |
| TorchVision | 0.21.0+cu124 | ✅ |
| TorchAudio | 2.6.0+cu124 | ✅ |
| Triton | 3.2.0 | ✅ |
| NumPy | 2.3.3 | ✅ |

---

## 3. 快速开始

### 3.1 安装依赖

```bash
cd /home/nihao/30_keyan/30_keyan/GeoKD-SR
bash setup_pai_env.sh
```

### 3.2 验证环境

```bash
python verify_env.py
```

### 3.3 测试模型加载

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-1.5B-Instruct",
    device_map="auto"
)
print("✓ 模型加载成功")
```

---

## 4. 完整依赖列表

### 4.1 已安装（PAI预装）

- torch>=2.6.0
- torchvision>=0.21.0
- torchaudio>=2.6.0
- triton>=3.2.0
- numpy>=2.3.3

### 4.2 需要安装

#### 核心依赖 (关键)
| 包名 | 版本要求 | 用途 |
|------|----------|------|
| transformers | >=4.37.0 | HuggingFace模型 |
| huggingface-hub | >=0.20.0 | 模型下载 |
| accelerate | >=0.25.0 | 分布式训练 |
| safetensors | >=0.4.0 | 安全模型格式 |
| tqdm | >=4.66.0 | 进度条 |

#### 训练依赖
| 包名 | 版本要求 | 用途 |
|------|----------|------|
| peft | >=0.7.0 | LoRA/AdaLoRA |
| datasets | >=2.15.0 | 数据集处理 |
| bitsandbytes | >=0.41.0 | 8bit量化 |

#### 数据处理
| 包名 | 版本要求 | 用途 |
|------|----------|------|
| pandas | >=2.0.0 | 数据处理 |
| scipy | >=1.10.0 | 科学计算 |
| scikit-learn | >=1.3.0 | 机器学习 |

#### 空间计算
| 包名 | 版本要求 | 用途 |
|------|----------|------|
| shapely | >=2.0.2 | 空间计算 |
| geopy | >=2.4.1 | 地理编码 |
| pyproj | >=3.6.1 | 坐标转换 |

#### 可视化与实验
| 包名 | 版本要求 | 用途 |
|------|----------|------|
| matplotlib | >=3.7.0 | 可视化 |
| seaborn | >=0.12.0 | 可视化 |
| wandb | >=0.15.0 | 实验跟踪 |
| tensorboard | >=2.14.0 | 可视化 |

---

## 5. 关键配置说明

### 5.1 HuggingFace镜像配置

由于国内网络环境，需要设置HuggingFace镜像：

```bash
# 临时设置（推荐）
export HF_ENDPOINT=https://hf-mirror.com

# 永久设置（添加到~/.bashrc）
echo 'export HF_ENDPOINT=https://hf-mirror.com' >> ~/.bashrc
source ~/.bashrc
```

### 5.2 GPU显存优化建议

A10 (24GB) 显存配置建议：

```python
from transformers import TrainingArguments

training_args = TrainingArguments(
    per_device_train_batch_size=4,   # 降低batch size
    gradient_accumulation_steps=4,    # 增加梯度累积
    fp16=True,                        # 使用混合精度
    gradient_checkpointing=True,      # 节省显存
    optim="adafactor",                # 使用内存友好优化器
)
```

### 5.3 模型量化配置

7B模型训练建议使用量化：

```python
from transformers import BitsAndBytesConfig

quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
)
```

---

## 6. 常见问题

### Q1: 模型下载超时
```bash
export HF_ENDPOINT=https://hf-mirror.com
```

### Q2: CUDA内存不足
- 减小batch_size
- 启用gradient_checkpointing
- 使用4bit量化

### Q3: pip安装缓慢
```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <package>
```

---

## 7. 关键文件路径

| 文件 | 路径 |
|------|------|
| 环境文档 | `/home/nihao/30_keyan/30_keyan/ENVIRONMENT.md` |
| 依赖清单 | `/home/nihao/30_keyan/30_keyan/GeoKD-SR/requirements.txt` |
| 安装脚本 | `/home/nihao/30_keyan/30_keyan/GeoKD-SR/setup_pai_env.sh` |
| 验证脚本 | `/home/nihao/30_keyan/30_keyan/GeoKD-SR/verify_env.py` |
| 学生模型 | `/home/nihao/30_keyan/30_keyan/GeoKD-SR/models/Qwen2.5-1.5B-Instruct/` |

---

## 8. 环境与原计划对比

| 项目 | 原计划 | 实际PAI | 状态 |
|------|--------|---------|------|
| Python | 3.10 | 3.12.12 | ✅ 兼容 |
| PyTorch | 2.1.0+cu118 | 2.6.0+cu124 | ✅ 升级 |
| CUDA | 11.8 | 12.4 | ✅ 升级 |
| GPU | A100-40GB | A10-24GB | ⚠️ 降级 |
| Conda | 使用 | 未安装 | 可选 |
