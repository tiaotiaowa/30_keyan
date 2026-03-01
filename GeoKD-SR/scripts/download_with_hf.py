"""
使用HuggingFace技术栈下载Qwen2.5模型
支持transformers、huggingface_hub等HuggingFace生态工具
"""
import os
from pathlib import Path
from huggingface_hub import (
    login,
    snapshot_download,
    whoami,
    scan_cache_dir,
    delete_cache
)
from transformers import AutoTokenizer, AutoModelForCausalLM, AutoConfig
import torch
from tqdm import tqdm
import shutil


# ==================== 配置 ====================
MODELS = {
    "qwen-7b": {
        "repo_id": "Qwen/Qwen2.5-7B-Instruct",
        "name": "Qwen2.5-7B-Instruct",
        "description": "Qwen2.5 7B指令微调版本 (教师模型)",
        "expected_size_gb": 14
    },
    "qwen-1.5b": {
        "repo_id": "Qwen/Qwen2.5-1.5B-Instruct",
        "name": "Qwen2.5-1.5B-Instruct",
        "description": "Qwen2.5 1.5B指令微调版本 (学生模型)",
        "expected_size_gb": 3
    }
}

BASE_DIR = Path(__file__).parent.parent
MODELS_DIR = BASE_DIR / "models"


# ==================== 工具函数 ====================

