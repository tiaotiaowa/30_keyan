"""
HuggingFace快速开始示例
演示如何使用HuggingFace技术栈加载和使用Qwen2.5模型
"""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from pathlib import Path


# ==================== 配置 ====================
MODEL_PATHS = {
    "teacher": "D:/30_keyan/GeoKD-SR/models/Qwen2.5-7B-Instruct",
    "student": "D:/30_keyan/GeoKD-SR/models/Qwen2.5-1.5B-Instruct"
}


# ==================== 基础功能 ====================

def load_model(model_path, device="auto"):
    """
    加载Qwen模型

    Args:
        model_path: 模型路径
        device: 设备 ("auto", "cuda", "cpu")

    Returns:
        (model, tokenizer)
    """
    print(f"[INFO] 加载模型: {model_path}")

    # 加载tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        trust_remote_code=True
    )

    # 加载模型
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto" if device == "auto" else None,
        trust_remote_code=True
    )

    print(f"[OK] 模型加载完成")
    print(f"     设备: {model.device}")
    print(f"     参数量: {sum(p.numel() for p in model.parameters()) / 1e9:.2f}B")

    return model, tokenizer


def chat(model, tokenizer, question, max_new_tokens=200, temperature=0.7):
    """
    对话功能

    Args:
        model: 模型
        tokenizer: 分词器
        question: 问题
        max_new_tokens: 最大生成token数
        temperature: 温度参数

    Returns:
        回答
    """
    # 准备输入
    messages = [{"role": "user", "content": question}]

    # 应用聊天模板
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    # Tokenize
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

    # 生成
    with torch.no_grad():
        outputs = model.generate(
            **model_inputs,
            max_new_tokens=max_new_tokens,
            do_sample=temperature > 0,
            temperature=temperature,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id
        )

    # 解码
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return response


# ==================== 示例1: 基础对话 ====================

def example1_basic_chat():
    """示例1: 基础对话"""
    print("\n" + "="*70)
    print("示例1: 基础对话")
    print("="*70)

    # 加载学生模型（更快）
    model, tokenizer = load_model(MODEL_PATHS["student"])

    # 对话
    questions = [
        "中国的首都是哪里？",
        "北京在上海的什么方向？",
        "长江流经哪些省份？"
    ]

    for question in questions:
        print(f"\n问题: {question}")
        response = chat(model, tokenizer, question)
        print(f"回答: {response}")

    # 清理
    del model
    torch.cuda.empty_cache()


# ==================== 示例2: 知识蒸馏 ====================

def example2_knowledge_distillation():
    """示例2: 知识蒸馏（获取软标签）"""
    print("\n" + "="*70)
    print("示例2: 知识蒸馏")
    print("="*70)

    # 加载教师和学生模型
    print("\n加载教师模型...")
    teacher_model, teacher_tokenizer = load_model(MODEL_PATHS["teacher"])

    print("\n加载学生模型...")
    student_model, student_tokenizer = load_model(MODEL_PATHS["student"])

    # 准备问题
    question = "北京在上海的什么方向？"
    print(f"\n问题: {question}")

    # 准备输入
    messages = [{"role": "user", "content": question}]
    text = student_tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )
    inputs = student_tokenizer([text], return_tensors="pt").to(student_model.device)

    # 教师模型推理
    print("\n教师模型推理...")
    with torch.no_grad():
        teacher_outputs = teacher_model(**inputs, labels=inputs["input_ids"])
        teacher_logits = teacher_outputs.logits
        teacher_loss = teacher_outputs.loss

    print(f"  教师模型损失: {teacher_loss.item():.4f}")

    # 学生模型推理
    print("\n学生模型推理...")
    with torch.no_grad():
        student_outputs = student_model(**inputs, labels=inputs["input_ids"])
        student_logits = student_outputs.logits
        student_loss = student_outputs.loss

    print(f"  学生模型损失: {student_loss.item():.4f}")

    # 计算KL散度（蒸馏损失）
    temperature = 2.0
    kl_loss = torch.nn.KLDivLoss(reduction="batchmean")(
        torch.log_softmax(student_logits / temperature, dim=-1),
        torch.softmax(teacher_logits / temperature, dim=-1)
    ) * (temperature ** 2)

    print(f"\nKL散度损失 (T={temperature}): {kl_loss.item():.4f}")

    # 生成回答对比
    print("\n教师模型回答:")
    teacher_response = chat(teacher_model, teacher_tokenizer, question)
    print(f"{teacher_response}")

    print("\n学生模型回答:")
    student_response = chat(student_model, student_tokenizer, question)
    print(f"{student_response}")

    # 清理
    del teacher_model, student_model
    torch.cuda.empty_cache()


# ==================== 示例3: 批量处理 ====================

def example3_batch_processing():
    """示例3: 批量处理"""
    print("\n" + "="*70)
    print("示例3: 批量处理")
    print("="*70)

    # 加载模型
    model, tokenizer = load_model(MODEL_PATHS["student"])

    # 准备批量问题
    questions = [
        "北京在上海的什么方向？",
        "长江流经哪些省份？",
        "从北京到广州的距离大约是多少？",
        "泰山位于哪个省份？",
    ]

    print(f"\n批量处理 {len(questions)} 个问题...")

    # 批量处理
    responses = []
    for i, question in enumerate(questions, 1):
        print(f"\n[{i}/{len(questions)}] {question}")
        response = chat(model, tokenizer, question, max_new_tokens=100)
        print(f"回答: {response}")
        responses.append(response)

    # 清理
    del model
    torch.cuda.empty_cache()


# ==================== 示例4: 空间关系推理 ====================

def example4_spatial_reasoning():
    """示例4: 地理空间推理"""
    print("\n" + "="*70)
    print("示例4: 地理空间推理")
    print("="*70)

    # 加载模型
    model, tokenizer = load_model(MODEL_PATHS["student"])

    # 空间关系推理问题
    spatial_questions = [
        {
            "type": "方向关系",
            "question": "北京在上海的什么方向？请详细说明。"
        },
        {
            "type": "拓扑关系",
            "question": "长江是否流经湖北省？请说明原因。"
        },
        {
            "type": "度量关系",
            "question": "从西安到成都的直线距离大约是多少公里？"
        },
        {
            "type": "综合推理",
            "question": "如果一个人从北京出发，先到武汉，再到广州，他整体是向什么方向移动？"
        }
    ]

    for item in spatial_questions:
        print(f"\n类型: {item['type']}")
        print(f"问题: {item['question']}")

        response = chat(model, tokenizer, item['question'], max_new_tokens=200)
        print(f"回答: {response}")

    # 清理
    del model
    torch.cuda.empty_cache()


# ==================== 主函数 ====================

def main():
    """主函数"""
    print("\n" + "="*70)
    print("HuggingFace + Qwen2.5 快速开始示例")
    print("="*70)

    print("\n请选择要运行的示例:")
    print("  1. 基础对话")
    print("  2. 知识蒸馏")
    print("  3. 批量处理")
    print("  4. 空间关系推理")
    print("  0. 退出")

    choice = input("\n选择 (0-4): ").strip()

    if choice == "1":
        example1_basic_chat()
    elif choice == "2":
        example2_knowledge_distillation()
    elif choice == "3":
        example3_batch_processing()
    elif choice == "4":
        example4_spatial_reasoning()
    elif choice == "0":
        print("退出")
    else:
        print("无效选择")

    print("\n" + "="*70)
    print("示例运行完成!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
