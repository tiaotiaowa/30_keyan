# GeoKD-SR 数据审查实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 对prompts_config_full.json执行完整的6层验证审查，生成问题报告和修复建议

**Architecture:** 创建独立的数据审查脚本，复用现有validate_data.py基础设施，新增拓扑语义验证和详细报告生成功能

**Tech Stack:** Python 3.8+, JSON, dataclasses, collections.Counter

---

## Task 1: 创建数据审查脚本框架

**Files:**
- Create: `scripts/review_prompts_data.py`

**Step 1: 创建脚本基础结构**

```python
#!/usr/bin/env python3
"""
GeoKD-SR 数据审查脚本

对prompts_config_full.json执行完整6层验证审查:
- L1: 格式验证
- L2: 语义验证
- L3: 空间关系验证
- L4: 坐标验证
- L5: 推理链验证
- L6: 分布验证

作者: GeoKD-SR Team
日期: 2026-03-06
"""

import json
import sys
from pathlib import Path
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import math

# 添加项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ================================
# 常量定义
# ================================

REQUIRED_FIELDS = [
    "id", "spatial_relation_type", "question", "answer",
    "reasoning_chain", "entities", "spatial_tokens",
    "entity_to_token", "difficulty"
]

SPATIAL_RELATION_TYPES = ["directional", "topological", "metric", "composite"]
TOPOLOGY_SUBTYPES = ["within", "contains", "adjacent", "disjoint", "overlap"]
DIFFICULTY_LEVELS = ["easy", "medium", "hard"]

# 中国坐标范围
COORDINATE_BOUNDS = {
    "lon_min": 73.0,
    "lon_max": 135.0,
    "lat_min": 18.0,
    "lat_max": 54.0
}

# V2.0 目标分布
TARGET_DISTRIBUTION = {
    "relation": {
        "directional": 0.25,
        "topological": 0.275,
        "metric": 0.275,
        "composite": 0.20
    },
    "difficulty": {
        "easy": 0.30,
        "medium": 0.50,
        "hard": 0.20
    },
    "topology_subtype": {
        "within": 0.20,
        "contains": 0.20,
        "adjacent": 0.20,
        "disjoint": 0.20,
        "overlap": 0.20
    }
}

# 实验字段需求
EXPERIMENT_REQUIREMENTS = {
    "Exp1": ["question", "answer"],
    "Exp2": ["question", "answer"],
    "Exp3a": ["question", "answer", "spatial_relation_type"],
    "Exp3": ["question", "answer", "spatial_relation_type"],
    "Exp4": ["question", "answer", "reasoning_chain"],
    "Exp5": ["question", "answer"],
    "Exp6": ["question", "answer"],
    "Exp7": ["question", "answer", "entities", "spatial_tokens", "entity_to_token"],
    "Exp8": ["question", "answer", "spatial_relation_type", "difficulty"],
    "Exp9": REQUIRED_FIELDS
}

# 推理链步骤名称
REASONING_CHAIN_STEPS = [
    "entity_identification",
    "spatial_relation_extraction",
    "coordinate_retrieval",
    "spatial_calculation",
    "answer_generation"
]

# 省份-城市映射(用于拓扑语义验证)
PROVINCE_CITY_MAP = {
    "北京市": ["北京"],
    "天津市": ["天津"],
    "河北省": ["石家庄", "唐山", "秦皇岛", "邯郸", "邢台", "保定", "张家口", "承德", "沧州", "廊坊", "衡水"],
    "山西省": ["太原", "大同", "阳泉", "长治", "晋城", "朔州", "晋中", "运城", "忻州", "临汾", "吕梁"],
    "内蒙古自治区": ["呼和浩特", "包头", "乌海", "赤峰", "通辽", "鄂尔多斯", "呼伦贝尔", "巴彦淖尔", "乌兰察布"],
    "辽宁省": ["沈阳", "大连", "鞍山", "抚顺", "本溪", "丹东", "锦州", "营口", "阜新", "辽阳", "盘锦", "铁岭", "朝阳", "葫芦岛"],
    "吉林省": ["长春", "吉林", "四平", "辽源", "通化", "白山", "松原", "白城", "延吉"],
    "黑龙江省": ["哈尔滨", "齐齐哈尔", "鸡西", "鹤岗", "双鸭山", "大庆", "伊春", "佳木斯", "七台河", "牡丹江", "黑河", "绥化"],
    "上海市": ["上海"],
    "江苏省": ["南京", "无锡", "徐州", "常州", "苏州", "南通", "连云港", "淮安", "盐城", "扬州", "镇江", "泰州", "宿迁"],
    "浙江省": ["杭州", "宁波", "温州", "嘉兴", "湖州", "绍兴", "金华", "衢州", "舟山", "台州", "丽水"],
    "安徽省": ["合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆", "黄山", "滁州", "阜阳", "宿州", "六安", "亳州", "池州", "宣城"],
    "福建省": ["福州", "厦门", "莆田", "三明", "泉州", "漳州", "南平", "龙岩", "宁德"],
    "江西省": ["南昌", "景德镇", "萍乡", "九江", "新余", "鹰潭", "赣州", "吉安", "宜春", "抚州", "上饶"],
    "山东省": ["济南", "青岛", "淄博", "枣庄", "东营", "烟台", "潍坊", "济宁", "泰安", "威海", "日照", "临沂", "德州", "聊城", "滨州", "菏泽"],
    "河南省": ["郑州", "开封", "洛阳", "平顶山", "安阳", "鹤壁", "新乡", "焦作", "濮阳", "许昌", "漯河", "三门峡", "南阳", "商丘", "信阳", "周口", "驻马店"],
    "湖北省": ["武汉", "黄石", "十堰", "宜昌", "襄阳", "鄂州", "荆门", "孝感", "荆州", "黄冈", "咸宁", "随州", "恩施"],
    "湖南省": ["长沙", "株洲", "湘潭", "衡阳", "邵阳", "岳阳", "常德", "张家界", "益阳", "郴州", "永州", "怀化", "娄底", "湘西"],
    "广东省": ["广州", "韶关", "深圳", "珠海", "汕头", "佛山", "江门", "湛江", "茂名", "肇庆", "惠州", "梅州", "汕尾", "河源", "阳江", "清远", "东莞", "中山", "潮州", "揭阳", "云浮"],
    "广西壮族自治区": ["南宁", "柳州", "桂林", "梧州", "北海", "防城港", "钦州", "贵港", "玉林", "百色", "贺州", "河池", "来宾", "崇左"],
    "海南省": ["海口", "三亚", "三沙", "儋州"],
    "重庆市": ["重庆"],
    "四川省": ["成都", "自贡", "攀枝花", "泸州", "德阳", "绵阳", "广元", "遂宁", "内江", "乐山", "南充", "眉山", "宜宾", "广安", "达州", "雅安", "巴中", "资阳", "阿坝", "甘孜", "凉山"],
    "贵州省": ["贵阳", "六盘水", "遵义", "安顺", "毕节", "铜仁", "黔西南", "黔东南", "黔南"],
    "云南省": ["昆明", "曲靖", "玉溪", "保山", "昭通", "丽江", "普洱", "临沧", "楚雄", "红河", "文山", "西双版纳", "大理", "德宏", "怒江", "迪庆"],
    "西藏自治区": ["拉萨", "日喀则", "昌都", "林芝", "山南", "那曲", "阿里"],
    "陕西省": ["西安", "铜川", "宝鸡", "咸阳", "渭南", "延安", "汉中", "榆林", "安康", "商洛"],
    "甘肃省": ["兰州", "嘉峪关", "金昌", "白银", "天水", "武威", "张掖", "平凉", "酒泉", "庆阳", "定西", "陇南", "临夏", "甘南"],
    "青海省": ["西宁", "海东", "海北", "黄南", "海南", "果洛", "玉树", "海西"],
    "宁夏回族自治区": ["银川", "石嘴山", "吴忠", "固原", "中卫"],
    "新疆维吾尔自治区": ["乌鲁木齐", "克拉玛依", "吐鲁番", "哈密", "昌吉", "博尔塔拉", "巴音郭楞", "阿克苏", "克孜勒苏", "喀什", "和田", "伊犁", "塔城", "阿勒泰"]
}


@dataclass
class ValidationResult:
    """验证结果数据类"""
    passed: int = 0
    failed: int = 0
    errors: List[Dict] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.passed + self.failed

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0


@dataclass
class ReviewReport:
    """审查报告数据类"""
    timestamp: str
    total_samples: int
    split_distribution: Dict[str, int]
    validation_results: Dict[str, ValidationResult]
    distribution_analysis: Dict[str, Dict]
    critical_issues: List[Dict]
    experiment_compatibility: Dict[str, int]
    recommendations: List[str]


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="GeoKD-SR 数据审查")
    parser.add_argument("--input", "-i", required=True, help="输入JSON文件路径")
    parser.add_argument("--output", "-o", default=None, help="输出报告路径")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")

    args = parser.parse_args()

    print(f"开始审查: {args.input}")
    # TODO: 实现审查逻辑


if __name__ == "__main__":
    main()
```

