"""
测试 GLM-4.7 API 连接
使用 zai-sdk 验证 API 调用是否正常
"""

import os
import sys
from pathlib import Path

# 加载 .env 文件
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(env_path)

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from zai import ZhipuAiClient

def test_glm47_api():
    """测试 GLM-4.7 API 连接"""
    print("=" * 60)
    print("测试 GLM-4.7 API 连接 (zai-sdk)")
    print("=" * 60)

    # 获取 API Key
    api_key = os.getenv("ZHIPUAI_API_KEY")
    if not api_key:
        print("错误: 请设置环境变量 ZHIPUAI_API_KEY")
        return False

    print(f"API Key: {api_key[:15]}...")

    # 初始化客户端
    try:
        client = ZhipuAiClient(api_key=api_key)
        print("客户端初始化成功")
    except Exception as e:
        print(f"客户端初始化失败: {e}")
        return False

    # 测试请求 - 按照用户提供的参考代码格式
    test_messages = [
        {"role": "user", "content": "请用一句话回答：北京位于中国的哪个方向？"}
    ]

    print("\n发送测试请求到 glm-4.7...")
    print(f"消息: {test_messages}")

    try:
        response = client.chat.completions.create(
            model="glm-4.7",
            messages=test_messages,
            max_tokens=512,
            temperature=0.7,
        )

        print("\n响应对象类型:", type(response))
        print("响应对象:", response)

        # 获取回复内容
        if hasattr(response, 'choices') and response.choices:
            message = response.choices[0].message
            print("\nMessage 对象:", message)
            content = message.content if hasattr(message, 'content') else str(message)
            print(f"\n回复内容: {content}")

            if hasattr(response, 'usage'):
                print(f"Token 使用: {response.usage}")

            return True
        else:
            print("错误: 响应中没有 choices")
            return False

    except Exception as e:
        print(f"API 调用错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_glm47_api()
    print("\n" + "=" * 60)
    print("测试结果:", "成功" if success else "失败")
    print("=" * 60)
    sys.exit(0 if success else 1)