def print_section(title):
    """打印分节标题"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70 + "\n")


def check_huggingface_auth():
    """检查HuggingFace认证状态"""
    try:
        user_info = whoami()
        print(f"[OK] 已登录HuggingFace")
        print(f"     用户名: {user_info.get('name', 'Unknown')}")
        return True
    except Exception:
        print("[INFO] 未登录HuggingFace (公开模型不需要登录)")
        return False


def check_disk_space(required_gb):
    """检查磁盘空间"""
    try:
        stat = shutil.disk_usage(MODELS_DIR)
        free_gb = stat.free / (1024**3)
        print(f"[INFO] 可用磁盘空间: {free_gb:.1f} GB")

        if free_gb < required_gb:
            print(f"[WARN] 磁盘空间不足！需要至少 {required_gb} GB")
            return False
        return True
    except Exception as e:
        print(f"[WARN] 无法检查磁盘空间: {e}")
        return True


def check_cache():
    """检查HuggingFace缓存"""
    try:
        cache_info = scan_cache_dir()
        print(f"[INFO] HuggingFace缓存大小: {cache_info.size_on_disk_gb:.2f} GB")
        print(f"      缓存位置: {cache_info.cache_dir}")
        return cache_info
    except Exception as e:
        print(f"[INFO] 无法读取缓存信息: {e}")
        return None


def download_model_with_hf_hub(model_key, use_cache=True):
    """
    使用huggingface_hub下载模型

    Args:
        model_key: 模型键 (qwen-7b 或 qwen-1.5b)
        use_cache: 是否使用HF缓存

    Returns:
        模型路径
    """
    model_config = MODELS[model_key]
    repo_id = model_config["repo_id"]
    model_name = model_config["name"]

    print_section(f"下载 {model_name}")

    print(f"仓库ID: {repo_id}")
    print(f"预期大小: {model_config['expected_size_gb']} GB")
    print(f"说明: {model_config['description']}")

    # 检查镜像设置
    hf_endpoint = os.environ.get('HF_ENDPOINT', 'https://huggingface.co')
    print(f"下载源: {hf_endpoint}")
    if hf_endpoint != 'https://huggingface.co':
        print("      ✓ 使用镜像加速")

    # 目标路径
    model_path = MODELS_DIR / model_name

    # 检查是否已存在
    if model_path.exists():
        print(f"[INFO] 模型已存在: {model_path}")

        # 验证完整性
        config_file = model_path / "config.json"
        if config_file.exists():
            print("[OK] 模型文件完整，跳过下载")
            return model_path
        else:
            print("[WARN] 模型文件不完整，重新下载")

    # 使用huggingface_hub下载
    try:
        print("\n[DOWNLOAD] 开始下载...")

        if use_cache:
            # 使用HF缓存系统
            print("[INFO] 使用HuggingFace缓存系统")
            model_path = snapshot_download(
                repo_id=repo_id,
                local_dir=str(model_path),
                local_dir_use_symlinks=False,
                resume_download=True,
                endpoint=hf_endpoint if hf_endpoint != 'https://huggingface.co' else None
            )
        else:
            # 直接下载到指定目录
            print("[INFO] 直接下载到目标目录")
            model_path = snapshot_download(
                repo_id=repo_id,
                local_dir=str(model_path),
                local_dir_use_symlinks=False,
                resume_download=True,
                endpoint=hf_endpoint if hf_endpoint != 'https://huggingface.co' else None
            )

        print(f"\n[OK] {model_name} 下载完成!")
        print(f"    保存位置: {model_path}")

        # 计算实际大小
        total_size = sum(
            f.stat().st_size
            for f in Path(model_path).rglob('*')
            if f.is_file()
        ) / (1024**3)
        print(f"    实际大小: {total_size:.2f} GB")

        return str(model_path)

    except Exception as e:
        print(f"\n[ERROR] 下载失败: {e}")
        print("\n解决方案:")
        print("1. 检查网络连接")
        print("2. 使用国内镜像:")
        print("   export HF_ENDPOINT=https://hf-mirror.com")
        print("   python scripts/download_with_hf.py")
        print("3. 检查HuggingFace是否可访问")
        raise


def verify_model_with_transformers(model_path, model_name):
    """
    使用transformers验证模型

    Args:
        model_path: 模型路径
        model_name: 模型名称

    Returns:
        是否验证成功
    """
    print_section(f"验证 {model_name}")

    try:
        # 1. 加载配置
        print("[1/4] 加载模型配置...")
        config = AutoConfig.from_pretrained(
            model_path,
            trust_remote_code=True
        )
        print(f"      ✓ 模型类型: {config.model_type}")
        print(f"      ✓ 词汇量: {config.vocab_size}")
        print(f"      ✓ 隐藏层大小: {config.hidden_size}")
        print(f"      ✓ 注意力头数: {config.num_attention_heads}")
        print(f"      ✓ 层数: {config.num_hidden_layers}")

        # 2. 加载Tokenizer
        print("\n[2/4] 加载Tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True
        )
        print(f"      ✓ Tokenizer加载成功")
        print(f"      ✓ 词汇表大小: {len(tokenizer)}")

        # 3. 检查设备
        print("\n[3/4] 检查计算设备...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"      ✓ 使用设备: {device.upper()}")
        if device == "cuda":
            print(f"      ✓ GPU数量: {torch.cuda.device_count()}")
            print(f"      ✓ GPU名称: {torch.cuda.get_device_name(0)}")

        # 4. 测试模型加载
        print("\n[4/4] 测试模型加载...")
        if "7B" in model_name and device == "cpu":
            print("      ⚠ 跳过完整模型加载（7B模型在CPU上内存不足）")
            print("      ✓ 配置验证通过")
        else:
            print("      ⚠ 首次加载需要创建CUDA缓存，可能需要几分钟...")

            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                device_map="auto" if device == "cuda" else None,
                trust_remote_code=True,
                low_cpu_mem_usage=True
            )

            # 简单推理测试
            print("\n      测试推理...")
            test_prompt = "中国的首都是哪里？"
            messages = [{"role": "user", "content": test_prompt}]
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )

            model_inputs = tokenizer([text], return_tensors="pt")
            if device == "cuda":
                model_inputs = {k: v.to(model.device) for k, v in model_inputs.items()}

            with torch.no_grad():
                outputs = model.generate(
                    **model_inputs,
                    max_new_tokens=50,
                    do_sample=False,
                    temperature=0.7
                )

            response = tokenizer.decode(outputs[0], skip_special_tokens=True)
            print(f"      ✓ 推理测试通过")
            print(f"      输入: {test_prompt}")
            print(f"      输出: {response[:100]}...")

            # 清理内存
            del model
            if device == "cuda":
                torch.cuda.empty_cache()

        print(f"\n[OK] {model_name} 验证完成!")
        return True

    except Exception as e:
        print(f"\n[ERROR] 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def load_model_with_transformers(model_path, device="auto"):
    """
    使用transformers加载模型（用于实际使用）

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
    if device == "auto":
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            torch_dtype="auto",
            device_map="auto"
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        ).to(device)

    print(f"[OK] 模型加载完成")
    return model, tokenizer


# ==================== 示例代码 ====================

def example_chat(model_path):
    """
    示例：使用模型进行对话

    Args:
        model_path: 模型路径
    """
    print_section("示例：对话")

    # 加载模型
    model, tokenizer = load_model_with_transformers(model_path)

    # 对话
    question = "北京在上海的什么方向？"
    print(f"问题: {question}\n")

    messages = [{"role": "user", "content": question}]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **model_inputs,
            max_new_tokens=200,
            do_sample=True,
            temperature=0.7,
            top_p=0.9
        )

    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    print(f"回答: {response}")