**Step 2: 验证脚本可运行**

Run: `python scripts/review_prompts_data.py --help`
Expected: 显示帮助信息

**Step 3: 提交基础框架**

```bash
git add scripts/review_prompts_data.py
git commit -m "feat: add data review script framework"
```

---

## Task 2: 实现L1-L2格式验证

**Files:**
- Modify: `scripts/review_prompts_data.py:150-250`

**Step 1: 添加格式验证函数**

```python
def validate_format(data: Dict) -> ValidationResult:
    """
    L1-L2 格式验证

    检查:
    - 必需字段存在性
    - 字段类型正确性
    - 枚举值有效性
    """
    result = ValidationResult()

    # L1: 必需字段检查
    for field in REQUIRED_FIELDS:
        if field not in data:
            result.failed += 1
            result.errors.append({
                "type": "missing_field",
                "field": field,
                "id": data.get("id", "unknown")
            })
        else:
            result.passed += 1

    # L2: 类型检查
    if not isinstance(data.get("question", ""), str):
        result.failed += 1
        result.errors.append({
            "type": "invalid_type",
            "field": "question",
            "expected": "str",
            "id": data.get("id", "unknown")
        })

    if not isinstance(data.get("answer", ""), str):
        result.failed += 1
        result.errors.append({
            "type": "invalid_type",
            "field": "answer",
            "expected": "str",
            "id": data.get("id", "unknown")
        })

    # L2: 枚举值检查
    relation_type = data.get("spatial_relation_type")
    if relation_type and relation_type not in SPATIAL_RELATION_TYPES:
        result.failed += 1
        result.errors.append({
            "type": "invalid_enum",
            "field": "spatial_relation_type",
            "value": relation_type,
            "valid_values": SPATIAL_RELATION_TYPES,
            "id": data.get("id", "unknown")
        })

    difficulty = data.get("difficulty")
    if difficulty and difficulty not in DIFFICULTY_LEVELS:
        result.failed += 1
        result.errors.append({
            "type": "invalid_enum",
            "field": "difficulty",
            "value": difficulty,
            "valid_values": DIFFICULTY_LEVELS,
            "id": data.get("id", "unknown")
        })

    # L2: 拓扑子类型检查
    if relation_type == "topological":
        topology_subtype = data.get("topology_subtype")
        if not topology_subtype:
            result.failed += 1
            result.errors.append({
                "type": "missing_topology_subtype",
                "id": data.get("id", "unknown")
            })
        elif topology_subtype not in TOPOLOGY_SUBTYPES:
            result.failed += 1
            result.errors.append({
                "type": "invalid_enum",
                "field": "topology_subtype",
                "value": topology_subtype,
                "valid_values": TOPOLOGY_SUBTYPES,
                "id": data.get("id", "unknown")
            })

    return result
```

