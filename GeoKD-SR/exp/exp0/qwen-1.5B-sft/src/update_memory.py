"""更新 memory.md"""

new_content = """
---

## 2026-03-21 数据处理模块创建完成

### 任务概述
在 GeoKD-SR/exp/exp0/qwen-1.5B-sft/src/data_processor.py 创建数据处理模块,用于将 GeoKD-SR 原始数据转换为 Qwen2.5 ChatML 格式。

### 模块功能

1. **ChatMLConverter 类**: 格式转换
   - 将 GeoKD-SR 数据(question, answer)转换为 ChatML 格式
   - 使用 Qwen2.5 的 apply_chat_template 方法
   - 正确构造 labels (system 和 user 段设为 -100,只有 assistant 段计算损失)

2. **GeoSRDataProcessor 类**: 数据加载
   - 继承自 torch.utils.data.Dataset
   - 支持 JSONL 格式数据加载
   - 支持 splits 和 split_coords 两种数据版本
   - 提供 get_statistics() 方法获取数据集统计信息

3. **DataCollatorForGeoSR 类**: 数据整理
   - 处理 batch 内的 padding
   - 支持 pad_to_multiple_of 优化

4. **create_dataloaders() 函数**: 便捷创建数据加载器

### 测试结果

- 总样本数: 9463 (训练集)
- 空间关系类型: topological(2673), directional(2347), metric(2562), composite(1881)
- 难度分布: easy(3035), medium(4175), hard(2253)
- 平均问题长度: 35.64 字符
- 平均答案长度: 12.95 字符

### 输出文件
- GeoKD-SR/exp/exp0/qwen-1.5B-sft/src/data_processor.py
"""

# 追加到 memory.md
with open("D:/30_keyan/memory.md", "a", encoding="utf-8") as f:
    f.write(new_content)

print("已更新 memory.md")