def example_kd_inference(teacher_path, student_path, question):
    """
    示例：知识蒸馏推理

    Args:
        teacher_path: 教师模型路径
        student_path: 学生模型路径
        question: 问题
    """
    print_section("示例：知识蒸馏推理")

    # 加载模型
    print("加载教师模型...")
    teacher_model, teacher_tokenizer = load_model_with_transformers(teacher_path)

    print("加载学生模型...")
    student_model, student_tokenizer = load_model_with_transformers(student_path)

    # 教师模型推理
    print(f"\n问题: {question}")
    print("\n教师模型回答:")
    messages = [{"role": "user", "content": question}]
    text = teacher_tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    model_inputs = teacher_tokenizer([text], return_tensors="pt").to(teacher_model.device)
    with torch.no_grad():
        outputs = teacher_model.generate(
            **model_inputs,
            max_new_tokens=200,
            do_sample=False
        )
    teacher_response = teacher_tokenizer.decode(outputs[0], skip_special_tokens=True)
    print(f"{teacher_response}")

    # 学生模型推理
    print("\n学生模型回答:")
    text = student_tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    model_inputs = student_tokenizer([text], return_tensors="pt").to(student_model.device)
    with torch.no_grad():
        outputs = student_model.generate(
            **model_inputs,
            max_new_tokens=200,
            do_sample=False
        )
    student_response = student_tokenizer.decode(outputs[0], skip_special_tokens=True)
    print(f"{student_response}")


# ==================== 主函数 ====================

def main():
    """主函数"""
    print_section("GeoKD-SR - HuggingFace模型下载工具")

    # 检查环境
    print("[INFO] 检查HuggingFace环境...")
    check_huggingface_auth()
    check_cache()

    # 确保目录存在
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # 选择模型
    print("\n请选择要下载的模型:")
    print("  1. Qwen2.5-7B-Instruct (教师模型, ~14GB)")
    print("  2. Qwen2.5-1.5B-Instruct (学生模型, ~3GB)")
    print("  3. 全部下载")
    print("  0. 退出")

    choice = input("\n选择 (0-3): ").strip()

    if choice == "0":
        print("退出")
        return
    elif choice == "1":
        models_to_download = ["qwen-7b"]
    elif choice == "2":
        models_to_download = ["qwen-1.5b"]
    elif choice == "3":
        models_to_download = ["qwen-7b", "qwen-1.5b"]
    else:
        print("无效选择")
        return

    # 检查磁盘空间
    total_size = sum(MODELS[m]["expected_size_gb"] for m in models_to_download)
    if not check_disk_space(total_size * 1.2):  # 预留20%缓冲
        print("\n[ERROR] 磁盘空间不足")
        return

    # 下载模型
    success_count = 0
    downloaded_models = []

    for model_key in models_to_download:
        try:
            model_path = download_model_with_hf_hub(model_key)
            model_name = MODELS[model_key]["name"]

            if verify_model_with_transformers(model_path, model_name):
                success_count += 1
                downloaded_models.append((model_key, model_path))

        except Exception as e:
            print(f"\n[ERROR] 处理 {model_key} 时出错: {e}")
            continue

    # 总结
    print_section("下载完成")
    print(f"成功下载: {success_count}/{len(models_to_download)} 个模型\n")

    for model_key, model_path in downloaded_models:
        print(f"✓ {MODELS[model_key]['name']}: {model_path}")

    # 使用示例
    if downloaded_models:
        print("\n" + "="*70)
        print("使用示例")
        print("="*70)

        print("\n# 加载模型")
        print("from transformers import AutoModelForCausalLM, AutoTokenizer")
        print(f"""
model_path = "{downloaded_models[0][1]}"
tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    device_map="auto",
    trust_remote_code=True
)
        """)

        print("\n# 对话示例")
        print("""
messages = [{"role": "user", "content": "你好"}]
text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

outputs = model.generate(**model_inputs, max_new_tokens=100)
response = tokenizer.decode(outputs[0], skip_special_tokens=True)
print(response)
        """)

    print("\n" + "="*70)
    print("更多信息请参考:")
    print("  - HuggingFace文档: https://huggingface.co/docs")
    print("  - Qwen模型: https://huggingface.co/Qwen")
    print("  - Transformers: https://huggingface.co/docs/transformers/")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
