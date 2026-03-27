# -*- coding: utf-8 -*-
"""
Qwen2.5-1.5B-Instruct 简单对话测试
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

print("=" * 60)
print("Qwen2.5-1.5B-Instruct 模型加载与对话测试")
print("=" * 60)

# Step 1: 检查CUDA可用性
print("\n[Step 1] 检查CUDA状态...")
print(f"  PyTorch版本: {torch.__version__}")
print(f"  CUDA可用: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"  CUDA版本: {torch.version.cuda}")
    print(f"  GPU设备: {torch.cuda.get_device_name(0)}")
    print(f"  GPU显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")

# Step 2: 加载模型和tokenizer
print("\n[Step 2] 加载模型...")
model_path = "D:/30_keyan/GeoKD-SR/models/Qwen2.5-1.5B-Instruct"
print(f"  模型路径: {model_path}")

tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
print("  Tokenizer加载完成")

model = AutoModelForCausalLM.from_pretrained(
    model_path,
    torch_dtype="auto",  # 使用auto自动选择
    device_map="auto",
    trust_remote_code=True
)
print("  模型加载完成")

# 显示显存使用情况
if torch.cuda.is_available():
    allocated = torch.cuda.memory_allocated(0) / 1024**3
    reserved = torch.cuda.memory_reserved(0) / 1024**3
    print(f"  显存已分配: {allocated:.2f} GB")
    print(f"  显存已预留: {reserved:.2f} GB")

# Step 3: 对话函数
def chat(prompt):
    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=256,
            temperature=0.7,
            top_p=0.8,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )

    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    # 提取助手回复部分
    if "assistant" in response:
        parts = response.split("assistant")
        if len(parts) > 1:
            response = parts[-1].strip()
    return response

# Step 4: 测试地理空间推理问题
print("\n[Step 3] 测试地理空间推理能力...")
print("-" * 60)

test_questions = [
    "北京在上海的什么方向？",
    "武汉和南京哪个城市更靠北？",
]

for i, question in enumerate(test_questions, 1):
    print(f"\n问题 {i}: {question}")
    print("-" * 40)
    try:
        response = chat(question)
        print(f"回答: {response}")
    except Exception as e:
        print(f"错误: {e}")

print("\n" + "=" * 60)
print("测试完成!")
print("=" * 60)
