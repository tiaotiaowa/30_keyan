# GeoKD-SR 数据下载总结报告

> **生成时间**: 2026-03-01
> **项目**: GeoKD-SR (地理空间关系推理知识蒸馏)

---

## 📊 数据总览

| 数据类型 | 数量 | 大小 | 状态 |
|---------|------|------|------|
| **地理实体数据库** | 168个实体 | ~50KB | ✅ 完成 |
| **GeoSR-Bench评测基准** | 900道题目 | ~500KB | ✅ 完成 |
| **Qwen2.5模型** | 2个模型 | ~17GB | 🔄 待下载 |

---

## ✅ 已完成数据

### 1. 地理实体数据库

**文件位置**: `data/geosr_chain/entity_database.json`

**数据统计**:
- 省级行政区: 34个
- 主要城市: 86个
- 主要河流: 18条
- 主要山脉: 15座
- 主要湖泊: 15个

**数据格式**:
```json
{
  "name": "北京",
  "type": "municipality",
  "lat": 39.9042,
  "lon": 116.4074,
  "category": "provinces"
}
```

**实体列表**:
- **4个直辖市**: 北京、上海、天津、重庆
- **23个省**: 河北、山西、辽宁、吉林、黑龙江、江苏、浙江、安徽、福建、江西、山东、河南、湖北、湖南、广东、海南、四川、贵州、云南、陕西、甘肃、青海、台湾
- **5个自治区**: 内蒙古、广西、西藏、宁夏、新疆
- **2个特别行政区**: 香港、澳门
- **重要城市**: 包括所有省会城市及深圳、苏州、宁波、厦门、青岛、大连等重要城市
- **主要河流**: 长江、黄河、珠江、淮河、海河、辽河、松花江等
- **主要山脉**: 喜马拉雅山脉、昆仑山脉、天山山脉、秦岭等
- **主要湖泊**: 青海湖、鄱阳湖、洞庭湖、太湖、呼伦湖等

---

### 2. GeoSR-Bench评测基准

**文件位置**: `data/geosr_bench/geosr_bench_v1.json`

**题目分布**:

#### 按任务类型分类
| 任务类型 | 数量 | 占比 |
|---------|------|------|
| 选择题 (multiple_choice) | 550题 | 61.1% |
| 判断题 (true_false) | 150题 | 16.7% |
| 填空题 (fill_blank) | 100题 | 11.1% |
| 推理题 (reasoning) | 100题 | 11.1% |

#### 按评测维度分类
| 评测维度 | 数量 | 占比 |
|---------|------|------|
| D1: 空间关系理解 | 400题 | 44.4% |
| D2: 空间推理能力 | 200题 | 22.2% |
| D3: 地理知识融合 | 300题 | 33.3% |

**题目示例**:

##### 选择题 (Directional)
```json
{
  "id": "D1_DIR_0001",
  "dimension": "D1_Spatial_Relation_Understanding",
  "task_type": "multiple_choice",
  "question": "Beijing is in which direction of Shanghai?",
  "question_cn": "北京在上海的什么方向？",
  "options": ["A. North", "B. Northwest", "C. Southeast", "D. Southwest"],
  "answer": "B",
  "entities": ["Beijing", "Shanghai"]
}
```

##### 判断题 (Topological)
```json
{
  "id": "D1_TOP_0158",
  "dimension": "D1_Spatial_Relation_Understanding",
  "task_type": "true_false",
  "question": "The Yangtze River flows through Hubei Province.",
  "question_cn": "长江流经湖北省。",
  "answer": true,
  "entities": ["Yangtze River", "Hubei Province"]
}
```

##### 填空题 (Metric)
```json
{
  "id": "D1_MET_0001",
  "dimension": "D1_Spatial_Relation_Understanding",
  "task_type": "fill_blank",
  "question": "What is the straight-line distance from Beijing to Shanghai (in km)?",
  "question_cn": "从北京到上海的直线距离大约是多少公里？",
  "answer": 1068,
  "tolerance": 50,
  "entities": ["Beijing", "Shanghai"]
}
```

##### 推理题 (Reasoning)
```json
{
  "id": "D2_REA_0597",
  "dimension": "D2_Spatial_Reasoning",
  "task_type": "reasoning",
  "question": "Analyze this travel route: Chengde -> Ningbo -> Guiyang -> Shijiazhuang. What is the overall direction of movement?",
  "question_cn": "分析旅行路线：承德→宁波→贵阳→石家庄。整体移动方向是什么？",
  "answer": "Overall moving to the West",
  "answer_cn": "整体向西方向移动",
  "entities": ["承德", "宁波", "贵阳", "石家庄"],
  "requires_multi_step": true
}
```

---

## 🔄 待下载数据

### Qwen2.5系列模型

**下载脚本**: `scripts/download_models.py`

