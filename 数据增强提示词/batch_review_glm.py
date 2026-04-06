#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GeoKD-SR 数据批量审核脚本
使用GLM-4.7模型对地理空间推理数据进行批量审核

功能：
- 每次处理5条数据
- 支持断点续传
- 错误重试机制
- 进度记录和日志
"""

import os
import sys
import json
import time
import getpass
import argparse
from datetime import datetime
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("错误：未安装anthropic库，请运行: pip install anthropic")
    sys.exit(1)


# ==================== 配置区 ====================

# 模型配置
MODEL = "glm-5"
BASE_URL = "https://open.bigmodel.cn/api/anthropic"
BATCH_SIZE = 1  # 每批处理5条
MAX_RETRIES = 3  # 最大重试次数
TIMEOUT = 300    # 超时时间（秒）
MAX_TOKENS = 32000  # 最大输出token数

# 文件路径（使用正斜杠兼容Windows和Linux）
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent

INPUT_FILE = str(PROJECT_DIR / "data" / "final" / "final_1_final.jsonl")
OUTPUT_FILE = str(PROJECT_DIR / "data" / "final" / "final_1_reviewed.jsonl")
CHECKPOINT_FILE = str(SCRIPT_DIR / "review_checkpoint.json")
ERROR_LOG = str(SCRIPT_DIR / "review_errors.log")
PROMPT_FILE = str(Path(PROJECT_DIR).parent / "审查提示词.md")


# ==================== 工具函数 ====================

def log_message(message, level="INFO"):
    """打印带时间戳的日志消息"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def log_error(error_message, data=None):
    """记录错误到日志文件"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(ERROR_LOG, 'a', encoding='utf-8') as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"[{timestamp}] ERROR: {error_message}\n")
        if data:
            f.write(f"相关数据:\n{json.dumps(data, ensure_ascii=False, indent=2)}\n")


def load_checkpoint():
    """加载断点记录"""
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log_message(f"加载断点文件失败: {e}", "WARNING")
    return {"processed_count": 0, "success_count": 0, "failed_count": 0}


def save_checkpoint(checkpoint):
    """保存断点记录"""
    checkpoint["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)


def load_prompt():
    """加载审查提示词"""
    if not os.path.exists(PROMPT_FILE):
        raise FileNotFoundError(f"审查提示词文件不存在: {PROMPT_FILE}")

    with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # 提取```之间的内容（如果有的话）
    if '```' in content:
        # 找到第一个```之后的内容
        parts = content.split('```', 2)
        if len(parts) >= 2:
            # 去除可能的语言标识符（如markdown）
            prompt = parts[1]
            if '\n' in prompt:
                first_line_end = prompt.index('\n')
                if not prompt[:first_line_end].strip() or prompt[:first_line_end].strip().isalpha():
                    prompt = prompt[first_line_end+1:]
            content = prompt.strip()

    return content


def load_data(start_index=0):
    """加载JSONL数据"""
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(f"输入文件不存在: {INPUT_FILE}")

    data = []
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i < start_index:
                continue
            line = line.strip()
            if line:
                try:
                    item = json.loads(line)
                    data.append(item)
                except json.JSONDecodeError as e:
                    log_error(f"第{i+1}行JSON解析失败: {e}", {"line": line[:200]})

    return data


def parse_response(response_text):
    """解析API返回的JSON数据"""
    results = []

    # 清理响应文本
    text = response_text.strip()

    # 尝试提取JSON对象（每行一个）
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 尝试解析JSON
        try:
            # 处理可能的前缀（如"json"）
            if line.startswith('```'):
                continue
            if line.startswith('json'):
                line = line[4:].strip()

            # 移除可能的代码块标记
            if line.endswith('```'):
                line = line[:-3].strip()

            if line.startswith('{') and line.endswith('}'):
                item = json.loads(line)
                results.append(item)
        except json.JSONDecodeError:
            # 尝试查找JSON对象的开始和结束
            start = line.find('{')
            end = line.rfind('}')
            if start != -1 and end != -1 and end > start:
                try:
                    item = json.loads(line[start:end+1])
                    results.append(item)
                except json.JSONDecodeError:
                    continue

    return results


def call_api(client, system_prompt, input_data, retry_count=0):
    """调用GLM-4.7 API进行审核"""
    try:
        # 构建用户输入
        user_content = "\n".join([json.dumps(item, ensure_ascii=False) for item in input_data])

        # 替换提示词中的{input}占位符
        full_system_prompt = system_prompt.replace("{input}", user_content)

        # 如果没有占位符，则将数据附加到用户消息
        if "{input}" not in system_prompt:
            # 调用API（数据作为用户消息）
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
                timeout=TIMEOUT
            )
        else:
            # 调用API（数据已嵌入系统提示词）
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": "请审核以下5条数据并输出修复后的JSON:\n" + user_content}],
                timeout=TIMEOUT
            )

        # 提取响应文本
        response_text = response.content[0].text
        return response_text, None

    except anthropic.APIStatusError as e:
        error_msg = f"API错误 (状态码: {e.status_code}): {e.message}"
        if retry_count < MAX_RETRIES:
            log_message(f"{error_msg}，正在重试 ({retry_count + 1}/{MAX_RETRIES})...", "WARNING")
            time.sleep(5 * (retry_count + 1))  # 指数退避
            return call_api(client, system_prompt, input_data, retry_count + 1)
        return None, error_msg

    except anthropic.APITimeoutError:
        error_msg = f"API超时 (超时时间: {TIMEOUT}秒)"
        if retry_count < MAX_RETRIES:
            log_message(f"{error_msg}，正在重试 ({retry_count + 1}/{MAX_RETRIES})...", "WARNING")
            time.sleep(10 * (retry_count + 1))
            return call_api(client, system_prompt, input_data, retry_count + 1)
        return None, error_msg

    except Exception as e:
        error_msg = f"未知错误: {str(e)}"
        if retry_count < MAX_RETRIES:
            log_message(f"{error_msg}，正在重试 ({retry_count + 1}/{MAX_RETRIES})...", "WARNING")
            time.sleep(5 * (retry_count + 1))
            return call_api(client, system_prompt, input_data, retry_count + 1)
        return None, error_msg


def save_results(results, output_file):
    """保存审核结果到文件"""
    with open(output_file, 'a', encoding='utf-8') as f:
        for item in results:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')


def print_progress(checkpoint, total_count):
    """打印进度信息"""
    processed = checkpoint["processed_count"]
    success = checkpoint["success_count"]
    failed = checkpoint["failed_count"]
    progress = (processed / total_count * 100) if total_count > 0 else 0

    print("\n" + "="*50)
    print(f"[进度] 处理进度: {processed}/{total_count} ({progress:.1f}%)")
    print(f"[成功] 成功: {success}  [失败] 失败: {failed}")
    print("="*50 + "\n")


# ==================== 主函数 ====================

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='GeoKD-SR 数据批量审核脚本')
    parser.add_argument('--resume', action='store_true', help='从断点继续处理')
    parser.add_argument('--test', type=int, default=0, help='测试模式：只处理前N条数据')
    args = parser.parse_args()

    # 打印欢迎信息
    print("\n" + "="*60)
    print("[GeoKD-SR] 数据批量审核脚本")
    print("="*60)
    print(f"模型: {MODEL}")
    print(f"输入文件: {INPUT_FILE}")
    print(f"输出文件: {OUTPUT_FILE}")
    print(f"批处理大小: {BATCH_SIZE}")
    print("="*60 + "\n")

    # 获取API密钥
    api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        api_key = os.environ.get("ZHIPU_API_KEY")

    if not api_key:
        print("[警告] 未检测到API密钥环境变量")
        api_key = getpass.getpass("请输入智谱API密钥（输入后不会显示）: ").strip()

    if not api_key:
        print("[错误] 未提供API密钥")
        sys.exit(1)

    # 初始化客户端
    client = anthropic.Anthropic(
        api_key=api_key,
        base_url=BASE_URL
    )

    # 加载审查提示词
    log_message("正在加载审查提示词...")
    try:
        system_prompt = load_prompt()
        log_message(f"审查提示词加载成功 (长度: {len(system_prompt)} 字符)")
    except Exception as e:
        log_message(f"加载审查提示词失败: {e}", "ERROR")
        sys.exit(1)

    # 加载断点或从头开始
    checkpoint = load_checkpoint()
    start_index = checkpoint["processed_count"] if args.resume else 0

    if args.resume and start_index > 0:
        log_message(f"从断点继续，已处理: {start_index} 条")

    # 加载数据
    log_message("正在加载数据...")
    try:
        all_data = load_data(0)  # 加载全部数据
        total_count = len(all_data)
        log_message(f"数据加载完成，共 {total_count} 条")

        # 测试模式
        if args.test > 0:
            all_data = all_data[:args.test]
            total_count = len(all_data)
            log_message(f"测试模式：只处理前 {total_count} 条数据")
    except Exception as e:
        log_message(f"加载数据失败: {e}", "ERROR")
        sys.exit(1)

    # 如果从头开始，清空输出文件
    if not args.resume or start_index == 0:
        # 确保输出目录存在
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        # 清空输出文件
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            pass
        checkpoint = {"processed_count": 0, "success_count": 0, "failed_count": 0}

    # 分批处理
    log_message("开始批量处理...")
    print_progress(checkpoint, total_count)

    # 从start_index开始处理
    data_to_process = all_data[start_index:]
    batch_count = 0

    for i in range(0, len(data_to_process), BATCH_SIZE):
        batch = data_to_process[i:i + BATCH_SIZE]
        batch_num = (start_index + i) // BATCH_SIZE + 1
        batch_count += 1

        log_message(f"正在处理批次 {batch_num} (数据 {start_index + i + 1}-{start_index + i + len(batch)})...")

        # 调用API
        response_text, error = call_api(client, system_prompt, batch)

        if error:
            log_message(f"批次 {batch_num} 处理失败: {error}", "ERROR")
            log_error(f"批次 {batch_num} API调用失败", batch)
            checkpoint["failed_count"] += len(batch)
            checkpoint["processed_count"] += len(batch)
            save_checkpoint(checkpoint)
            continue

        # 解析响应
        try:
            reviewed_data = parse_response(response_text)

            if len(reviewed_data) != len(batch):
                log_message(f"警告：返回数据数量不匹配 (期望: {len(batch)}, 实际: {len(reviewed_data)})", "WARNING")
                log_error(f"批次 {batch_num} 返回数量不匹配", {
                    "expected": len(batch),
                    "actual": len(reviewed_data),
                    "response": response_text[:1000]
                })

                # 如果数量不匹配，尝试保留原始数据
                if len(reviewed_data) < len(batch):
                    # 补充缺失的数据（保留原始数据）
                    for j in range(len(reviewed_data), len(batch)):
                        reviewed_data.append(batch[j])

            # 保存结果
            save_results(reviewed_data, OUTPUT_FILE)

            checkpoint["success_count"] += len(reviewed_data)
            checkpoint["processed_count"] += len(batch)
            save_checkpoint(checkpoint)

            log_message(f"批次 {batch_num} 处理成功，已保存 {len(reviewed_data)} 条数据")

            # 每10个批次打印一次进度
            if batch_count % 10 == 0:
                print_progress(checkpoint, total_count)

        except Exception as e:
            log_message(f"批次 {batch_num} 解析失败: {e}", "ERROR")
            log_error(f"批次 {batch_num} 响应解析失败", {
                "error": str(e),
                "response": response_text[:2000]
            })
            checkpoint["failed_count"] += len(batch)
            checkpoint["processed_count"] += len(batch)
            save_checkpoint(checkpoint)

        # 短暂延迟，避免API限流
        time.sleep(1)

    # 处理完成
    print("\n" + "="*60)
    print("[完成] 批量处理完成！")
    print("="*60)
    print(f"[统计] 总计处理: {checkpoint['processed_count']} 条")
    print(f"[成功] 成功: {checkpoint['success_count']} 条")
    print(f"[失败] 失败: {checkpoint['failed_count']} 条")
    print(f"[输出] 输出文件: {OUTPUT_FILE}")
    print(f"[日志] 错误日志: {ERROR_LOG}")
    print("="*60 + "\n")

    # 更新memory.md
    memory_file = PROJECT_DIR.parent / "memory.md"
    if memory_file.exists():
        try:
            with open(memory_file, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"\n\n## {timestamp}\n")
                f.write("### GeoKD-SR 数据批量审核\n")
                f.write(f"- 处理数据: {checkpoint['processed_count']} 条\n")
                f.write(f"- 成功: {checkpoint['success_count']} 条\n")
                f.write(f"- 失败: {checkpoint['failed_count']} 条\n")
                f.write(f"- 输出文件: {OUTPUT_FILE}\n")
        except Exception as e:
            log_message(f"更新memory.md失败: {e}", "WARNING")


if __name__ == "__main__":
    main()
