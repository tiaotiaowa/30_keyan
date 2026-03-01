# GeoKD-SR 数据管理工具使用指南

## 概述

GeoKD-SR 数据管理工具提供完整的数据管理功能，包括：
- 数据验证
- 数据统计
- 格式转换
- 数据浏览
- 缓存管理

## 安装依赖

```bash
# 核心依赖
pip install pyyaml

# 可选依赖（用于可视化）
pip install matplotlib
```

## 配置文件

配置文件位于 `configs/data.yaml`，包含以下配置项：

```yaml
data:
  base_dir: "data"              # 数据基础目录
  geosr_chain: "data/geosr_chain"
  geosr_bench: "data/geosr_bench"

validation:
  required_fields:              # 必填字段
    - "id"
    - "spatial_relation"
    - "entities"
  spatial_relations:            # 有效的空间关系类型
    - "within"
    - "contains"
    - "intersects"
    # ...

cache:
  cache_dir: ".cache/data_manager"
  max_size_mb: 1000

statistics:
  output_dir: "outputs/statistics"
  visualize: true
  save_report: true
```

## 功能使用

### 1. 列出所有数据文件

```bash
python scripts/data_manager.py list
```

输出示例：
```
数据文件列表:
============================================================

geosr_chain:
  - data/geosr_chain/train.jsonl
  - data/geosr_chain/entity_database.json

geosr_bench:
  - data/geosr_bench/benchmark.json
============================================================
```

### 2. 验证数据

验证JSONL文件：
```bash
python scripts/data_manager.py verify --data_path data/geosr_chain/train.jsonl
```

验证JSON文件：
```bash
python scripts/data_manager.py verify --data_path data/geosr_chain/entity_database.json
```

静默模式（减少输出）：
```bash
python scripts/data_manager.py verify --data_path data/geosr_chain/train.jsonl --quiet
```

验证输出示例：
```
============================================================
数据验证结果
============================================================
文件路径: data/geosr_chain/train.jsonl
文件类型: .jsonl
状态: ✓ 通过

总计记录: 1000
有效记录: 995
无效记录: 5

错误信息 (5):
  - 行 45: 缺少必填字段 entities
  - 行 123: 空实体列表
  - 行 256: 无效的空间关系类型
  - 行 489: 实体缺少 id 字段
  - 行 789: 实体缺少 name 字段
============================================================
```

### 3. 数据统计

```bash
# 基本统计
python scripts/data_manager.py stats --data_path data/geosr_chain/train.jsonl

# 保存统计报告
python scripts/data_manager.py stats --data_path data/geosr_chain/train.jsonl --output_file my_stats.json

# 不生成可视化图表
python scripts/data_manager.py stats --data_path data/geosr_chain/train.jsonl --no-visualize
```

统计输出示例：
```
============================================================
数据统计报告
============================================================
文件: data/geosr_chain/train.jsonl
总记录数: 1000

空间关系分布:
  within: 350 (35.00%)
  contains: 280 (28.00%)
  intersects: 150 (15.00%)
  near: 120 (12.00%)
  north_of: 50 (5.00%)
  south_of: 30 (3.00%)
  east_of: 12 (1.20%)
  west_of: 8 (0.80%)

实体类型分布:
  POI: 2100
  City: 850
  Street: 650
  Landmark: 320
  River: 180

实体数量分布:
  2 个实体: 650 条记录
  3 个实体: 250 条记录
  4 个实体: 80 条记录
  5 个实体: 20 条记录

数据质量:
  missing_id: 0
  missing_relation: 5
  missing_entities: 0
  empty_entities: 3

生成时间: 2026-03-01 14:30:00
============================================================

统计报告已保存到: outputs/statistics/statistics_20260301_143000.json
可视化图表已保存到: outputs/statistics/visualization_20260301_143000.png
```

### 4. 格式转换

```bash
# JSON 转 JSONL
python scripts/data_manager.py convert --input data.json --output data.jsonl

# JSONL 转 JSON
python scripts/data_manager.py convert --input data.jsonl --output data.json

# 批量转换示例
for file in data/*.json; do
    python scripts/data_manager.py convert --input "$file" --output "${file%.json}.jsonl"
done
```

### 5. 清理缓存

```bash
python scripts/data_manager.py clean
```

输出示例：
```
✓ 已清理 150 个缓存文件
  缓存目录: .cache/data_manager
```

## Python API 使用

### 基本使用

```python
from scripts.data_manager import DataManager

# 创建数据管理器
manager = DataManager()

# 或者指定配置文件
manager = DataManager(config_path="configs/data.yaml")
```

### 数据验证

```python
# 验证数据
result = manager.verify_data("data/geosr_chain/train.jsonl")

# 检查结果
if result['valid']:
    print(f"✓ 数据验证通过")
    print(f"总记录数: {result['total']}")
    print(f"有效记录: {result['valid_count']}")
else:
    print(f"✗ 数据验证失败")
    print(f"错误: {result['errors']}")
```