**Step 2: 添加批量验证函数**

```python
def batch_validate_format(prompts: List[Dict]) -> ValidationResult:
    """批量格式验证"""
    total_result = ValidationResult()

    for prompt in prompts:
        result = validate_format(prompt)
        total_result.passed += result.passed
        total_result.failed += result.failed
        total_result.errors.extend(result.errors[:10])  # 只保留前10个错误样本

    return total_result
```

**Step 3: 运行测试验证**

Run: `python -c "from scripts.review_prompts_data import validate_format; print('OK')"`
Expected: `OK`

**Step 4: 提交格式验证**

```bash
git add scripts/review_prompts_data.py
git commit -m "feat: add L1-L2 format validation"
```

---

## Task 3: 实现L4坐标范围验证

**Files:**
- Modify: `scripts/review_prompts_data.py:250-350`

**Step 1: 添加坐标验证函数**

```python
def validate_coordinates(data: Dict) -> ValidationResult:
    """
    L4 坐标范围验证

    检查:
    - 经度在73-135°E范围内
    - 纬度在18-54°N范围内
    """
    result = ValidationResult()

    # 检查entity1坐标
    entity1 = data.get("entity1", {})
    coords1 = entity1.get("coords", [])

    if len(coords1) >= 2:
        lon1, lat1 = coords1[0], coords1[1]
        if not (COORDINATE_BOUNDS["lon_min"] <= lon1 <= COORDINATE_BOUNDS["lon_max"]):
            result.failed += 1
            result.errors.append({
                "type": "coordinate_out_of_bounds",
                "entity": entity1.get("name"),
                "field": "longitude",
                "value": lon1,
                "valid_range": [COORDINATE_BOUNDS["lon_min"], COORDINATE_BOUNDS["lon_max"]],
                "id": data.get("id", "unknown")
            })
        if not (COORDINATE_BOUNDS["lat_min"] <= lat1 <= COORDINATE_BOUNDS["lat_max"]):
            result.failed += 1
            result.errors.append({
                "type": "coordinate_out_of_bounds",
                "entity": entity1.get("name"),
                "field": "latitude",
                "value": lat1,
                "valid_range": [COORDINATE_BOUNDS["lat_min"], COORDINATE_BOUNDS["lat_max"]],
                "id": data.get("id", "unknown")
            })
    else:
        result.failed += 1
        result.errors.append({
            "type": "missing_coordinates",
            "entity": entity1.get("name"),
            "id": data.get("id", "unknown")
        })

    # 检查entity2坐标
    entity2 = data.get("entity2", {})
    coords2 = entity2.get("coords", [])

    if len(coords2) >= 2:
        lon2, lat2 = coords2[0], coords2[1]
        if not (COORDINATE_BOUNDS["lon_min"] <= lon2 <= COORDINATE_BOUNDS["lon_max"]):
            result.failed += 1
            result.errors.append({
                "type": "coordinate_out_of_bounds",
                "entity": entity2.get("name"),
                "field": "longitude",
                "value": lon2,
                "valid_range": [COORDINATE_BOUNDS["lon_min"], COORDINATE_BOUNDS["lon_max"]],
                "id": data.get("id", "unknown")
            })
        if not (COORDINATE_BOUNDS["lat_min"] <= lat2 <= COORDINATE_BOUNDS["lat_max"]):
            result.failed += 1
            result.errors.append({
                "type": "coordinate_out_of_bounds",
                "entity": entity2.get("name"),
                "field": "latitude",
                "value": lat2,
                "valid_range": [COORDINATE_BOUNDS["lat_min"], COORDINATE_BOUNDS["lat_max"]],
                "id": data.get("id", "unknown")
            })
    else:
        result.failed += 1
        result.errors.append({
            "type": "missing_coordinates",
            "entity": entity2.get("name"),
            "id": data.get("id", "unknown")
        })

    if result.failed == 0:
        result.passed = 1

    return result


def batch_validate_coordinates(prompts: List[Dict]) -> ValidationResult:
    """批量坐标验证"""
    total_result = ValidationResult()
    out_of_bounds_entities = set()

    for prompt in prompts:
        result = validate_coordinates(prompt)
        total_result.passed += result.passed
        total_result.failed += result.failed

        for error in result.errors:
            if error["type"] == "coordinate_out_of_bounds":
                out_of_bounds_entities.add(error["entity"])

    # 添加汇总信息
    if out_of_bounds_entities:
        total_result.errors.append({
            "type": "summary",
            "out_of_bounds_entities": list(out_of_bounds_entities),
            "count": len(out_of_bounds_entities)
        })

    return total_result
```

