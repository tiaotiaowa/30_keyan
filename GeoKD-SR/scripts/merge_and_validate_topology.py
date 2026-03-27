#!/usr/bin/env python3
"""
合并和验证拓扑数据

功能：
1. 合并3个Agent生成的数据
2. 验证数据质量
3. 与现有数据整合
4. 生成最终统计报告
"""

import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent

# 文件路径
AGENT_OUTPUTS = [
    BASE_DIR / "data" / "geosr_chain" / "supplement" / "agent1_output_v2.jsonl",
    BASE_DIR / "data" / "geosr_chain" / "supplement" / "agent2_output_v2.jsonl",
    BASE_DIR / "data" / "geosr_chain" / "supplement" / "agent3_output_v2.jsonl",
]

EXISTING_DATA = BASE_DIR / "data" / "geosr_chain" / "balanced_topology_downsampled.jsonl"
FINAL_OUTPUT = BASE_DIR / "data" / "geosr_chain" / "balanced_topology_final.jsonl"
REPORT_OUTPUT = BASE_DIR / "data" / "geosr_chain" / "generation_report.json"


def load_jsonl(file_path: Path) -> list:
    """加载JSONL文件"""
    records = []
    if file_path.exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return records


def validate_record(record: dict) -> dict:
    """验证单条记录，返回验证结果"""
    issues = []

    # 检查必需字段
    required_fields = ['id', 'question', 'answer', 'reasoning_chain', 'entities',
                       'topology_subtype', 'difficulty']
    for field in required_fields:
        if field not in record:
            issues.append(f"缺少字段: {field}")

    # 检查question长度
    question = record.get('question', '')
    difficulty = record.get('difficulty', 'medium')
    min_lengths = {'easy': 30, 'medium': 50, 'hard': 80}
    min_len = min_lengths.get(difficulty, 50)
    if len(question) < min_len:
        issues.append(f"Question太短: {len(question)}字符 (需要≥{min_len})")

    # 检查reasoning_chain
    chain = record.get('reasoning_chain', [])
    if len(chain) < 5:
        issues.append(f"Reasoning chain不完整: {len(chain)}步 (需要5步)")

    # 检查entities
    entities = record.get('entities', [])
    if len(entities) < 2:
        issues.append(f"实体数量不足: {len(entities)}个 (需要≥2个)")

    # 检查坐标
    for e in entities:
        if 'coords' not in e:
            issues.append(f"实体缺少坐标: {e.get('name', 'unknown')}")

    return {
        'valid': len(issues) == 0,
        'issues': issues
    }


def merge_and_validate():
    """合并和验证数据"""
    print("=" * 60)
    print("拓扑数据合并和验证")
    print("=" * 60)

    # 1. 加载所有生成的数据
    all_generated = []
    for agent_file in AGENT_OUTPUTS:
        if agent_file.exists():
            records = load_jsonl(agent_file)
            all_generated.extend(records)
            print(f"加载 {agent_file.name}: {len(records)} 条")

    print(f"\n总计生成数据: {len(all_generated)} 条")

    # 2. 验证数据
    print("\n验证数据质量...")
    valid_records = []
    invalid_records = []

    for record in all_generated:
        result = validate_record(record)
        if result['valid']:
            valid_records.append(record)
        else:
            invalid_records.append({
                'record': record,
                'issues': result['issues']
            })

    print(f"  有效数据: {len(valid_records)} 条")
    print(f"  无效数据: {len(invalid_records)} 条")

    # 3. 统计子类型分布
    subtype_counts = defaultdict(int)
    difficulty_counts = defaultdict(int)

    for record in valid_records:
        subtype_counts[record.get('topology_subtype', 'unknown')] += 1
        difficulty_counts[record.get('difficulty', 'unknown')] += 1

    print("\n生成数据分布:")
    print("  子类型:")
    for subtype, count in sorted(subtype_counts.items()):
        print(f"    {subtype}: {count}")
    print("  难度:")
    for diff, count in sorted(difficulty_counts.items()):
        print(f"    {diff}: {count}")

    # 4. 加载现有数据
    existing_records = []
    if EXISTING_DATA.exists():
        existing_records = load_jsonl(EXISTING_DATA)
        print(f"\n现有数据: {len(existing_records)} 条")

        # 统计现有分布
        existing_subtype = defaultdict(int)
        for r in existing_records:
            existing_subtype[r.get('topology_subtype', 'unknown')] += 1
        print("  现有子类型分布:")
        for subtype, count in sorted(existing_subtype.items()):
            print(f"    {subtype}: {count}")

    # 5. 合并数据
    print("\n合并数据...")
    final_records = existing_records + valid_records

    # 去重（按ID）
    seen_ids = set()
    unique_records = []
    for record in final_records:
        record_id = record.get('id', '')
        if record_id and record_id not in seen_ids:
            seen_ids.add(record_id)
            unique_records.append(record)

    print(f"  合并后总数: {len(unique_records)} 条 (去重后)")

    # 6. 统计最终分布
    final_subtype = defaultdict(int)
    final_difficulty = defaultdict(int)

    for record in unique_records:
        final_subtype[record.get('topology_subtype', 'unknown')] += 1
        final_difficulty[record.get('difficulty', 'unknown')] += 1

    print("\n最终数据分布:")
    print("  子类型:")
    for subtype in ['disjoint', 'within', 'contains', 'adjacent', 'overlap']:
        count = final_subtype.get(subtype, 0)
        status = "✓" if count >= 610 else "✗"
        print(f"    {subtype}: {count} {status}")

    # 7. 保存最终数据
    print(f"\n保存到: {FINAL_OUTPUT}")
    with open(FINAL_OUTPUT, 'w', encoding='utf-8') as f:
        for record in unique_records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    # 8. 生成报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "generated_total": len(all_generated),
            "valid_count": len(valid_records),
            "invalid_count": len(invalid_records),
            "existing_count": len(existing_records),
            "final_count": len(unique_records)
        },
        "subtype_distribution": dict(final_subtype),
        "difficulty_distribution": dict(final_difficulty),
        "invalid_samples": [
            {"id": r['record'].get('id'), "issues": r['issues']}
            for r in invalid_records[:10]
        ]
    }

    with open(REPORT_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n报告保存到: {REPORT_OUTPUT}")
    print("\n" + "=" * 60)
    print("合并和验证完成!")
    print("=" * 60)

    return len(valid_records)


if __name__ == "__main__":
    merge_and_validate()
