#!/usr/bin/env python3
"""测试JSON解析功能"""
import json
import re

# 测试响应
test_response = '''
这是一一个关于地理位置的简单问题。

已知实体：北京、上海

已知关系：北京位于上海的东北方向
上海位于北京的东南方向

请返回JSON格式的答案答案答案。
答案: "是的，北京位于上海的东北方向"
'''

# 测试解析
result = extract_json_from_response(test_response)
print(f"解析结果: {result}")