**Step 2: 运行测试**

Run: `python -c "from scripts.review_prompts_data import validate_coordinates, COORDINATE_BOUNDS; print(f'Range: {COORDINATE_BOUNDS}')"`
Expected: 显示坐标范围

**Step 3: 提交坐标验证**

```bash
git add scripts/review_prompts_data.py
git commit -m "feat: add L4 coordinate range validation"
```

---

## Task 4: 实现拓扑语义验证

**Files:**
- Modify: `scripts/review_prompts_data.py:350-450`

**Step 1: 添加拓扑语义验证函数**

```python
def validate_topology_semantics(data: Dict) -> ValidationResult:
    """
    拓扑关系语义正确性验证

    检查:
    - 省份-城市包含关系是否地理正确
    - topology_subtype是否与实际关系一致
    """
    result = ValidationResult()

    if data.get("spatial_relation_type") != "topological":
        result.passed = 1
        return result

    entity1 = data.get("entity1", {})
    entity2 = data.get("entity2", {})
    topology_subtype = data.get("topology_subtype")

    name1 = entity1.get("name", "")
    name2 = entity2.get("name", "")
    type1 = entity1.get("type", "")
    type2 = entity2.get("type", "")

    # 检查省份-城市包含关系
    if type1 == "province" and type2 == "city":
        # 省份包含城市
        if topology_subtype in ["contains", "within"]:
            cities_in_province = PROVINCE_CITY_MAP.get(name1, [])
            if name2 not in cities_in_province:
                result.failed += 1
                result.errors.append({
                    "type": "invalid_province_city_relation",
                    "province": name1,
                    "city": name2,
                    "topology_subtype": topology_subtype,
                    "valid_cities": cities_in_province[:5],  # 只显示前5个
                    "id": data.get("id", "unknown")
                })

    elif type1 == "city" and type2 == "province":
        # 城市在省份内
        if topology_subtype in ["contains", "within"]:
            cities_in_province = PROVINCE_CITY_MAP.get(name2, [])
            if name1 not in cities_in_province:
                result.failed += 1
                result.errors.append({
                    "type": "invalid_city_province_relation",
                    "city": name1,
                    "province": name2,
                    "topology_subtype": topology_subtype,
                    "valid_cities": cities_in_province[:5],
                    "id": data.get("id", "unknown")
                })

    if result.failed == 0:
        result.passed = 1

    return result


def batch_validate_topology_semantics(prompts: List[Dict]) -> ValidationResult:
    """批量拓扑语义验证"""
    total_result = ValidationResult()
    invalid_pairs = []

    for prompt in prompts:
        if prompt.get("spatial_relation_type") == "topological":
            result = validate_topology_semantics(prompt)
            total_result.passed += result.passed
            total_result.failed += result.failed

            for error in result.errors:
                if error["type"] in ["invalid_province_city_relation", "invalid_city_province_relation"]:
                    pair = (error.get("province"), error.get("city"))
                    if pair not in invalid_pairs:
                        invalid_pairs.append(pair)
                        total_result.errors.append(error)

    return total_result
```

