#!/usr/bin/env python3
"""
合并和验证最终数据
将3个agent生成的数据与现有数据集合并
"""

import json
from pathlib import Path
from collections import Counter
from datetime import datetime

# 路径配置
BASE_DIR = Path(__file__).parent.parent
SUPPLEMENT_DIR = BASE_DIR / "data" / "geosr_chain" / "supplement"
EXISTING_DATA = BASE_DIR / "data" / "geosr_chain" / "balanced_topology_downsampled.jsonl"
FINAL_OUTPUT = BASE_DIR / "data" / "geosr_chain" / "balanced_topology_final.jsonl"

# Agent输出文件
AGENT_OUTPUTS = [
    SUPPLEMENT_DIR / "agent1_output.jsonl",
    SUPPLEMENT_DIR / "agent2_output.jsonl",
    SUPPLEMENT_DIR / "agent3_output.jsonl"
]


def load_jsonl(filepath):
    """加载JSONL文件"""
    data = []
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data.append(json.loads(line.strip()))
                except:
                    pass
    return data


def save_jsonl(filepath, data):
    """保存JSONL文件"""
    with open(filepath, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')


def validate_data(data):
    """验证数据质量"""
    issues = []

    for i, item in enumerate(data):
        # 检查必需字段
        required_fields = ["id", "question", "answer", "reasoning_chain", "entities", "topology_subtype"]
        for field in required_fields:
            if field not in item:
                issues.append(f"第{i+1}条数据缺少字段: {field}")

        # 检查reasoning_chain
        chain = item.get("reasoning_chain", [])
        if len(chain) < 5:
            issues.append(f"第{i+1}条数据reasoning_chain不足5步: {len(chain)}步")

        # 检查entities
        entities = item.get("entities", [])
        if len(entities) < 2:
            issues.append(f"第{i+1}条数据entities不足2个")
        else:
            for e in entities:
                if "coords" not in e:
                    issues.append(f"第{i+1}条数据实体缺少coords")

    return issues


def merge_and_validate():
    """合并和验证数据"""
    print("=" * 60)
    print("Step 1: 加载现有数据")
    print("=" * 60)

    existing_data = load_jsonl(EXISTING_DATA)
    print(f"现有数据量: {len(existing_data)}")

    # 统计现有分布
    existing_by_subtype = Counter(d.get("topology_subtype", "unknown") for d in existing_data)
    print(f"现有子类型分布:")
    for subtype, count in sorted(existing_by_subtype.items()):
        print(f"  {subtype}: {count}")

    print("\n" + "=" * 60)
    print("Step 2: 加载Agent生成的数据")
    print("=" * 60)

    all_new_data = []
    for i, filepath in enumerate(AGENT_OUTPUTS, 1):
        if filepath.exists():
            agent_data = load_jsonl(filepath)
            print(f"Agent-{i}: {len(agent_data)} 条")
            all_new_data.extend(agent_data)
        else:
            print(f"Agent-{i}: 文件不存在 - {filepath}")

    print(f"\n总新增数据: {len(all_new_data)}")

    print("\n" + "=" * 60)
    print("Step 3: 验证数据质量")
    print("=" * 60)

    issues = validate_data(all_new_data)
    if issues:
        print(f"发现 {len(issues)} 个问题:")
        for issue in issues[:20]:  # 只显示前20个
            print(f"  - {issue}")
        if len(issues) > 20:
            print(f"  ... 还有 {len(issues) - 20} 个问题")
    else:
        print("数据验证通过!")

    print("\n" + "=" * 60)
    print("Step 4: 合并数据")
    print("=" * 60)

    # 筛选拓扑类型数据
    existing_topological = [d for d in existing_data if d.get("spatial_relation_type") == "topological"]
    print(f"现有拓扑类型数据: {len(existing_topological)}")

    # 合并
    final_data = existing_topological + all_new_data
    print(f"合并后总数: {len(final_data)}")

    # 统计最终分布
    final_by_subtype = Counter(d.get("topology_subtype", "unknown") for d in final_data)
    print(f"\n最终子类型分布:")
    for subtype, count in sorted(final_by_subtype.items()):
        target = 610
        status = "✓" if count >= target else "✗"
        print(f"  {subtype}: {count} (目标:{target}) {status}")

    print("\n" + "=" * 60)
    print("Step 5: 保存最终数据")
    print("=" * 60)

    save_jsonl(FINAL_OUTPUT, final_data)
    print(f"已保存到: {FINAL_OUTPUT}")

    # 生成报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "existing_count": len(existing_data),
        "existing_topological": len(existing_topological),
        "new_data_count": len(all_new_data),
        "final_count": len(final_data),
        "validation_issues": len(issues),
        "final_distribution": dict(final_by_subtype),
        "target_distribution": {"disjoint": 610, "within": 610, "contains": 610, "adjacent": 610, "overlap": 610}
    }

    report_file = SUPPLEMENT_DIR / "merge_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"报告已保存到: {report_file}")

    print("\n" + "=" * 60)
    print("合并和验证完成!")
    print("=" * 60)

    return report


if __name__ == "__main__":
    merge_and_validate()
