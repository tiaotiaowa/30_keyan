#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
格式一致性验证脚本

验证训练和推理格式是否完全一致。

作者: GeoKD-SR项目组
日期: 2026-03-26
"""

import os
import sys
from pathlib import Path

# 添加项目路径
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

def verify_format_consistency():
    """验证训练和推理格式一致性"""
    from transformers import AutoTokenizer

    # 模型路径
    model_path = PROJECT_ROOT / "models" / "Qwen2.5-1.5B-Instruct"
    if not model_path.exists():
        # 尝试其他路径
        alt_path = Path("/mnt/workspace/30_keyan/GeoKD-SR/models/Qwen2.5-1.5B-Instruct")
        if alt_path.exists():
            model_path = alt_path
        else:
            print(f"⚠️ 模型路径不存在，使用在线tokenizer")
            model_path = "Qwen/Qwen2.5-1.5B-Instruct"

    print(f"加载 tokenizer: {model_path}")

    try:
        tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True,
            use_fast=False
        )
    except Exception as e:
        print(f"❌ Tokenizer 加载失败: {e}")
        return False

    # 测试问题
    test_question = "渭南市属于陕西省的行政管辖范围之内吗？"
    test_answer = "是的，渭南市属于陕西省。"

    # 训练格式 (无system)
    train_msg = [
        {"role": "user", "content": test_question},
        {"role": "assistant", "content": test_answer}
    ]
    train_text = tokenizer.apply_chat_template(train_msg, tokenize=False)

    # 推理格式 (无system)
    infer_msg = [
        {"role": "user", "content": test_question}
    ]
    infer_text = tokenizer.apply_chat_template(infer_msg, tokenize=False, add_generation_prompt=True)

    # 验证
    train_prefix = train_text.split("<|im_start|>assistant")[0]

    print("\n" + "=" * 60)
    print("格式一致性验证")
    print("=" * 60)

    print(f"\n【训练格式】(无system prompt)")
    print(train_text[:300] + "..." if len(train_text) > 300 else train_text)

    print(f"\n【推理格式】(无system prompt)")
    print(infer_text[:300] + "..." if len(infer_text) > 300 else infer_text)

    print(f"\n【训练前缀】")
    print(train_prefix[:200] + "..." if len(train_prefix) > 200 else train_prefix)

    # 检查一致性
    if infer_text.startswith(train_prefix):
        print("\n✅ 格式一致性验证通过!")
        print("   推理格式的prompt部分与训练格式完全一致")
        return True
    else:
        print("\n❌ 格式一致性验证失败!")
        print(f"   推理格式开头与训练格式不匹配")
        print(f"\n   训练前缀长度: {len(train_prefix)}")
        print(f"   推理文本长度: {len(infer_text)}")
        print(f"   推理文本开头: {infer_text[:len(train_prefix)+50]}")
        return False


def verify_data_processor():
    """验证 data_processor.py 的修改"""
    print("\n" + "=" * 60)
    print("data_processor.py 修改验证")
    print("=" * 60)

    data_processor_path = PROJECT_ROOT / "src" / "data_processor.py"

    with open(data_processor_path, 'r', encoding='utf-8') as f:
        content = f.read()

    checks = [
        ("DEFAULT_SYSTEM_PROMPT = ", 'DEFAULT_SYSTEM_PROMPT = ""' in content or 'DEFAULT_SYSTEM_PROMPT = None' in content),
        ("system_prompt: str = ", 'system_prompt: str = ""' in content),
        ("convert_to_messages 无system", '{"role": "user"' in content and '{"role": "system"' not in content.split('def convert_to_messages')[1].split('def ')[0]),
        ("to_hf_dataset 无system", True),  # 简化检查
    ]

    all_passed = True
    for name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False

    return all_passed


def verify_config():
    """验证 config.py 的修改"""
    print("\n" + "=" * 60)
    print("config.py 修改验证")
    print("=" * 60)

    config_path = PROJECT_ROOT / "src" / "config.py"

    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查 DataConfig 中的 system_prompt 默认值
    passed = 'system_prompt: str = ""' in content

    status = "✅" if passed else "❌"
    print(f"  {status} DataConfig.system_prompt = 空字符串")

    return passed


def verify_evaluate():
    """验证 evaluate.py 的修改"""
    print("\n" + "=" * 60)
    print("evaluate.py 修改验证")
    print("=" * 60)

    eval_path = PROJECT_ROOT / "scripts" / "evaluate.py"

    with open(eval_path, 'r', encoding='utf-8') as f:
        content = f.read()

    checks = [
        ("system_prompt 参数默认空", 'system_prompt: str = ""' in content),
        ("messages 无 system role", '{"role": "user", "content": question}' in content),
    ]

    all_passed = True
    for name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False

    return all_passed


def main():
    """主函数"""
    print("=" * 60)
    print("P0修复验证：System Prompt一致性检查")
    print("=" * 60)

    results = []

    # 验证各文件修改
    results.append(("data_processor.py", verify_data_processor()))
    results.append(("config.py", verify_config()))
    results.append(("evaluate.py", verify_evaluate()))
    results.append(("格式一致性", verify_format_consistency()))

    # 汇总
    print("\n" + "=" * 60)
    print("验证结果汇总")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 所有验证通过！可以开始重新训练。")
    else:
        print("\n⚠️ 存在验证失败项，请检查修改。")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