**Step 2: 运行测试**

Run: `python -c "from scripts.review_prompts_data import validate_topology_semantics; print('OK')"`
Expected: `OK`

**Step 3: 提交拓扑语义验证**

```bash
git add scripts/review_prompts_data.py
git commit -m "feat: add topology semantics validation"
```

---

## Task 5: 实现L6分布验证

**Files:**
- Modify: `scripts/review_prompts_data.py:450-550`

**Step 1: 添加分布验证函数**

```python
def validate_distribution(prompts: List[Dict]) -> Dict[str, Dict]:
    """
    L6 分布验证

    检查:
    - 空间关系类型分布
    - 难度分布
    - 拓扑子类型分布
    """
    results = {}

    # 1. 空间关系类型分布
    relation_counts = Counter(p.get("spatial_relation_type") for p in prompts)
    total = len(prompts)

    relation_analysis = {}
    for rel_type, target_ratio in TARGET_DISTRIBUTION["relation"].items():
        actual_count = relation_counts.get(rel_type, 0)
        actual_ratio = actual_count / total if total > 0 else 0
        deviation = abs(actual_ratio - target_ratio)

        relation_analysis[rel_type] = {
            "count": actual_count,
            "actual_ratio": actual_ratio,
            "target_ratio": target_ratio,
            "deviation": deviation,
            "passed": deviation < 0.05
        }

    results["relation_distribution"] = {
        "passed": all(a["passed"] for a in relation_analysis.values()),
        "details": relation_analysis
    }

    # 2. 难度分布
    difficulty_counts = Counter(p.get("difficulty") for p in prompts)

    difficulty_analysis = {}
    for diff, target_ratio in TARGET_DISTRIBUTION["difficulty"].items():
        actual_count = difficulty_counts.get(diff, 0)
        actual_ratio = actual_count / total if total > 0 else 0
        deviation = abs(actual_ratio - target_ratio)

        difficulty_analysis[diff] = {
            "count": actual_count,
            "actual_ratio": actual_ratio,
            "target_ratio": target_ratio,
            "deviation": deviation,
            "passed": deviation < 0.05
        }

    results["difficulty_distribution"] = {
        "passed": all(a["passed"] for a in difficulty_analysis.values()),
        "details": difficulty_analysis
    }

    # 3. 拓扑子类型分布(仅topological类型)
    topological_prompts = [p for p in prompts if p.get("spatial_relation_type") == "topological"]
    if topological_prompts:
        subtype_counts = Counter(p.get("topology_subtype") for p in topological_prompts)
        topo_total = len(topological_prompts)

        subtype_analysis = {}
        for subtype, target_ratio in TARGET_DISTRIBUTION["topology_subtype"].items():
            actual_count = subtype_counts.get(subtype, 0)
            actual_ratio = actual_count / topo_total if topo_total > 0 else 0
            deviation = abs(actual_ratio - target_ratio)

            subtype_analysis[subtype] = {
                "count": actual_count,
                "actual_ratio": actual_ratio,
                "target_ratio": target_ratio,
                "deviation": deviation,
                "passed": deviation < 0.05
            }

        results["topology_subtype_distribution"] = {
            "passed": all(a["passed"] for a in subtype_analysis.values()),
            "details": subtype_analysis
        }

    return results
```

**Step 2: 运行测试**

Run: `python -c "from scripts.review_prompts_data import validate_distribution; print('OK')"`
Expected: `OK`

**Step 3: 提交分布验证**

```bash
git add scripts/review_prompts_data.py
git commit -m "feat: add L6 distribution validation"
```

---

## Task 6: 实现实验兼容性验证

**Files:**
- Modify: `scripts/review_prompts_data.py:550-620`

**Step 1: 添加实验兼容性验证函数**

```python
def validate_experiment_compatibility(prompts: List[Dict]) -> Dict[str, Dict]:
    """
    实验兼容性验证

    检查每个实验所需的字段是否完整
    """
    results = {}
    total = len(prompts)

    for exp_name, required_fields in EXPERIMENT_REQUIREMENTS.items():
        compatible_count = 0
        missing_field_counts = Counter()

        for prompt in prompts:
            is_compatible = True
            for field in required_fields:
                if field not in prompt or not prompt[field]:
                    is_compatible = False
                    missing_field_counts[field] += 1

            if is_compatible:
                compatible_count += 1

        compatibility_rate = compatible_count / total if total > 0 else 0

        results[exp_name] = {
            "compatible_count": compatible_count,
            "total": total,
            "compatibility_rate": compatibility_rate,
            "passed": compatibility_rate >= 0.90,  # 90%通过标准
            "missing_fields": dict(missing_field_counts)
        }

    return results
```

