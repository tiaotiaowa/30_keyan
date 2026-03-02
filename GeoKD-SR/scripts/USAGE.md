# Qwen2.5模型下载 - 执行指南

## 环境检查结果 ✓

所有环境测试已通过：

- ✓ Python 3.12.7
- ✓ PyTorch 2.10.0+cpu
- ✓ Transformers 5.0.0
- ✓ HuggingFace Hub 1.4.0
- ✓ 网络连接正常（使用 hf-mirror.com 镜像）
- ✓ 磁盘空间充足（68.60 GB 可用）
- ✓ 目录结构就绪

## 立即开始下载

### 方式1: 使用交互式脚本（推荐）

直接运行下载脚本，按照提示选择模型：

```bash
cd D:\30_keyan\GeoKD-SR\scripts
python download_models.py
```

**操作步骤：**
1. 脚本会列出2个模型（7B和1.5B）
2. 输入 `0` 下载所有模型，或输入 `1,2` 选择特定模型
3. 等待下载完成（会显示进度条）
4. 自动验证模型完整性

### 方式2: 使用批处理脚本

**Windows用户：**
```bash
cd D:\30_keyan\GeoKD-SR\scripts
run_download.bat
```

脚本会提示是否使用镜像加速，选择 `1` 使用 hf-mirror.com。

### 方式3: 手动设置镜像后下载

```bash
# PowerShell
$env:HF_ENDPOINT="https://hf-mirror.com"
python D:\30_keyan\GeoKD-SR\scripts\download_models.py

# CMD
set HF_ENDPOINT=https://hf-mirror.com
python D:\30_keyan\GeoKD-SR\scripts\download_models.py
```

## 模型选择建议

### 首次测试 - 推荐1.5B模型
- 大小：约3GB
- 下载时间：5-10分钟（100Mbps网络）
- 内存需求：约6GB RAM
- 适用场景：快速测试、开发调试

### 生产使用 - 推荐7B模型
- 大小：约14GB
- 下载时间：20-40分钟（100Mbps网络）
- 内存需求：约16GB RAM（CPU）/ 8GB VRAM（GPU）
- 适用场景：实际应用、性能评估

### 两者都下载
- 总大小：约17GB
- 建议分批下载，先下载1.5B测试，确认无问题后再下载7B

## 下载过程

下载时会显示以下信息：

```
============================================================
  准备下载 Qwen2.5-1.5B-Instruct
============================================================

模型说明: Qwen2.5 1.5B指令微调版本
预期大小: 3GB
仓库ID: Qwen/Qwen2.5-1.5B-Instruct
保存路径: D:\30_keyan\GeoKD-SR\models\Qwen2.5-1.5B-Instruct

下载源: https://hf-mirror.com
✓ 使用镜像加速

开始下载...
Downloading: 100%|█████████████████| 3.00G/3.00G [05:23<00:00]

✓ Qwen2.5-1.5B-Instruct 下载完成!
保存位置: D:\30_keyan\GeoKD-SR\models\Qwen2.5-1.5B-Instruct
实际大小: 3.02 GB
```

## 自动验证

下载完成后会自动验证：

1. **文件完整性检查** - 验证必要文件存在
2. **Tokenizer测试** - 加载分词器
3. **配置检查** - 验证模型配置
4. **推理测试** - 运行简单推理（如果内存足够）

## 预期下载时间（使用hf-mirror.com镜像）

| 网络 | 1.5B模型 | 7B模型 |
|------|----------|--------|
| 1000Mbps | ~1分钟 | ~4分钟 |
| 100Mbps | ~5分钟 | ~20分钟 |
| 50Mbps | ~10分钟 | ~40分钟 |
| 10Mbps | ~40分钟 | ~3小时 |

## 下载后使用

下载完成后，模型保存在：

```
D:\30_keyan\GeoKD-SR\models\
├── Qwen2.5-1.5B-Instruct\   (约3GB)
└── Qwen2.5-7B-Instruct\     (约14GB)
```

在代码中使用：

```python
from transformers import AutoTokenizer, AutoModelForCausalLM

# 加载模型
model_path = "D:\\30_keyan\\GeoKD-SR\\models\\Qwen2.5-1.5B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    device_map="auto",
    trust_remote_code=True
)

# 使用模型进行对话
response, history = model.chat(tokenizer, "介绍一下中国的地理特征", history=None)
print(response)
```

## 故障排查

### 问题1: 下载速度慢
**解决方案：** 使用国内镜像
```bash
set HF_ENDPOINT=https://hf-mirror.com
python download_models.py
```

### 问题2: 连接超时
**解决方案：**
- 检查网络连接
- 尝试切换镜像源
- 如果使用VPN，暂时关闭

### 问题3: 磁盘空间不足
**解决方案：**
- 只下载1.5B模型（需要3GB）
- 清理磁盘空间后再下载7B模型

### 问题4: 验证失败
**解决方案：**
- 检查下载是否完整
- 重新下载模型
- 查看详细错误信息

## 下一步

下载完成后：

1. **测试模型**
   ```python
   python scripts/test_model.py
   ```

2. **集成到GeoKD-SR项目**
   - 在 `config.py` 中配置模型路径
   - 使用模型进行地理知识问答

3. **性能优化**
   - 使用GPU加速（如果有CUDA）
   - 配置量化模型（4bit/8bit）

## 技术支持

如有问题，请检查：
- `scripts/README.md` - 详细文档
- `scripts/test_download.py` - 环境测试
- HuggingFace文档：https://huggingface.co/docs

## 当前状态

✓ 环境已就绪
✓ 网络连接正常
✓ 脚本已创建
✓ 等待执行下载

**现在可以运行下载脚本开始下载模型！**
