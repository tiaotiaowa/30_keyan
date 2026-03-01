# GeoKD-SR 数据管理工具

完整的GeoKD-SR数据管理解决方案，提供数据验证、统计、格式转换等功能。

## 快速开始

### 1. 安装依赖

```bash
# 核心依赖
pip install pyyaml

# 可选依赖（用于可视化）
pip install matplotlib
```

### 2. 创建示例数据

```bash
python scripts/create_sample_data.py
```

### 3. 使用数据管理工具

```bash
# 列出所有数据文件
python scripts/data_manager.py list

# 验证数据
python scripts/data_manager.py verify --data_path data/geosr_chain/train.jsonl

# 查看统计信息
python scripts/data_manager.py stats --data_path data/geosr_chain/train.jsonl

# 格式转换
python scripts/data_manager.py convert \
    --input data/geosr_chain/entity_database.json \
    --output data/geosr_chain/entity_database.jsonl

# 清理缓存
python scripts/data_manager.py clean
```

## 功能特性

### 1. 数据验证

验证JSON和JSONL格式的数据文件，检查：
- 文件格式正确性
- 必填字段完整性
- 空间关系类型有效性
- 实体字段完整性
- 数据质量统计

### 2. 数据统计

生成详细的数据统计报告：
- 空间关系类型分布
- 实体类型分布
- 实体数量分布
- 数据质量指标
- 可视化图表（可选）

### 3. 格式转换

支持JSON和JSONL格式之间的相互转换：
- JSON → JSONL
- JSONL → JSON
- 批量处理支持

### 4. 数据浏览

快速列出项目中的所有数据文件，按数据集分组显示。

### 5. 缓存管理

清理临时缓存文件，释放磁盘空间。

## 文件结构

```
GeoKD-SR/
├── configs/
│   └── data.yaml                 # 数据管理配置
├── scripts/
│   ├── data_manager.py           # 数据管理工具主程序
│   └── create_sample_data.py     # 示例数据生成器
├── data/
│   ├── geosr_chain/
│   │   ├── train.jsonl          # 训练数据
│   │   └── entity_database.json # 实体数据库
│   └── geosr_bench/
│       └── benchmark.json       # 基准测试数据
└── outputs/
    └── statistics/              # 统计报告输出目录
```

## 配置说明

编辑 `configs/data.yaml` 来自定义数据管理行为：

```yaml
# 数据目录配置
data:
  base_dir: "data"
  geosr_chain: "data/geosr_chain"
  geosr_bench: "data/geosr_bench"

# 数据验证规则
validation:
  required_fields:
    - "id"
    - "spatial_relation"
    - "entities"

  entity_required_fields:
    - "id"
    - "name"
    - "type"
    - "geometry"

  spatial_relations:
    - "within"
    - "contains"
    - "intersects"
    # ... 更多关系类型

# 缓存配置
cache:
  cache_dir: ".cache/data_manager"
  max_size_mb: 1000

# 统计配置
statistics:
  output_dir: "outputs/statistics"
  visualize: true
  save_report: true
```

## 使用示例

### Python API

```python
from scripts.data_manager import DataManager

# 创建数据管理器
manager = DataManager()

# 验证数据
result = manager.verify_data("data/geosr_chain/train.jsonl")
print(f"验证结果: {result['valid']}")

# 生成统计
stats = manager.show_statistics(
    "data/geosr_chain/train.jsonl",
    output_file="my_stats.json"
)

# 格式转换
manager.convert_format(
    input_path="data.json",
    output_path="data.jsonl"
)

# 列出所有数据
data_files = manager.list_data()
for dataset, files in data_files.items():
    print(f"{dataset}: {len(files)} files")
```

### 批量验证

```bash
# 验证所有JSONL文件
for file in data/**/*.jsonl; do
    echo "验证: $file"
    python scripts/data_manager.py verify --data_path "$file"
done
```

### 批量转换

```bash
# 将所有JSON文件转换为JSONL
for file in data/**/*.json; do
    output="${file%.json}.jsonl"
    python scripts/data_manager.py convert --input "$file" --output "$output"
done
```

## 输出说明

### 验证输出

```
============================================================
数据验证结果
============================================================
文件路径: data/geosr_chain/train.jsonl
文件类型: .jsonl
状态: [OK] 通过

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

### 统计输出

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
```

## 数据格式规范

### JSONL格式（训练数据）

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
    }
  ],
  "question": "故宫位于北京市内吗？",
  "answer": "是的，故宫位于北京市内。",
  "reasoning": "故宫的地理坐标在北京市的行政边界范围内。"
}
```

### JSON格式（实体数据库）

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
  ]
}
```

## 命令行参数

```
usage: data_manager.py [-h] [--config CONFIG] [--data_path DATA_PATH]
                       [--input INPUT] [--output OUTPUT]
                       [--output_file OUTPUT_FILE] [--no-visualize]
                       [--quiet]
                       {list,verify,stats,convert,clean,download}

GeoKD-SR 数据管理工具

positional arguments:
  {list,verify,stats,convert,clean,download}
                        命令

optional arguments:
  -h, --help            显示帮助信息
  --config CONFIG       配置文件路径
  --data_path DATA_PATH
                        数据文件路径
  --input INPUT         输入文件路径（转换命令使用）
  --output OUTPUT       输出文件路径（转换命令使用）
  --output_file OUTPUT_FILE
                        统计报告输出文件
  --no-visualize        不生成可视化图表
  --quiet, -q           静默模式，减少输出
```

## 故障排除

### 编码问题（Windows）

如果遇到编码错误，确保数据文件使用UTF-8编码保存。

### matplotlib导入错误

如果不需要可视化功能，可以忽略此警告。如需可视化，请安装：

```bash
pip install matplotlib
```

### YAML文件不存在

首次运行时会使用默认配置，或手动创建 `configs/data.yaml` 文件。

## 扩展功能

### 自定义验证规则

编辑 `configs/data.yaml` 添加自定义验证规则：

```yaml
validation:
  required_fields:
    - "id"
    - "spatial_relation"
    - "entities"
    - "custom_field"  # 添加自定义字段

  spatial_relations:
    - "within"
    - "custom_relation"  # 添加自定义关系
```

### 集成到项目

```python
# 在其他脚本中使用数据管理器
from scripts.data_manager import DataManager

class MyDataProcessor:
    def __init__(self):
        self.data_manager = DataManager()

    def process_data(self, data_path):
        # 验证数据
        result = self.data_manager.verify_data(data_path)
        if not result['valid']:
            raise ValueError("数据验证失败")

        # 加载数据
        records = self.data_manager._load_data(data_path)

        # 处理数据...
        return processed_records
```

## 最佳实践

1. **定期验证数据**：在数据更新后运行验证
2. **保存统计报告**：定期生成并保存统计报告用于追踪数据变化
3. **使用版本控制**：对数据文件使用版本控制
4. **备份数据**：在进行批量操作前备份原始数据
5. **文档化数据格式**：为自定义数据格式创建文档

## 性能建议

- 对于大型数据文件（>100MB），使用 `--quiet` 模式减少输出
- 批量处理时考虑使用多进程
- 定期清理缓存以释放磁盘空间

## 贡献指南

欢迎提交问题和改进建议！

## 许可证

MIT License