**Step 2: 运行测试**

Run: `python -c "from scripts.review_prompts_data import validate_experiment_compatibility; print('OK')"`
Expected: `OK`

**Step 3: 提交实验兼容性验证**

```bash
git add scripts/review_prompts_data.py
git commit -m "feat: add experiment compatibility validation"
```

---

## Task 7: 实现L5推理链结构验证

**Files:**
- Modify: `scripts/review_prompts_data.py:620-720`

**Step 1: 添加推理链验证函数**

```python
def validate_reasoning_chain(data: Dict) -> ValidationResult:
    """
    L5 推理链结构验证

    检查:
    - 5步结构完整性
    - 步骤名称正确性
    - action字段正确性
    """
    result = ValidationResult()

    reasoning_chain = data.get("reasoning_chain", [])

    # 检查步骤数量
    if len(reasoning_chain) != 5:
        result.failed += 1
        result.errors.append({
            "type": "invalid_chain_length",
            "expected": 5,
            "actual": len(reasoning_chain),
            "id": data.get("id", "unknown")
        })
        return result

    # 检查步骤名称
    expected_names = REASONING_CHAIN_STEPS
    actual_names = [step.get("name", "") for step in reasoning_chain]

    if actual_names != expected_names:
        result.failed += 1
        result.errors.append({
            "type": "invalid_step_names",
            "expected": expected_names,
            "actual": actual_names,
            "id": data.get("id", "unknown")
        })

    # 检查步骤编号
    expected_steps = [1, 2, 3, 4, 5]
    actual_steps = [step.get("step", 0) for step in reasoning_chain]

    if actual_steps != expected_steps:
        result.failed += 1
        result.errors.append({
            "type": "invalid_step_numbers",
            "expected": expected_steps,
            "actual": actual_steps,
            "id": data.get("id", "unknown")
        })

    if result.failed == 0:
        result.passed = 1

    return result


def batch_validate_reasoning_chain(prompts: List[Dict]) -> ValidationResult:
    """批量推理链验证"""
    total_result = ValidationResult()

    for prompt in prompts:
        result = validate_reasoning_chain(prompt)
        total_result.passed += result.passed
        total_result.failed += result.failed

        # 只保留前20个错误样本
        if result.errors and len(total_result.errors) < 20:
            total_result.errors.extend(result.errors)

    return total_result
```

**Step 2: 运行测试**

Run: `python -c "from scripts.review_prompts_data import validate_reasoning_chain; print('OK')"`
Expected: `OK`

**Step 3: 提交推理链验证**

```bash
git add scripts/review_prompts_data.py
git commit -m "feat: add L5 reasoning chain validation"
```

---

## Task 8: 实现完整审查流程和报告生成

**Files:**
- Modify: `scripts/review_prompts_data.py:720-900`

**Step 1: 添加主审查函数**

