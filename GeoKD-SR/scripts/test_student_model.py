# -*- coding: utf-8 -*-
"""
测试学生模型 (Qwen2.5-1.5B-Instruct)
验证模型加载和基础推理功能
"""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import time
import sys

# 设置输出编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_student_model():
    """测试学生模型"""
    print("\n" + "="*70)
    print("GeoKD-SR 学生模型测试")
    print("="*70)

    model_path = "D:/30_keyan/GeoKD-SR/models/Qwen2.5-1.5B-Instruct"

    # 1. 检查模型文件
    print("\n[步骤1] 检查模型文件...")
    from pathlib import Path
    model_dir = Path(model_path)

    required_files = [
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "model.safetensors"
    ]

    missing_files = []
    for file in required_files:
        file_path = model_dir / file
        if not file_path.exists():
            missing_files.append(file)

    if missing_files:
        print(f"[ERROR] 缺少文件: {missing_files}")
        return False
    else:
        print("[OK] 所有必需文件存在")

    # 2. 加载tokenizer
    print("\n[步骤2] 加载tokenizer...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True
        )
        print(f"[OK] Tokenizer加载成功")
        print(f"   词表大小: {len(tokenizer)}")
    except Exception as e:
        print(f"[ERROR] Tokenizer加载失败: {e}")
        return False

    # 3. 加载模型
    print("\n[步骤3] 加载模型...")
    try:
        start_time = time.time()

        # CPU模式：不使用device_map
        if torch.cuda.is_available():
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch.float16,
                device_map="auto",
                trust_remote_code=True
            )
        else:
            # 纯CPU模式
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch.float32,
                trust_remote_code=True
            )

        load_time = time.time() - start_time

        print(f"[OK] 模型加载成功 (耗时: {load_time:.2f}秒)")
        print(f"   参数量: {sum(p.numel() for p in model.parameters()) / 1e9:.2f}B")

        # 检查显存/内存使用
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated() / 1024**3
            print(f"   GPU显存: {allocated:.2f} GB")
            print(f"   设备: {model.device}")
        else:
            import psutil
            memory = psutil.Process().memory_info().rss / 1024**3
            print(f"   内存使用: {memory:.2f} GB")
            print(f"   设备: CPU")

    except Exception as e:
        print(f"[ERROR] 模型加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 4. 测试推理
    print("\n[步骤4] 测试推理功能...")

    test_questions = [
        "你好，请介绍一下你自己。",
        "中国的首都是哪里？",
        "北京在上海的什么方向？"
    ]

    for i, question in enumerate(test_questions, 1):
        print(f"\n  测试 {i}/{len(test_questions)}: {question}")

        try:
            # 准备输入
            messages = [{"role": "user", "content": question}]
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )

            model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

            # 生成
            start_time = time.time()
            with torch.no_grad():
                outputs = model.generate(
                    **model_inputs,
                    max_new_tokens=50,
                    do_sample=False,
                    pad_token_id=tokenizer.eos_token_id
                )

            inference_time = time.time() - start_time

            # 解码
            response = tokenizer.decode(outputs[0], skip_special_tokens=True)

            # 提取回答部分（去除输入）
            if "assistant\n" in response:
                answer = response.split("assistant\n")[-1]
            else:
                answer = response

            print(f"    [OK] 成功 (耗时: {inference_time:.2f}秒)")
            print(f"    回答: {answer[:100]}...")

        except Exception as e:
            print(f"    [ERROR] 失败: {e}")
            return False

    # 5. 测试空间推理
    print("\n[步骤5] 测试空间推理能力...")

    spatial_question = "如果从北京向东南方向走到济南，再从济南向东南方向走到南京，那么南京在北京的什么方向？"
    print(f"  问题: {spatial_question}")

    try:
        messages = [{"role": "user", "content": spatial_question}]
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

        start_time = time.time()
        with torch.no_grad():
            outputs = model.generate(
                **model_inputs,
                max_new_tokens=150,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                pad_token_id=tokenizer.eos_token_id
            )

        inference_time = time.time() - start_time

        response = tokenizer.decode(outputs[0], skip_special_tokens=True)

        if "assistant\n" in response:
            answer = response.split("assistant\n")[-1]
        else:
            answer = response

        print(f"  [OK] 成功 (耗时: {inference_time:.2f}秒)")
        print(f"  回答: {answer}")

    except Exception as e:
        print(f"  [ERROR] 失败: {e}")
        return False

    # 清理
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    print("\n" + "="*70)
    print("[SUCCESS] 所有测试通过！学生模型工作正常")
    print("="*70 + "\n")

    return True


if __name__ == "__main__":
    try:
        success = test_student_model()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
