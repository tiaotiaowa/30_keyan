#!/usr/bin/env python3
"""
创建示例数据用于测试数据管理工具
"""

import json
from pathlib import Path

# 创建示例GeoSR-Chain训练数据（JSONL格式）
train_data = [
    {
        "id": "train_001",
        "spatial_relation": "within",
        "entities": [
            {
                "id": "e1",
                "name": "故宫",
                "type": "POI",
                "geometry": {"type": "Point", "coordinates": [116.397, 39.918]}
            },
            {
                "id": "e2",
                "name": "北京市",
                "type": "City",
                "geometry": {"type": "Polygon", "coordinates": [[[116.0, 39.5], [117.0, 39.5], [117.0, 40.5], [116.0, 40.5], [116.0, 39.5]]]}
            }
        ],
        "question": "故宫位于北京市内吗？",
        "answer": "是的，故宫位于北京市内。",
        "reasoning": "故宫的地理坐标在北京市的行政边界范围内。"
    },
    {
        "id": "train_002",
        "spatial_relation": "near",
        "entities": [
            {
                "id": "e1",
                "name": "天安门广场",
                "type": "POI",
                "geometry": {"type": "Point", "coordinates": [116.397, 39.905]}
            },
            {
                "id": "e2",
                "name": "王府井大街",
                "type": "Street",
                "geometry": {"type": "LineString", "coordinates": [[116.410, 39.910], [116.415, 39.915]]}
            }
        ],
        "question": "天安门广场靠近王府井大街吗？",
        "answer": "是的，天安门广场距离王府井大街很近。",
        "reasoning": "两地之间的直线距离小于1公里。"
    },
    {
        "id": "train_003",
        "spatial_relation": "north_of",
        "entities": [
            {
                "id": "e1",
                "name": "长城",
                "type": "Landmark",
                "geometry": {"type": "LineString", "coordinates": [[116.0, 40.5], [117.0, 41.0]]}
            },
            {
                "id": "e2",
                "name": "北京市中心",
                "type": "City",
                "geometry": {"type": "Point", "coordinates": [116.397, 39.918]}
            }
        ],
        "question": "长城位于北京市中心的北面吗？",
        "answer": "是的，长城位于北京市中心以北。",
        "reasoning": "长城的纬度高于北京市中心的纬度。"
    },
    {
        "id": "train_004",
        "spatial_relation": "contains",
        "entities": [
            {
                "id": "e1",
                "name": "北京市",
                "type": "City",
                "geometry": {"type": "Polygon", "coordinates": [[[116.0, 39.5], [117.0, 39.5], [117.0, 40.5], [116.0, 40.5], [116.0, 39.5]]]}
            },
            {
                "id": "e2",
                "name": "颐和园",
                "type": "POI",
                "geometry": {"type": "Point", "coordinates": [116.273, 40.002]}
            }
        ],
        "question": "北京市包含颐和园吗？",
        "answer": "是的，颐和园位于北京市境内。",
        "reasoning": "颐和园的地理坐标在北京市的行政边界范围内。"
    },
    {
        "id": "train_005",
        "spatial_relation": "intersects",
        "entities": [
            {
                "id": "e1",
                "name": "长安街",
                "type": "Street",
                "geometry": {"type": "LineString", "coordinates": [[116.350, 39.910], [116.450, 39.910]]}
            },
            {
                "id": "e2",
                "name": "中轴线",
                "type": "Line",
                "geometry": {"type": "LineString", "coordinates": [[116.397, 39.850], [116.397, 39.950]]}
            }
        ],
        "question": "长安街与中轴线相交吗？",
        "answer": "是的，长安街与中轴线在天安门广场处相交。",
        "reasoning": "两条街道的路径在天安门广场处交叉。"
    }
]