```python
def run_full_review(input_path: str, verbose: bool = False) -> ReviewReport:
    """
    执行完整数据审查
    """
    # 加载数据
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    prompts = data.get("prompts", [])
    metadata = data.get("metadata", {})

    print(f"加载数据: {len(prompts)} 条样本")
    print(f"版本: {metadata.get('version', 'unknown')}")
    print(f"创建时间: {metadata.get('created_at', 'unknown')}")
    print()

    # Split分布
    split_distribution = Counter(p.get("split") for p in prompts)
    print(f"Split分布: {dict(split_distribution)}")
    print()

    # 执行各项验证
    print("执行验证...")
    validation_results = {}

    # L1-L2 格式验证
    print("  - L1-L2 格式验证...")
    validation_results["format"] = batch_validate_format(prompts)

    # L4 坐标验证
    print("  - L4 坐标范围验证...")
    validation_results["coordinates"] = batch_validate_coordinates(prompts)

    # 拓扑语义验证
    print("  - 拓扑语义验证...")
    validation_results["topology_semantics"] = batch_validate_topology_semantics(prompts)

    # L5 推理链验证
    print("  - L5 推理链验证...")
    validation_results["reasoning_chain"] = batch_validate_reasoning_chain(prompts)

    # L6 分布验证
    print("  - L6 分布验证...")
    distribution_analysis = validate_distribution(prompts)

    # 实验兼容性验证
    print("  - 实验兼容性验证...")
    experiment_compatibility = validate_experiment_compatibility(prompts)

    # 收集关键问题
    critical_issues = []

    # 坐标越界问题
    coord_errors = validation_results["coordinates"].errors
    for error in coord_errors:
        if error.get("type") == "summary":
            critical_issues.append({
                "severity": "HIGH",
                "type": "coordinate_out_of_bounds",
                "description": f"发现 {error['count']} 个实体坐标越界",
                "entities": error["out_of_bounds_entities"][:10]
            })

    # 拓扑语义问题
    topo_errors = validation_results["topology_semantics"].errors
    if topo_errors:
        critical_issues.append({
            "severity": "HIGH",
            "type": "invalid_topology_semantics",
            "description": f"发现 {len(topo_errors)} 个拓扑关系语义错误",
            "examples": topo_errors[:5]
        })

    # 生成建议
    recommendations = []

    if validation_results["coordinates"].failed > 0:
        recommendations.append("修复坐标越界问题：检查实体数据库中的坐标数据")

    if validation_results["topology_semantics"].failed > 0:
        recommendations.append("修复拓扑语义问题：确保省份-城市映射正确")

    if not distribution_analysis.get("relation_distribution", {}).get("passed", True):
        recommendations.append("调整空间关系类型分布以符合目标")

    if not distribution_analysis.get("difficulty_distribution", {}).get("passed", True):
        recommendations.append("调整难度分布以符合目标")

    # 创建报告
    report = ReviewReport(
        timestamp=datetime.now().isoformat(),
        total_samples=len(prompts),
        split_distribution=dict(split_distribution),
        validation_results=validation_results,
        distribution_analysis=distribution_analysis,
        critical_issues=critical_issues,
        experiment_compatibility=experiment_compatibility,
        recommendations=recommendations
    )

    return report


def print_report(report: ReviewReport):
    """打印审查报告"""
    print("=" * 60)
    print("GeoKD-SR 数据审查报告")
    print("=" * 60)
    print(f"时间: {report.timestamp}")
    print(f"总样本数: {report.total_samples}")
    print(f"Split分布: {report.split_distribution}")
    print()

    # 验证结果
    print("-" * 40)
    print("验证结果:")
    print("-" * 40)

    for name, result in report.validation_results.items():
        status = "PASS" if result.failed == 0 else "FAIL"
        print(f"  {name}: {status} (passed={result.passed}, failed={result.failed})")

    # 分布分析
    print()
    print("-" * 40)
    print("分布分析:")
    print("-" * 40)

    for dist_name, dist_result in report.distribution_analysis.items():
        status = "PASS" if dist_result.get("passed", True) else "FAIL"
        print(f"  {dist_name}: {status}")

        if "details" in dist_result:
            for key, details in dist_result["details"].items():
                deviation = details.get("deviation", 0) * 100
                print(f"    {key}: {details['actual_ratio']*100:.1f}% (target: {details['target_ratio']*100:.1f}%, dev: {deviation:.2f}%)")

    # 实验兼容性
    print()
    print("-" * 40)
    print("实验兼容性:")
    print("-" * 40)

    for exp_name, exp_result in report.experiment_compatibility.items():
        status = "PASS" if exp_result["passed"] else "FAIL"
        rate = exp_result["compatibility_rate"] * 100
        print(f"  {exp_name}: {status} ({rate:.1f}%)")

    # 关键问题
    if report.critical_issues:
        print()
        print("-" * 40)
        print("关键问题:")
        print("-" * 40)

        for issue in report.critical_issues:
            print(f"  [{issue['severity']}] {issue['type']}")
            print(f"    {issue['description']}")

    # 建议
    if report.recommendations:
        print()
        print("-" * 40)
        print("修复建议:")
        print("-" * 40)

        for i, rec in enumerate(report.recommendations, 1):
            print(f"  {i}. {rec}")

    print()
    print("=" * 60)


def save_report(report: ReviewReport, output_path: str):
    """保存报告为JSON"""
    # 转换为可序列化字典
    report_dict = {
        "timestamp": report.timestamp,
        "total_samples": report.total_samples,
        "split_distribution": report.split_distribution,
        "validation_results": {
            name: {
                "passed": result.passed,
                "failed": result.failed,
                "pass_rate": result.pass_rate,
                "errors": result.errors[:20]  # 只保留前20个错误
            }
            for name, result in report.validation_results.items()
        },
        "distribution_analysis": report.distribution_analysis,
        "critical_issues": report.critical_issues,
        "experiment_compatibility": report.experiment_compatibility,
        "recommendations": report.recommendations
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report_dict, f, ensure_ascii=False, indent=2)

    print(f"报告已保存: {output_path}")
```

**Step 2: 更新main函数**

```python
def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="GeoKD-SR 数据审查")
    parser.add_argument("--input", "-i", required=True, help="输入JSON文件路径")
    parser.add_argument("--output", "-o", default=None, help="输出报告路径")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")

    args = parser.parse_args()

    # 执行审查
    report = run_full_review(args.input, args.verbose)

    # 打印报告
    print_report(report)

    # 保存报告
    if args.output:
        save_report(report, args.output)
    else:
        # 默认输出路径
        default_output = Path(args.input).parent / "review_report.json"
        save_report(report, str(default_output))


if __name__ == "__main__":
    main()
```

