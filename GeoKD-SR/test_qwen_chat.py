# -*- coding: utf-8 -*-
"""
Qwen2.5-1.5B-Instruct 地理空间推理助手
单轮对话模式，支持用户输入问题并输出答案
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# Prompt模板
PROMPT_TEMPLATE = """你是一个地理空间推理专家。请根据问题给出准确、简洁的答案。

问题: {question}

请直接给出答案，不需要解释过程。答案格式要求：
- 方向问题：直接说明方向，如"东南方向"
- 距离问题：给出具体数值，如"约1200公里"
- 拓扑问题：明确说明关系，如"是的，XX位于YY内部"
- 复合问题：同时给出最终结果

答案:"""


def main():
    print("=" * 60)
    print("Qwen2.5-1.5B-Instruct 地理空间推理助手")
    print("单轮对话模式 | 输入 'quit' 或 'exit' 退出")
    print("=" * 60)

    # Step 1: 检查CUDA可用性
    print("\n[1] 检查CUDA状态...")
    print(f"  PyTorch版本: {torch.__version__}")
    print(f"  CUDA可用: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"  CUDA版本: {torch.version.cuda}")
        print(f"  GPU设备: {torch.cuda.get_device_name(0)}")
        print(f"  GPU显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
    else:
        print("  警告: CUDA不可用，将使用CPU运行（较慢）")

    # Step 2: 加载模型和tokenizer
    print("\n[2] 加载模型...")
    model_path = "D:/30_keyan/GeoKD-SR/models/Qwen2.5-1.5B-Instruct"
    print(f"  模型路径: {model_path}")

    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    print("  Tokenizer加载完成")

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float16,
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

    # Step 3: 单轮对话函数
    def chat(question):
        """单轮对话，使用地理空间推理prompt模板"""
        prompt = PROMPT_TEMPLATE.format(question=question)
        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt").to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=256,
                temperature=0.1,
                top_p=0.9,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id
            )

        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        # 提取助手回复部分
        if "<|im_start|>assistant" in response:
            response = response.split("<|im_start|>assistant")[-1].strip()
        if "<|im_end|>" in response:
            response = response.split("<|im_end|>")[0].strip()
        return response

    # Step 4: 交互式单轮对话
    print("\n" + "=" * 60)
    print("开始对话（每轮独立，无历史记忆）")
    print("=" * 60)

    while True:
        try:
            print("\n" + "-" * 40)
            user_input = input("问题: ").strip()

            # 退出命令
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n再见!")
                break

            if user_input:
                response = chat(user_input)
                print(f"\n答案: {response}")
            else:
                print("请输入问题...")

        except KeyboardInterrupt:
            print("\n\n再见!")
            break

if __name__ == "__main__":
    main()