# 创建示例实体数据库（JSON格式）
entity_database = {
    "entities": [
        {
            "id": "beijing",
            "name": "北京市",
            "type": "City",
            "admin_level": 2,
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[116.0, 39.5], [117.0, 39.5], [117.0, 40.5], [116.0, 40.5], [116.0, 39.5]]]
            },
            "properties": {
                "population": 21540000,
                "area_sqkm": 16410,
                "province": "北京"
            }
        },
        {
            "id": "forbidden_city",
            "name": "故宫",
            "type": "POI",
            "category": "Historic Site",
            "geometry": {
                "type": "Point",
                "coordinates": [116.397, 39.918]
            },
            "properties": {
                "built_year": 1420,
                "area_hectares": 72,
                "visitors_per_year": 19000000
            }
        },
        {
            "id": "great_wall",
            "name": "长城",
            "type": "Landmark",
            "category": "Historic Site",
            "geometry": {
                "type": "LineString",
                "coordinates": [[116.0, 40.5], [117.0, 41.0]]
            },
            "properties": {
                "built_year": -221,
                "length_km": 21000,
                "unesco_year": 1987
            }
        },
        {
            "id": "tiananmen_square",
            "name": "天安门广场",
            "type": "POI",
            "category": "Plaza",
            "geometry": {
                "type": "Point",
                "coordinates": [116.397, 39.905]
            },
            "properties": {
                "area_hectares": 44,
                "capacity": 1000000
            }
        },
        {
            "id": "wangfujing_street",
            "name": "王府井大街",
            "type": "Street",
            "category": "Shopping Street",
            "geometry": {
                "type": "LineString",
                "coordinates": [[116.410, 39.910], [116.415, 39.915]]
            },
            "properties": {
                "length_km": 1.8,
                "shops": 200
            }
        }
    ],
    "metadata": {
        "version": "1.0",
        "created_at": "2026-03-01",
        "total_entities": 5,
        "entity_types": ["City", "POI", "Landmark", "Street"]
    }
}

# 创建示例基准测试数据（JSON格式）
benchmark_data = {
    "benchmark": "GeoSR-Bench v1.0",
    "description": "地理空间关系推理基准测试集",
    "questions": [
        {
            "id": "bench_001",
            "question": "故宫位于北京市内吗？",
            "type": "within",
            "entities": ["故宫", "北京市"],
            "answer": "yes",
            "difficulty": "easy"
        },
        {
            "id": "bench_002",
            "question": "长城和颐和园哪个更靠北？",
            "type": "north_of",
            "entities": ["长城", "颐和园"],
            "answer": "长城",
            "difficulty": "medium"
        },
        {
            "id": "bench_003",
            "question": "从天安门广场到王府井大街的距离是多少？",
            "type": "near",
            "entities": ["天安门广场", "王府井大街"],
            "answer": "约1.5公里",
            "difficulty": "medium"
        },
        {
            "id": "bench_004",
            "question": "北京市包含多少个世界文化遗产？",
            "type": "contains",
            "entities": ["北京市", "世界文化遗产"],
            "answer": "7",
            "difficulty": "hard"
        },
        {
            "id": "bench_005",
            "question": "长安街与中轴线在哪里相交？",
            "type": "intersects",
            "entities": ["长安街", "中轴线"],
            "answer": "天安门广场",
            "difficulty": "easy"
        }
    ],
    "metadata": {
        "total_questions": 5,
        "difficulty_distribution": {
            "easy": 2,
            "medium": 2,
            "hard": 1
        },
        "relation_types": ["within", "north_of", "near", "contains", "intersects"]
    }
}

def create_sample_data():
    """创建示例数据文件"""
    import sys
    import io

    # 设置标准输出为UTF-8编码
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    base_dir = Path("data")

    # 创建目录
    (base_dir / "geosr_chain").mkdir(parents=True, exist_ok=True)
    (base_dir / "geosr_bench").mkdir(parents=True, exist_ok=True)

    # 保存训练数据（JSONL格式）
    train_file = base_dir / "geosr_chain" / "train.jsonl"
    with open(train_file, 'w', encoding='utf-8') as f:
        for record in train_data:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    print(f"[OK] 创建训练数据: {train_file}")

    # 保存实体数据库（JSON格式）
    entity_file = base_dir / "geosr_chain" / "entity_database.json"
    with open(entity_file, 'w', encoding='utf-8') as f:
        json.dump(entity_database, f, ensure_ascii=False, indent=2)
    print(f"[OK] 创建实体数据库: {entity_file}")

    # 保存基准测试数据（JSON格式）
    benchmark_file = base_dir / "geosr_bench" / "benchmark.json"
    with open(benchmark_file, 'w', encoding='utf-8') as f:
        json.dump(benchmark_data, f, ensure_ascii=False, indent=2)
    print(f"[OK] 创建基准测试数据: {benchmark_file}")

    print("\n示例数据创建完成！")
    print("\n现在可以测试数据管理工具:")
    print("  python scripts/data_manager.py list")
    print("  python scripts/data_manager.py verify --data_path data/geosr_chain/train.jsonl")
    print("  python scripts/data_manager.py stats --data_path data/geosr_chain/train.jsonl")

if __name__ == '__main__':
    create_sample_data()
