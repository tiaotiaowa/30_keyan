#!/usr/bin/env python3
"""
Qwen2.5-1.5B-Instruct 模型测试脚本
测试模型加载、GPU推理和地理空间推理能力
"""

import os
import sys
import time
import torch

# 设置HuggingFace镜像
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

def test_model_loading():
    """测试模型加载"""
    print("\n" + "="*60)
    print("[1] 模型加载测试")
    print("="*60)

    from transformers import AutoModelForCausalLM, AutoTokenizer

    model_path = "/home/nihao/30_keyan/30_keyan/GeoKD-SR/models/Qwen2.5-1.5B-Instruct"

    print(f"模型路径: {model_path}")
    print(f"加载Tokenizer...", end=" ", flush=True)
    start = time.time()
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    print(f"✓ ({time.time()-start:.2f}s)")

    print(f"加载模型...", end=" ", flush=True)
    start = time.time()
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True
    )
    print(f"✓ ({time.time()-start:.2f}s)")

    # 模型信息
    print(f"\n模型信息:")
    print(f"  - 参数量: {sum(p.numel() for p in model.parameters()) / 1e9:.2f}B")
    print(f"  - 数据类型: {model.dtype}")
    print(f"  - 设备: {model.device}")

    return model, tokenizer

def test_gpu_inference(model, tokenizer):
    """测试GPU推理"""
    print("\n" + "="*60)
    print("[2] GPU推理测试")
    print("="*60)

    # GPU信息
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"显存: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    # 测试推理
    test_prompts = [
        "你好，请介绍一下你自己。",
        "1+1等于几？",
        "中国的首都是哪里？"
    ]

    for i, prompt in enumerate(test_prompts, 1):
        print(f"\n测试 {i}: {prompt}")

        # 构建消息
        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer([text], return_tensors="pt").to(model.device)

        # 推理
        start = time.time()
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=100,
                do_sample=True,
                temperature=0.7,
                top_p=0.8,
                pad_token_id=tokenizer.eos_token_id
            )

        response = tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
        elapsed = time.time() - start

        print(f"回复: {response[:200]}...")
        print(f"耗时: {elapsed:.2f}s")

        # 显存使用
        mem_used = torch.cuda.max_memory_allocated() / 1e9
        print(f"显存使用: {mem_used:.2f} GB")

    return True

def test_geo_spatial_reasoning(model, tokenizer):
    """测试地理空间推理能力"""
    print("\n" + "="*60)
    print("[3] 地理空间推理测试")
    print("="*60)

    geo_questions = [
        "北京在上海的什么方向？",
        "长江流经哪些省份？",
        "从广州到北京的直线距离大约是多少公里？",
        "喜马拉雅山脉位于中国和哪个国家的边境？",
        "如果一个人在成都，想要去最近的海边，应该去哪个城市？"
    ]

    print("测试地理空间推理问题...\n")

    for i, question in enumerate(geo_questions, 1):
        print(f"\n问题 {i}: {question}")
        print("-" * 50)

        messages = [{"role": "user", "content": question}]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer([text], return_tensors="pt").to(model.device)

        start = time.time()
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=256,
                do_sample=True,
                temperature=0.7,
                top_p=0.8,
                pad_token_id=tokenizer.eos_token_id
            )

        response = tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
        elapsed = time.time() - start

        print(f"回答: {response}")
        print(f"耗时: {elapsed:.2f}s")

    return True

def test_batch_inference(model, tokenizer):
    """测试批量推理"""
    print("\n" + "="*60)
    print("[4] 批量推理测试")
    print("="*60)

    batch_questions = [
        "中国有多少个省级行政区？",
        "黄河的长度是多少？",
        "珠穆朗玛峰有多高？"
    ]

    print(f"批量处理 {len(batch_questions)} 个问题...")

    # 批量构建输入
    texts = []
    for q in batch_questions:
        messages = [{"role": "user", "content": q}]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        texts.append(text)

    inputs = tokenizer(texts, return_tensors="pt", padding=True).to(model.device)

    start = time.time()
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=100,
            do_sample=True,
            temperature=0.7,
            pad_token_id=tokenizer.eos_token_id
        )

    elapsed = time.time() - start

    print(f"\n批量推理结果 (总耗时: {elapsed:.2f}s):")
    for i, (q, output) in enumerate(zip(batch_questions, outputs), 1):
        response = tokenizer.decode(output[inputs['input_ids'].shape[1]:], skip_special_tokens=True)
        print(f"\n{i}. {q}")
        print(f"   回答: {response[:100]}...")

    return True

def main():
    print("="*60)
    print("Qwen2.5-1.5B-Instruct 模型测试")
    print("="*60)
    print(f"PyTorch版本: {torch.__version__}")
    print(f"CUDA可用: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    try:
        # 1. 加载模型
        model, tokenizer = test_model_loading()

        # 2. GPU推理测试
        test_gpu_inference(model, tokenizer)

        # 3. 地理空间推理测试
        test_geo_spatial_reasoning(model, tokenizer)

        # 4. 批量推理测试
        test_batch_inference(model, tokenizer)

        print("\n" + "="*60)
        print("✅ 所有测试完成！")
        print("="*60)

        # 最终显存使用
        mem_allocated = torch.cuda.memory_allocated() / 1e9
        mem_reserved = torch.cuda.memory_reserved() / 1e9
        print(f"\n显存使用:")
        print(f"  - 已分配: {mem_allocated:.2f} GB")
        print(f"  - 已预留: {mem_reserved:.2f} GB")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
