# Qwen2.5模型下载指南

## 已创建的文件

1. **scripts/download_models.py** - 主要下载脚本
2. **scripts/requirements.txt** - 依赖清单
3. **scripts/run_download.sh** - Linux/Mac快速启动脚本
4. **scripts/run_download.bat** - Windows快速启动脚本

## 环境检查

✓ Python 3.12.7 已安装
✓ PyTorch 2.10.0 已安装
✓ Transformers 5.0.0 已安装
✓ HuggingFace Hub 1.4.0 已安装
✓ tqdm 4.66.5 已安装

所有依赖已满足，无需额外安装。

## 模型信息

| 模型 | 大小 | 说明 |
|------|------|------|
| Qwen2.5-7B-Instruct | ~14GB | 7B参数指令微调版本，适合生产使用 |
| Qwen2.5-1.5B-Instruct | ~3GB | 1.5B参数指令微调版本，适合快速测试 |

## 下载方法

### 方法1: 使用快速启动脚本（推荐）

**Windows:**
```bash
cd D:\30_keyan\GeoKD-SR\scripts
run_download.bat
```

**Linux/Mac:**
```bash
cd /d/30_keyan/GeoKD-SR/scripts
chmod +x run_download.sh
./run_download.sh
```

### 方法2: 直接运行Python脚本

```bash
cd D:\30_keyan\GeoKD-SR\scripts
python download_models.py
```

### 方法3: 使用国内镜像加速（推荐国内用户）

```bash
# Windows PowerShell
$env:HF_ENDPOINT="https://hf-mirror.com"
python download_models.py

# Linux/Mac
export HF_ENDPOINT=https://hf-mirror.com
python download_models.py
```

## 下载流程

1. 脚本会列出可用模型
2. 选择要下载的模型（可以多选）
3. 自动下载并显示进度
4. 下载完成后自动验证模型完整性
5. 验证通过后可以测试推理

## 验证说明

验证脚本会检查：
- ✓ 模型文件完整性（config.json, tokenizer等）
- ✓ Tokenizer加载测试
- ✓ 模型配置加载
- ✓ 简单推理测试（如果内存足够）

## 存储位置

模型将下载到：
```
D:/30_keyan/GeoKD-SR/models/
├── Qwen2.5-7B-Instruct/
│   ├── config.json
│   ├── tokenizer_config.json
│   ├── model-00001-of-00029.safetensors
│   └── ...
└── Qwen2.5-1.5B-Instruct/
    ├── config.json
    ├── tokenizer_config.json
    └── ...
```

## 使用示例

下载完成后，在代码中使用：

```python
from transformers import AutoTokenizer, AutoModelForCausalLM

# 加载7B模型
model_path = "D:/30_keyan/GeoKD-SR/models/Qwen2.5-7B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    device_map="auto",
    trust_remote_code=True
)

# 推理
response, history = model.chat(tokenizer, "你好", history=None)
print(response)
```

## 网络问题排查

如果下载失败：

1. **使用镜像加速**（推荐）:
   ```bash
   export HF_ENDPOINT=https://hf-mirror.com
   ```

2. **手动下载**:
   - 访问 https://hf-mirror.com/Qwen/Qwen2.5-7B-Instruct
   - 下载所有文件到指定目录
   - 运行验证脚本

3. **检查网络连接**:
   ```bash
   ping hf-mirror.com
   ping huggingface.co
   ```

## 预计时间

- 7B模型 (14GB):
  - 100Mbps网速: ~20分钟
  - 10Mbps网速: ~3小时

- 1.5B模型 (3GB):
  - 100Mbps网速: ~5分钟
  - 10Mbps网速: ~40分钟

使用国内镜像可以显著加速。
