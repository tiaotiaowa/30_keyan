# -*- coding: utf-8 -*-
"""
GLM-5 数据生成测试脚本
测试从prompts生成1条数据
"""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
import json

API_KEY = "809fc06b8b744d719d870463211f7dd0.0Lc5qs0W20PMzjfW"
CHAT_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

def test_glm5_chat(prompt: str, max_tokens: int = 2000):
    """测试GLM-5 Chat API"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "glm-5",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }

    print(f"\n发送请求到GLM-5...")
    print(f"Prompt长度: {len(prompt)} 字符")

    response = requests.post(CHAT_URL, headers=headers, json=payload, timeout=120)

    if response.status_code == 200:
        result = response.json()
        message = result["choices"][0]["message"]
        content = message.get("content", "")
        reasoning = message.get("reasoning_content", "")

        print(f"\nAPI调用成功!")
        print(f"推理内容长度: {len(reasoning)} 字符")
        print(f"回复内容长度: {len(content)} 字符")

        # 如果content为空，使用reasoning_content
        final_content = content if content else reasoning

        if reasoning:
            print(f"\n推理过程预览: {reasoning[:200]}...")
        print(f"\n最终回复: {final_content[:500]}...")

        return final_content
    else:
        print(f"API调用失败: {response.status_code}")
        print(f"错误信息: {response.text}")
        return None

def test_generate_one_record():
    """测试生成1条地理空间关系数据"""
    from scripts.generate_data_glm5 import GLM5Client, GeoSRDataGenerator, EntityDatabase

    print("=" * 60)
    print("GLM-5 地理空间关系数据生成测试")
    print("=" * 60)

    # 初始化客户端
    client = GLM5Client(api_key=API_KEY)
    print(f"\n1. GLM5Client初始化成功")
    print(f"   API Key: {API_KEY[:15]}...")
    print(f"   模型: {client.model}")

    # 初始化实体数据库
    db = EntityDatabase()
    print(f"\n2. EntityDatabase初始化成功")
    print(f"   实体数量: {len(db.entities)}")

    # 初始化数据生成器
    generator = GeoSRDataGenerator(glm5_client=client, entity_db=db)
    print(f"\n3. GeoSRDataGenerator初始化成功")

    # 生成1条数据
    print(f"\n4. 开始生成1条测试数据...")

    try:
        # 先检查实体数据
        entities_with_coords = db.get_entities_with_coords()
        print(f"   带坐标的实体数量: {len(entities_with_coords)}")

        if len(entities_with_coords) < 2:
            print("[错误] 实体数量不足，无法生成数据")
            return

        record = generator.generate_single_record()

        if record:
            print(f"\n✓ 数据生成成功!")
            print(f"\n生成的数据:")
            print(json.dumps(record, ensure_ascii=False, indent=2)[:1000])

            # 保存到文件
            output_file = "outputs/test_single_record.json"
            os.makedirs("outputs", exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
            print(f"\n数据已保存到: {output_file}")
        else:
            print(f"\n✗ 数据生成失败 - API返回为空")

    except Exception as e:
        print(f"\n✗ 生成过程出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 先测试基础API调用
    print("步骤1: 测试基础API调用")
    test_prompt = "请回答：北京在上海的什么方向？"
    result = test_glm5_chat(test_prompt, max_tokens=2000)

    if result:
        print("\n" + "=" * 60)
        print("步骤2: 测试数据生成")
        test_generate_one_record()
    else:
        print("\n基础API测试失败，请检查API密钥和网络连接")
