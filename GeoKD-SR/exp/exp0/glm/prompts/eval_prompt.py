"""
LLM-as-Judge 评估Prompt模板

用于让GLM-4.7评估模型输出的质量
"""

# 评估Prompt模板
EVAL_PROMPT_TEMPLATE = """你是一个地理空间推理专家。请从以下维度评估模型输出的质量。

## 问题
{question}

## 标准答案
{reference_answer}

## 模型输出
{prediction}

## 评估维度

### 1. 推理质量 (reasoning_quality, 1-5分)
- 5分: 推理链完整、逻辑清晰，步骤之间有明确的因果关系
- 4分: 推理基本正确，有小瑕疵但不影响结论
- 3分: 推理方向正确，但关键步骤缺失或跳跃
- 2分: 推理有明显错误，但有一定逻辑
- 1分: 推理完全错误或无推理过程

### 2. 答案完整性 (answer_completeness, 1-5分)
- 5分: 完整回答问题，包含所有必要信息，表述清晰
- 4分: 基本完整，有轻微遗漏但不影响理解
- 3分: 部分回答，关键信息缺失，需要补充
- 2分: 回答不完整，缺少重要内容
- 1分: 未给出有效答案或答非所问

### 3. 空间一致性 (spatial_consistency, 1-5分)
- 5分: 空间描述完全正确，方向/位置/距离准确
- 4分: 基本正确，有小偏差但不影响主要结论
- 3分: 部分正确，存在空间概念混淆
- 2分: 空间描述有明显错误
- 1分: 空间描述完全错误

### 4. 综合评分 (overall_score, 1-5分)
综合考虑以上三个维度给出整体评分。

请严格按JSON格式输出评估结果（不要包含其他任何内容，不要使用markdown代码块）:
{"reasoning_quality": <1-5的整数>, "answer_completeness": <1-5的整数>, "spatial_consistency": <1-5的整数>, "overall_score": <1-5的整数>, "brief_comment": "<一句话评价>"}"""


def format_eval_prompt(question: str, reference: str, prediction: str) -> str:
    """
    格式化评估Prompt

    Args:
        question: 原始问题
        reference: 标准答案
        prediction: 模型预测

    Returns:
        格式化后的Prompt字符串
    """
    return EVAL_PROMPT_TEMPLATE.format(
        question=question,
        reference_answer=reference,
        prediction=prediction
    )


def parse_eval_response(response: str) -> dict:
    """
    解析评估响应

    Args:
        response: LLM返回的JSON字符串

    Returns:
        解析后的字典，包含各项评分
    """
    import json
    import re

    # 尝试直接解析
    try:
        return json.loads(response.strip())
    except json.JSONDecodeError:
        pass

    # 尝试提取JSON部分
    json_pattern = r'\{[^{}]*"reasoning_quality"[^{}]*\}'
    match = re.search(json_pattern, response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # 尝试提取各维度分数
    result = {
        "reasoning_quality": 3,
        "answer_completeness": 3,
        "spatial_consistency": 3,
        "overall_score": 3,
        "brief_comment": "解析失败，使用默认分数"
    }

    patterns = {
        "reasoning_quality": r'"reasoning_quality"\s*:\s*(\d)',
        "answer_completeness": r'"answer_completeness"\s*:\s*(\d)',
        "spatial_consistency": r'"spatial_consistency"\s*:\s*(\d)',
        "overall_score": r'"overall_score"\s*:\s*(\d)'
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, response)
        if match:
            result[key] = int(match.group(1))

    return result


# 测试用例
if __name__ == "__main__":
    # 测试评估Prompt
    question = "鼓浪屿郑成功纪念馆位于福建省的什么方位？"
    reference = "东南方向"
    prediction = "位于东南方向"

    prompt = format_eval_prompt(question, reference, prediction)
    print("="*60)
    print("评估Prompt测试:")
    print(prompt)

    # 测试解析
    test_response = '''{"reasoning_quality": 4, "answer_completeness": 5, "spatial_consistency": 5, "overall_score": 4, "brief_comment": "答案准确，方向正确"}'''

    print("="*60)
    print("解析测试:")
    result = parse_eval_response(test_response)
    print(f"解析结果: {result}")