**Step 3: 运行完整审查**

Run: `cd D:/30_keyan/GeoKD-SR && python scripts/review_prompts_data.py -i data/prompts/prompts_config_full.json -o outputs/prompts_review_report.json`
Expected: 显示完整审查报告

**Step 4: 提交完整审查功能**

```bash
git add scripts/review_prompts_data.py
git commit -m "feat: add complete data review functionality"
```

---

## Task 9: 执行审查并生成报告

**Files:**
- Create: `outputs/prompts_review_report.json`

**Step 1: 确保输出目录存在**

Run: `powershell -Command "New-Item -ItemType Directory -Force -Path 'D:\30_keyan\GeoKD-SR\outputs'"`
Expected: 目录创建成功

**Step 2: 执行审查**

Run: `cd D:/30_keyan/GeoKD-SR && python scripts/review_prompts_data.py -i data/prompts/prompts_config_full.json -o outputs/prompts_review_report.json -v`
Expected: 生成完整审查报告

**Step 3: 检查报告文件**

Run: `python -c "import json; r=json.load(open('D:/30_keyan/GeoKD-SR/outputs/prompts_review_report.json','r',encoding='utf-8')); print(f'Critical issues: {len(r[\"critical_issues\"])}'); print(f'Recommendations: {len(r[\"recommendations\"])}')"`
Expected: 显示关键问题数量

**Step 4: 提交审查报告**

```bash
git add outputs/prompts_review_report.json
git commit -m "docs: add data review report"
```

---

## Task 10: 根据审查结果生成修复建议文档

**Files:**
- Create: `outputs/prompts_fix_recommendations.md`

**Step 1: 创建修复建议文档**

根据审查报告，创建详细的修复建议文档：

```markdown
# GeoKD-SR 数据修复建议

> **审查日期**: 2026-03-06
> **审查文件**: prompts_config_full.json

## 一、关键问题清单

### 1.1 坐标越界问题
**严重性**: HIGH
**影响范围**: 80条数据

**问题描述**:
部分实体坐标超出中国境内范围(73-135°E, 18-54°N)

**修复方案**:
1. 定位所有越界坐标
2. 从权威数据源获取正确坐标
3. 更新entity_database_expanded.json
4. 重新生成受影响的数据

### 1.2 拓扑语义错误
**严重性**: HIGH
**影响范围**: 待统计

**问题描述**:
省份-城市包含关系不正确，如：
- 陕西省-长沙标记为contains，但长沙实际在湖南省

**修复方案**:
1. 使用PROVINCE_CITY_MAP验证所有拓扑关系
2. 移除或修正错误关系
3. 确保topology_subtype与实际地理关系一致

## 二、修复优先级

| 优先级 | 问题 | 影响 | 工作量 |
|--------|------|------|--------|
| P0 | 坐标越界 | 数据有效性 | 2小时 |
| P0 | 拓扑语义 | 数据正确性 | 4小时 |
| P1 | 分布偏差 | 实验公平性 | 1小时 |

## 三、修复步骤

### Step 1: 修复坐标越界
```bash
# 运行坐标修复脚本
python scripts/fix_coordinates.py --input data/prompts/prompts_config_full.json
```

### Step 2: 修复拓扑语义
```bash
# 运行拓扑语义修复脚本
python scripts/fix_topology_semantics.py --input data/prompts/prompts_config_full.json
```

### Step 3: 重新验证
```bash
# 重新运行审查
python scripts/review_prompts_data.py -i data/prompts/prompts_config_full.json
```

## 四、验证通过标准

- [ ] 坐标越界: 0条
- [ ] 拓扑语义错误: 0条
- [ ] 分布偏差: <5%
- [ ] 实验兼容性: ≥90%
```

**Step 2: 提交修复建议文档**

```bash
git add outputs/prompts_fix_recommendations.md
git commit -m "docs: add data fix recommendations"
```

---

## 总结

### 预期交付物

| 文件 | 描述 |
|------|------|
| `scripts/review_prompts_data.py` | 数据审查脚本 |
| `outputs/prompts_review_report.json` | 审查报告(JSON) |
| `outputs/prompts_fix_recommendations.md` | 修复建议文档 |

### 验证检查清单

- [ ] 脚本可运行
- [ ] L1-L2格式验证通过
- [ ] L4坐标验证报告生成
- [ ] 拓扑语义验证报告生成
- [ ] L5推理链验证通过
- [ ] L6分布验证报告生成
- [ ] 实验兼容性报告生成
- [ ] 关键问题已列出
- [ ] 修复建议已生成

### 后续行动

1. 根据审查报告修复数据
2. 重新生成数据
3. 再次运行审查确认通过
4. 将审查报告纳入项目文档