**模型列表**:
1. **Qwen2.5-7B-Instruct** (教师模型)
   - 大小: ~14GB
   - 仓库: `Qwen/Qwen2.5-7B-Instruct`
   - 保存位置: `models/Qwen2.5-7B-Instruct/`

2. **Qwen2.5-1.5B-Instruct** (学生模型)
   - 大小: ~3GB
   - 仓库: `Qwen/Qwen2.5-1.5B-Instruct`
   - 保存位置: `models/Qwen2.5-1.5B-Instruct/`

**下载方法**:

#### 方法1: 直接运行下载脚本
```bash
cd D:/30_keyan/GeoKD-SR
python scripts/download_models.py
```

#### 方法2: 使用镜像加速（推荐国内用户）
```bash
# 设置镜像
export HF_ENDPOINT=https://hf-mirror.com

# 运行下载
python scripts/download_models.py
```

#### 方法3: 手动下载
1. 访问 https://huggingface.co/Qwen/Qwen2.5-7B-Instruct
2. 点击 "Files and versions"
3. 下载所有文件到 `models/Qwen2.5-7B-Instruct/`
4. 重复步骤1-3下载1.5B模型

**预计下载时间**: 30-90分钟（取决于网速）

**磁盘空间需求**: 至少20GB可用空间

---

## 📁 文件结构

```
D:/30_keyan/GeoKD-SR/
├── data/
│   ├── geosr_chain/
│   │   └── entity_database.json          (168个实体, ~50KB)
│   └── geosr_bench/
│       └── geosr_bench_v1.json           (900道题目, ~500KB)
├── models/
│   ├── Qwen2.5-7B-Instruct/              (待下载, ~14GB)
│   └── Qwen2.5-1.5B-Instruct/            (待下载, ~3GB)
├── scripts/
│   └── download_models.py                (下载脚本)
├── experiments/
│   └── generate_benchmark.py             (评测基准生成器)
└── data/
    └── entity_database.py                (实体数据库管理器)
```

---

## 🔍 数据验证

### 地理实体数据库验证

```bash
cd D:/30_keyan/GeoKD-SR
python -c "
import json
with open('data/geosr_chain/entity_database.json', 'r', encoding='utf-8') as f:
    entities = json.load(f)

print(f'Total entities: {len(entities)}')
categories = {}
for e in entities:
    cat = e.get('category', 'unknown')
    categories[cat] = categories.get(cat, 0) + 1

for cat, count in categories.items():
    print(f'  {cat}: {count}')
"
```

**预期输出**:
```
Total entities: 168
  provinces: 34
  cities: 86
  rivers: 18
  mountains: 15
  lakes: 15
```

### 评测基准验证

```bash
python -c "
import json
with open('data/geosr_bench/geosr_bench_v1.json', 'r', encoding='utf-8') as f:
    questions = json.load(f)

print(f'Total questions: {len(questions)}')

# 按类型统计
task_types = {}
for q in questions:
    tt = q['task_type']
    task_types[tt] = task_types.get(tt, 0) + 1

print('\nBy task type:')
for tt, count in sorted(task_types.items()):
    print(f'  {tt}: {count}')

# 按维度统计
dimensions = {}
for q in questions:
    dim = q['dimension']
    dimensions[dim] = dimensions.get(dim, 0) + 1

print('\nBy dimension:')
for dim, count in sorted(dimensions.items()):
    print(f'  {dim}: {count}')
"
```

**预期输出**:
```
Total questions: 900

By task type:
  fill_blank: 100
  multiple_choice: 550
  reasoning: 100
  true_false: 150

By dimension:
  D1_Spatial_Relation_Understanding: 400
  D2_Spatial_Reasoning: 200
  D3_Geographic_Knowledge: 300
```

---

## 🚀 下一步操作

### 1. 下载Qwen模型（必须）

```bash
cd D:/30_keyan/GeoKD-SR

# 使用镜像加速
export HF_ENDPOINT=https://hf-mirror.com
python scripts/download_models.py
```

### 2. 生成训练数据（可选）

如果有OpenAI API密钥，可以生成更多训练数据：

```bash
python scripts/generate_training_data.py \
    --relation_type all \
    --num_samples 1000
```

### 3. 开始基线实验

模型下载完成后，可以开始基线训练：

```bash
python scripts/train_baseline.py \
    --model_name baseline \
    --epochs 3 \
    --batch_size 2 \
    --checkpoint_dir checkpoints/baseline
```

---

## 📞 技术支持

如有问题，请检查：
1. Python环境是否正确配置（Python 3.10+）
2. 依赖包是否安装（transformers, torch, tqdm等）
3. 磁盘空间是否充足（至少20GB）
4. 网络连接是否正常

---

**报告生成时间**: 2026-03-01
**版本**: V1.0