### 数据统计

```python
# 生成统计信息
stats = manager.show_statistics(
    "data/geosr_chain/train.jsonl",
    output_file="my_stats.json",
    visualize=True
)

# 访问统计数据
print(f"总记录数: {stats['total_records']}")
print(f"空间关系分布: {stats['spatial_relations']}")
print(f"实体类型分布: {stats['entity_types']}")
```

### 格式转换

```python
# 转换格式
success = manager.convert_format(
    input_path="data/input.json",
    output_path="data/output.jsonl"
)

if success:
    print("✓ 转换成功")
```

### 列出数据

```python
# 列出所有数据文件
data_files = manager.list_data()

for dataset_name, files in data_files.items():
    print(f"{dataset_name}:")
    for file in files:
        print(f"  - {file}")
```

## 数据格式规范

### JSONL格式（训练数据）

每行一个JSON对象：

```json
{
  "id": "train_001",
  "spatial_relation": "within",
  "entities": [
    {
      "id": "e1",
      "name": "故宫",
      "type": "POI",
      "geometry": {
        "type": "Point",
        "coordinates": [116.397, 39.918]
      }
    },
    {
      "id": "e2",
      "name": "北京市",
      "type": "City",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[116.0, 39.5], [117.0, 39.5], [117.0, 40.5], [116.0, 40.5], [116.0, 39.5]]]
      }
    }
  ],
  "question": "故宫位于北京市内吗？",
  "answer": "是的，故宫位于北京市内。",
  "reasoning": "故宫的地理坐标在北京市的行政边界范围内。"
}
```

### JSON格式（实体数据库/基准测试）

```json
{
  "entities": [
    {
      "id": "beijing",
      "name": "北京市",
      "type": "City",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[116.0, 39.5], [117.0, 39.5], [117.0, 40.5], [116.0, 40.5], [116.0, 39.5]]]
      },
      "properties": {
        "population": 21540000,
        "area_sqkm": 16410
      }
    }
  ],
  "metadata": {
    "version": "1.0",
    "total_entities": 100
  }
}
```

## 测试

创建示例数据并测试：

```bash
# 1. 创建示例数据
python scripts/create_sample_data.py

# 2. 列出数据文件
python scripts/data_manager.py list

# 3. 验证数据
python scripts/data_manager.py verify --data_path data/geosr_chain/train.jsonl

# 4. 查看统计
python scripts/data_manager.py stats --data_path data/geosr_chain/train.jsonl

# 5. 格式转换
python scripts/data_manager.py convert \
    --input data/geosr_chain/entity_database.json \
    --output data/geosr_chain/entity_database.jsonl
```

## 高级功能

### 自定义验证规则

修改 `configs/data.yaml` 中的验证规则：

```yaml
validation:
  required_fields:
    - "id"
    - "spatial_relation"
    - "entities"
    - "question"          # 添加自定义必填字段
    - "answer"

  entity_required_fields:
    - "id"
    - "name"
    - "type"
    - "geometry"
    - "properties"        # 添加自定义字段

  spatial_relations:
    - "within"
    - "contains"
    - "custom_relation"   # 添加自定义关系
```

### 批量处理

```python
from pathlib import Path
from scripts.data_manager import DataManager

manager = DataManager()

# 批量验证
data_dir = Path("data/geosr_chain")
results = {}

for file in data_dir.glob("*.jsonl"):
    result = manager.verify_data(str(file), verbose=False)
    results[file.name] = result

# 汇总结果
for filename, result in results.items():
    print(f"{filename}: {'✓' if result['valid'] else '✗'} ({result['valid_count']}/{result['total']})")
```

### 数据质量报告

```python
# 生成详细的质量报告
stats = manager.show_statistics("data/train.jsonl")

quality_issues = stats['data_quality']
total_records = stats['total_records']

print("\n数据质量评分:")
score = 100
for issue, count in quality_issues.items():
    if count > 0:
        penalty = (count / total_records) * 100
        score -= penalty
        print(f"  {issue}: {count} (-{penalty:.2f}%)")

print(f"\n总体评分: {score:.2f}/100")
```

## 故障排除

### 问题1: ModuleNotFoundError: No module named 'yaml'

解决方案：
```bash
pip install pyyaml
```

### 问题2: 可视化图表不显示

解决方案：
```bash
pip install matplotlib
```

### 问题3: 文件编码错误

确保数据文件使用UTF-8编码：
```bash
# 转换文件编码
iconv -f GBK -t UTF-8 input.txt > output.jsonl
```

## 最佳实践

1. **定期验证数据**：在数据更新后运行验证
2. **保存统计报告**：定期生成并保存统计报告用于追踪数据变化
3. **使用版本控制**：对数据文件使用版本控制
4. **备份数据**：在进行批量操作前备份原始数据
5. **文档化数据格式**：为自定义数据格式创建文档

## 联系与支持

如有问题或建议，请联系项目维护者。
