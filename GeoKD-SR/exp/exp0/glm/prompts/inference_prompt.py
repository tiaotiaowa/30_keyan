"""
GLM-4.7 推理Prompt模板

用于让GLM-4.7回答地理空间推理问题
"""

# 系统提示词
SYSTEM_PROMPT = """你是一个专业的地理空间推理专家，擅长回答以下类型的问题：
1. 方向关系问题 - 判断两个地理实体之间的相对方位
2. 距离问题 - 计算两个地理实体之间的距离
3. 拓扑关系问题 - 判断包含、相邻、重叠等拓扑关系
4. 复合问题 - 同时涉及方向和距离的问题

请用简洁、准确的语言回答问题。"""

# 推理Prompt模板
INFERENCE_PROMPT_TEMPLATE = """请回答以下地理空间问题。

问题: {question}

回答要求：
- 方向问题：直接说明方向，如"东南方向"、"位于...的西北方向"
- 距离问题：给出具体数值和单位，如"约1200公里"、"大约800千米"
- 拓扑问题：明确说明关系，如"是的，XX位于YY省内部"、"XX与YY相邻"
- 复合问题：同时给出方向和距离，如"东北方向，距离约2000公里"

请直接给出答案，不需要解释推理过程。

答案:"""


def format_inference_prompt(question: str) -> list:
    """
    格式化推理Prompt

    Args:
        question: 问题文本

    Returns:
        messages: 格式化后的消息列表，适用于GLM API
    """
    user_content = INFERENCE_PROMPT_TEMPLATE.format(question=question)

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content}
    ]


def format_simple_prompt(question: str) -> str:
    """
    格式化简单Prompt（单轮对话格式）

    Args:
        question: 问题文本

    Returns:
        格式化后的Prompt字符串
    """
    return INFERENCE_PROMPT_TEMPLATE.format(question=question)


# 测试用例
if __name__ == "__main__":
    # 测试方向问题
    test_directional = "鼓浪屿郑成功纪念馆位于福建省的什么方位？"
    print("="*50)
    print("方向问题测试:")
    print(format_simple_prompt(test_directional))

    # 测试距离问题
    test_metric = "昆明和海口分别是云南省和海南省的省会城市，请问这两座城市之间的直线距离大约是多少公里？"
    print("="*50)
    print("距离问题测试:")
    print(format_simple_prompt(test_metric))

    # 测试拓扑问题
    test_topological = "武汉市是否位于湖北省内部？"
    print("="*50)
    print("拓扑问题测试:")
    print(format_simple_prompt(test_topological))
