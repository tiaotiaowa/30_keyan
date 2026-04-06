#!/usr/bin/env python3
"""
DeepSeek-V3.2 API 连通性测试 + 小样本生成测试

使用阿里云百炼 DashScope OpenAI 兼容模式调用 deepseek-v3.2
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from openai import OpenAI

# ============================================================
# 配置
# ============================================================
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
API_KEY = "sk-f2ee8087b5fe4221a3ea641e00fb2137"
MODEL = "deepseek-v3.2"

# 测试提示词目录
BASE_DIR = Path(r"D:\gis_data\output\问题生成模版设计")
TEST_PROMPTS_DIR = BASE_DIR / "test_prompts"
TEST_RESULTS_DIR = BASE_DIR / "test_results"

# 小样本测试选取的文件
TEST_FILES = [
    "test_directional_positive.md",
    "test_topo_contains_positive.md",
]

# ============================================================
# API 客户端初始化
# ============================================================
client = OpenAI(
    base_url=BASE_URL,
    api_key=API_KEY,
)


def test_connectivity():
    """Step 1: 连通性测试"""
    print("=" * 60)
    print("Step 1: API 连通性测试")
    print("-" * 40)

    try:
        start = time.time()
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "你好，请回复1+1=?"}],
            temperature=1.0,
            top_p=0.95,
            max_tokens=256,
        )
        elapsed = time.time() - start
        content = response.choices[0].message.content
        print(f"  状态: 成功")
        print(f"  响应: {content}")
        print(f"  延迟: {elapsed:.2f}s")
        print(f"  模型: {response.model}")
        if response.usage:
            print(f"  Token用量: prompt={response.usage.prompt_tokens}, completion={response.usage.completion_tokens}")
        return True
    except Exception as e:
        print(f"  连通性测试失败: {e}")
        return False


def check_test_prompts():
    """Step 2: 检查测试提示词文件"""
    print("\n" + "=" * 60)
    print("Step 2: 检查测试提示词文件")
    print("-" * 40)
    if not TEST_PROMPTS_DIR.exists():
        print(f"  错误: 目录不存在: {TEST_PROMPTS_DIR}")
        print(f"  请先运行: python generate_test_prompts.py")
        return False

    existing_files = list(TEST_PROMPTS_DIR.glob("*.md"))
    print(f"  找到 {len(existing_files)} 个测试提示词文件")

    missing = []
    for f in TEST_FILES:
        if not (TEST_PROMPTS_DIR / f).exists():
            missing.append(f)

    if missing:
        print(f"  缺少文件: {missing}")
        print(f"  请先运行: python generate_test_prompts.py")
        return False

    print(f"  所有必要文件存在")
    return True


def run_small_sample_test():
    """Step 3: 小样本测试"""
    print("\n" + "=" * 60)
    print("Step 3: 小样本生成测试")
    print("=" * 60)

    os.makedirs(TEST_RESULTS_DIR, exist_ok=True)

    results = []

    for test_file in TEST_FILES:
        prompt_path = TEST_PROMPTS_DIR / test_file
        print(f"\n--- 测试: {test_file} ---")

        # 读取提示词
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_text = f.read().strip()

        print(f"  提示词长度: {len(prompt_text)} 字符")

        # 调用 API
        try:
            start = time.time()
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt_text}],
                temperature=1.0,
                top_p=0.95,
                max_tokens=65536,
                extra_body={
                    "enable_thinking": True,
                    "thinking_budget": 32768,
                },
            )
            elapsed = time.time() - start

            # 提取响应
            raw_content = response.choices[0].message.content
            reasoning_content = getattr(response.choices[0].message, 'reasoning_content', None)

            print(f"  延迟: {elapsed:.1f}s")
            if response.usage:
                print(f"  Prompt tokens: {response.usage.prompt_tokens}")
                print(f"  Completion tokens: {response.usage.completion_tokens}")

            # 尝试解析 JSON
            json_valid = False
            parsed_json = None
            json_error = None

            # 尝试直接解析
            try:
                parsed_json = json.loads(raw_content)
                json_valid = True
            except json.JSONDecodeError:
                # 尝试提取 ```json ... ``` 代码块
                match = re.search(r'```json\s*\n?(.*?)\n?```', raw_content, re.DOTALL)
                if match:
                    try:
                        parsed_json = json.loads(match.group(1).strip())
                        json_valid = True
                    except json.JSONDecodeError as e:
                        json_error = str(e)
                else:
                    # 尝试提取第一个完整的 JSON 对象
                    match = re.search(r'\{[\s\S]*\}', raw_content)
                    if match:
                        try:
                            parsed_json = json.loads(match.group(0))
                            json_valid = True
                        except json.JSONDecodeError as e:
                            json_error = str(e)
                    else:
                        json_error = "未找到JSON内容"

            # 验证 JSON 结构
            structure_valid = False
            missing_keys = []
            if json_valid and parsed_json:
                required_keys = {"true_false", "choice", "fill_blank", "open_qa"}
                actual_keys = set(parsed_json.keys())
                missing_keys = list(required_keys - actual_keys)
                structure_valid = len(missing_keys) == 0

            # 保存结果
            result = {
                "test_file": test_file,
                "elapsed_seconds": round(elapsed, 2),
                "json_valid": json_valid,
                "structure_valid": structure_valid,
                "missing_keys": missing_keys,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                    "completion_tokens": response.usage.completion_tokens if response.usage else None,
                    "total_tokens": response.usage.total_tokens if response.usage else None,
                },
                "parsed_json": parsed_json,
                "raw_content": raw_content,
                "reasoning_content": reasoning_content,
                "json_error": json_error,
            }
            results.append(result)

            # 保存到文件
            result_filename = test_file.replace(".md", "_result.json")
            result_path = TEST_RESULTS_DIR / result_filename
            # 不保存 raw_content 和 reasoning 到 JSON 文件（太大）
            save_data = {k: v for k, v in result.items() if k not in ("raw_content", "reasoning_content")}
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            print(f"  结果已保存: {result_path}")

            # 额外保存完整响应
            full_result_path = TEST_RESULTS_DIR / result_filename.replace("_result.json", "_full_response.txt")
            with open(full_result_path, 'w', encoding='utf-8') as f:
                if reasoning_content:
                    f.write("=== 思考过程 ===\n")
                    f.write(reasoning_content)
                    f.write("\n\n=== 生成结果 ===\n")
                f.write(raw_content)

            status = "JSON有效, 结构完整" if structure_valid else ("JSON有效, 结构缺字段: " + str(missing_keys) if json_valid else "JSON解析失败")
            print(f"  状态: {status}")

        except Exception as e:
            print(f"  API调用失败: {e}")
            results.append({
                "test_file": test_file,
                "error": str(e),
                "elapsed_seconds": None,
            })

    return results


def generate_report(results):
    """Step 4: 生成汇总报告"""
    print("\n" + "=" * 60)
    print("Step 4: 汇总报告")
    print("=" * 60)

    success_count = sum(1 for r in results if r.get("json_valid") and r.get("structure_valid"))
    json_fail_count = sum(1 for r in results if r.get("json_valid") and not r.get("structure_valid"))
    error_count = sum(1 for r in results if "error" in r)

    total_tests = len(results)
    avg_latency = None
    latencies = [r["elapsed_seconds"] for r in results if r.get("elapsed_seconds")]
    if latencies:
        avg_latency = sum(latencies) / len(latencies)

    report_lines = [
        "# DeepSeek-V3.2 小样本测试报告",
        "",
        f"- 测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 模型: {MODEL}",
        f"- 测试模板数: {total_tests}",
        f"- 成功(结构完整): {success_count}",
        f"- JSON有效但结构不完整: {json_fail_count}",
        f"- API调用失败: {error_count}",
        "",
        "## 详细结果",
        "",
    ]

    for r in results:
        report_lines.append(f"### {r['test_file']}")
        report_lines.append("")
        if "error" in r:
            report_lines.append(f"- 状态: API调用失败")
            report_lines.append(f"- 错误: {r['error']}")
        else:
            status = "成功" if r.get("structure_valid") else ("JSON结构不完整" if r.get("json_valid") else "JSON解析失败")
            report_lines.append(f"- 状态: {status}")
            report_lines.append(f"- 延迟: {r.get('elapsed_seconds', 'N/A')}s")
            usage = r.get("usage", {})
            if usage.get("prompt_tokens"):
                report_lines.append(f"- Prompt tokens: {usage['prompt_tokens']}")
                report_lines.append(f"- Completion tokens: {usage['completion_tokens']}")
                report_lines.append(f"- Total tokens: {usage['total_tokens']}")
            if r.get("missing_keys"):
                report_lines.append(f"- 缺少字段: {r['missing_keys']}")
            if r.get("json_error"):
                report_lines.append(f"- JSON错误: {r['json_error']}")
            # 展示生成的题目
            parsed = r.get("parsed_json")
            if parsed:
                report_lines.append("")
                report_lines.append("**生成结果预览:**")
                report_lines.append("```json")
                report_lines.append(json.dumps(parsed, ensure_ascii=False, indent=2)[:2000])
                if len(json.dumps(parsed, ensure_ascii=False, indent=2)) > 2000:
                    report_lines.append("... (截断)")
                report_lines.append("```")
        report_lines.append("")

    report_lines.append("## 统计汇总")
    report_lines.append("")
    if avg_latency:
        report_lines.append(f"- 平均延迟: {avg_latency:.1f}s")
    total_prompt = sum(r.get("usage", {}).get("prompt_tokens", 0) or 0 for r in results)
    total_completion = sum(r.get("usage", {}).get("completion_tokens", 0) or 0 for r in results)
    total_total = sum(r.get("usage", {}).get("total_tokens", 0) or 0 for r in results)
    report_lines.append(f"- 总 Prompt tokens: {total_prompt}")
    report_lines.append(f"- 总 Completion tokens: {total_completion}")
    report_lines.append(f"- 总 Token 用量: {total_total}")

    report_content = "\n".join(report_lines)

    report_path = BASE_DIR / "小样本测试报告.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_content)
    print(f"  报告已保存: {report_path}")
    return report_content


def main():
    # 强制 UTF-8 输出
    sys.stdout.reconfigure(encoding='utf-8')

    print("DeepSeek-V3.2 API 测试脚本")
    print(f"模型: {MODEL}")
    print(f"API地址: {BASE_URL}")
    print()

    # Step 1
    if not test_connectivity():
        print("\nAPI 连通失败，退出。")
        return

    # Step 2
    if not check_test_prompts():
        print("\n测试提示词不完整，退出。")
        return

    # Step 3
    results = run_small_sample_test()

    # Step 4
    if results:
        generate_report(results)
    else:
        print("无测试结果")

    print("\n完成!")


if __name__ == "__main__":
    main()
