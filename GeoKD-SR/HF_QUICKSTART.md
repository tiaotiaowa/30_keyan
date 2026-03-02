# 🚀 使用HuggingFace下载Qwen模型

## 快速开始

### 1️⃣ 安装依赖

```bash
pip install transformers>=4.36.0 huggingface_hub>=0.20.0 torch
```

### 2️⃣ 配置镜像（可选，国内推荐）

```bash
# Windows PowerShell
$env:HF_ENDPOINT="https://hf-mirror.com"

# Windows CMD
set HF_ENDPOINT=https://hf-mirror.com

# Linux/Mac
export HF_ENDPOINT=https://hf-mirror.com
```

### 3️⃣ 下载模型

```bash
cd D:\30_keyan\GeoKD-SR\scripts
python download_with_hf.py
```

选择要下载的模型：
- 选项1: Qwen2.5-7B-Instruct (教师模型, ~14GB)
- 选项2: Qwen2.5-1.5B-Instruct (学生模型, ~3GB)
- 选项3: 全部下载

---

## 💡 快速示例

### 加载模型

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

# 加载模型
model_path = "D:/30_keyan/GeoKD-SR/models/Qwen2.5-7B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    device_map="auto",
    trust_remote_code=True
)

# 对话
messages = [{"role": "user", "content": "你好"}]
text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = tokenizer([text], return_tensors="pt").to(model.device)

outputs = model.generate(**inputs, max_new_tokens=100)
response = tokenizer.decode(outputs[0], skip_special_tokens=True)
print(response)
```

### 运行示例

```bash
cd D:\30_keyan\GeoKD-SR\examples
python hf_quickstart.py
```

---

## 📚 更多资源

- **完整指南**: `docs/HUGGINGFACE_GUIDE.md`
- **下载脚本**: `scripts/download_with_hf.py`
- **示例代码**: `examples/hf_quickstart.py`
- **HuggingFace文档**: https://huggingface.co/docs

---

## ❓ 常见问题

**Q: 下载速度慢怎么办？**
A: 设置镜像 `export HF_ENDPOINT=https://hf-mirror.com`

**Q: 内存不足怎么办？**
A: 使用量化加载或先下载1.5B小模型

**Q: 如何使用GPU？**
A: 确保安装了CUDA版本的PyTorch，模型会自动使用GPU

---

**需要帮助？** 查看 `docs/HUGGINGFACE_GUIDE.md` 获取详细文档
