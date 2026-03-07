# GeoKD-SR 项目记忆

## 2026-03-07 GLM-5 API调用验证

### 任务概述
验证GLM-5 API调用方式并测试单条数据生成。

### 关键发现
1. **GLM-5是推理模型**，返回两个字段：
   - `content`: 最终答案 (1177字符)
   - `reasoning_content`: 推理过程 (1573字符)
2. **max_tokens设置**: 建议使用4096以上，否则content可能为空
3. **API调用方式正确**，无需修改

### 测试结果
成功生成1条metric类型数据：
- 文件: `outputs/test_single_record_v2.json`
- ID: geosr_metric_001
- 问题: 沧州与珠海之间的直线距离约为多少公里？
- 答案: 沧州与珠海之间的直线距离约为1809公里。
- 推理链: 5步完整 ✅

### 测试脚本
创建了简化测试脚本 `scripts/test_glm5_simple.py`，特点：
- 自动加载.env中的API密钥
- 使用max_tokens=4096确保完整响应
- 优先使用content，为空时使用reasoning_content

### 环境配置
- API Key: 已配置在 `.env` 文件
- API URL: `https://open.bigmodel.cn/api/paas/v4/chat/completions`
- Model: `glm-5`

---

## 2026-03-06 省份-城市映射问题修复

### 问题描述
审查发现284条拓扑语义错误，省份-城市包含关系不正确。例如：
- 陕西省-长沙（长沙实际属于湖南省）
- 浙江省-黑河（黑河实际属于黑龙江省）
- 吉林省-苏州（苏州实际属于江苏省）

### 问题根源
在`scripts/generate_prompts.py`的`_select_topological_entity_pair`方法中，选择省份-城市组合时使用的是完全随机配对逻辑：
```python
return random.choice(provinces), random.choice(cities)
```
这会导致省份和城市之间没有实际的包含关系。

### 修复方案
在`_select_topological_entity_pair`方法中添加了辅助函数`get_valid_province_city_pair()`：
1. 按省份分组所有城市
2. 构建省份名称映射（处理"省"、"市"后缀）
3. 只返回真正有包含关系的省份-城市配对

### 修复的代码位置
- 文件: `D:\30_keyan\GeoKD-SR\scripts\generate_prompts.py`
- 方法: `_select_topological_entity_pair`
- 修改点:
  - easy难度: 第725-726行 (使用valid_pair替代随机配对)
  - medium难度: 第749-750行 (使用valid_pair替代随机配对)
  - hard难度: 第839-840行 (使用valid_pair替代随机配对)
  - 备选方案: 添加valid_pair检查

### 验证结果
测试生成了10个省份-城市配对，全部验证通过：
```
1. 福建省 - 三明 (城市属于: 福建省) [OK]
2. 四川省 - 遂宁 (城市属于: 四川省) [OK]
3. 河北省 - 三河 (城市属于: 河北省) [OK]
...
```

### 注意事项
- `entity_database.py`中的城市-省份映射本身是正确的
- 问题出在生成脚本中的随机配对逻辑
- 修复后需要重新生成数据才能生效

---

## 2026-03-06 数据质量验证任务总结

### 任务概述
作为数据验证Agent，执行了GeoKD-SR实验数据的质量验证任务，检查了`data/prompts/prompts_config_full.json`文件的数据质量。

### 验证结果

**总体评估**: 数据质量未达标，得分88/100

#### 通过的检查项:
1. 总样本数: 11,800个 (达标)
2. 数据集分布: train/dev/test比例正确
3. 空间关系分布: directional/topological/metric/composite分布均衡
4. 难度分布: easy/medium/hard比例合理
5. 拓扑关系子类型: contains/disjoint/adjacent/within/overlap分布合理

#### 发现的问题:

**问题1: 实体对重复率过高 (10.57% vs 目标<5%)**
- 总实体对数: 10,553
- 重复实体对数: 422
- 重复出现次数: 1,247
- 高频重复Top3:
  - 内江-自贡: 41次
  - 吉林-白山: 39次
  - 荆州-黄冈: 38次

**问题2: 存在170个(0,0)坐标**
- 影响169个prompts
- 涉及14个唯一实体:
  - 河流类: 珠江(26)、韩江(13)、嫩江(11)、松花江(11)、澜沧江(10)、额尔古纳河(9)、海河(7)、黄河(7)、长江(3)
  - 湖泊类: 抚仙湖(25)、西湖(10)、呼伦湖(9)
  - 山脉类: 武夷山脉(17)、云岭(12)

### 生成的文件
1. `scripts/validate_data_quality.py` - 数据质量验证脚本
2. `scripts/analyze_detailed_issues.py` - 详细问题分析脚本
3. `outputs/data_quality_report.txt` - 简明验证报告
4. `outputs/detailed_issue_analysis.json` - 详细问题数据
5. `outputs/data_quality_validation_report.md` - 完整验证报告

### 修复建议
1. **高优先级**: 从`entity_database_expanded.json`查找14个实体的正确坐标，或手动补充
2. **中优先级**: 优化实体配对策略，降低重复率到5%以下

### 项目文件结构
```
GeoKD-SR/
├── data/
│   ├── prompts/
│   │   └── prompts_config_full.json (11,800个prompts)
│   ├── entity_database_expanded.json (507个实体)
│   └── geosr_chain/
│       ├── train.jsonl (8,000)
│       ├── dev.jsonl (800)
│       └── test.jsonl (3,000)
├── scripts/
│   ├── validate_data_quality.py
│   └── analyze_detailed_issues.py
└── outputs/
    ├── data_quality_report.txt
    ├── detailed_issue_analysis.json
    └── data_quality_validation_report.md
```
