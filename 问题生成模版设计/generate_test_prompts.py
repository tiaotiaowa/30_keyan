#!/usr/bin/env python3
"""从 pairs_positive.jsonl 每种关系取一条数据，填入模板生成可直接使用的测试提示词"""

import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_FILE = r"D:\gis_data\output\pairs_positive.jsonl"
TEMPLATE_DIR = r"D:\gis_data\output\问题生成模版设计\prompts"
OUTPUT_DIR = r"D:\gis_data\output\问题生成模版设计\test_prompts"

# target_relation -> (模板文件名, 输出文件名)
RELATION_MAP = {
    "directional": ("directional_positive.md", "test_directional_positive.md"),
    "metric": ("metric_positive.md", "test_metric_positive.md"),
    "topological.contains": ("topo_contains_positive.md", "test_topo_contains_positive.md"),
    "topological.within": ("topo_within_positive.md", "test_topo_within_positive.md"),
    "topological.touches": ("topo_touches_positive.md", "test_topo_touches_positive.md"),
    "topological.crosses": ("topo_crosses_positive.md", "test_topo_crosses_positive.md"),
    "topological.disjoint": ("topo_disjoint_positive.md", "test_topo_disjoint_positive.md"),
    "composite.direction_distance": ("composite_dd_positive.md", "test_composite_dd_positive.md"),
    "composite.direction_topology": ("composite_dir_topo_positive.md", "test_composite_dir_topo_positive.md"),
    "composite.distance_topology": ("composite_dist_topo_positive.md", "test_composite_dist_topo_positive.md"),
    "composite.direction_distance_topology": ("composite_ddt_positive.md", "test_composite_ddt_positive.md"),
}


def load_one_per_relation(jsonl_path):
    """从JSONL中为每种target_relation取第一条记录"""
    records = {}
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            rel = data["target_relation"]
            if rel not in records:
                records[rel] = data
            if len(records) == len(RELATION_MAP):
                break
    return records


def fill_template(template_text, data):
    """将模板占位符替换为实际数据值"""
    ea = data["entity_a"]
    eb = data["entity_b"]
    facts = data["spatial_facts"]

    # 基础替换表
    replacements = {
        "{{entity_a_name}}": ea["name_zh"],
        "{{entity_a_centroid}}": json.dumps(ea["centroid"], ensure_ascii=False),
        "{{entity_a_type}}": ea["type"],
        "{{entity_b_name}}": eb["name_zh"],
        "{{entity_b_centroid}}": json.dumps(eb["centroid"], ensure_ascii=False),
        "{{entity_b_type}}": eb["type"],
        "{{difficulty}}": "easy",
    }

    # 方向类占位符
    if "direction_8" in facts:
        replacements["{{fact_direction_8}}"] = facts["direction_8"]
    if "azimuth_deg" in facts:
        replacements["{{fact_azimuth_deg}}"] = str(facts["azimuth_deg"])

    # 距离类占位符
    if "distance_km" in facts:
        replacements["{{fact_distance_km}}"] = str(facts["distance_km"])

    # 执行全局替换
    result = template_text
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)

    return result


def fix_input_spatial_facts(text, data):
    """
    修复【输入数据格式】段中的空间事实行。
    仅替换输入数据格式代码块中的"空间事实:"行，不动示例中的行。

    策略：找到"## 输入数据格式"之后的第一个"空间事实:"行并替换。
    """
    facts = data["spatial_facts"]
    rel = data["target_relation"]

    # 只有复合模板需要修复（拓扑模板的空间事实已正确硬编码，方向/距离模板已通过占位符替换）
    if not rel.startswith("composite."):
        return text

    facts_json = json.dumps(facts, ensure_ascii=False)

    # 找到"## 输入数据格式"段的位置
    input_section_marker = "## 输入数据格式"
    marker_pos = text.find(input_section_marker)
    if marker_pos == -1:
        return text

    # 在标记之后的文本中，找到第一个"空间事实:"行并替换
    after_marker = text[marker_pos:]
    pattern = r'(空间事实:\s*)\{[^}]+\}'

    match = re.search(pattern, after_marker)
    if match:
        # 替换这一处
        old_text = match.group(0)
        new_text = match.group(1) + facts_json
        # 在原文中定位并替换
        abs_start = marker_pos + match.start()
        abs_end = marker_pos + match.end()
        text = text[:abs_start] + new_text + text[abs_end:]

    return text


def fix_output_format_topo(text, data):
    """
    修复输出格式段中的硬编码拓扑值，使其与实际数据一致。
    仅对composite.dist_topo模板需要（其他复合模板的拓扑值已正确）。
    """
    facts = data["spatial_facts"]
    rel = data["target_relation"]

    if rel != "composite.distance_topology":
        return text

    # 将输出格式段中的 "within": false, "disjoint": true 替换为实际值
    # 实际数据的 spatial_facts: {"distance_km": 123, "within": true}
    # 构建拓扑部分字符串
    topo_parts = []
    for k, v in facts.items():
        if k == "distance_km":
            continue
        topo_parts.append(f'"{k}": {json.dumps(v)}')
    topo_str = ", ".join(topo_parts)

    # 替换输出格式段中的拓扑字段
    # 原文有: "within": false, "disjoint": true
    # 需要替换为: "within": true
    text = text.replace('"within": false, "disjoint": true', topo_str)

    return text


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("加载数据...")
    records = load_one_per_relation(DATA_FILE)
    print(f"  找到 {len(records)} 种关系类型")

    for rel, (template_file, output_file) in RELATION_MAP.items():
        if rel not in records:
            print(f"  WARNING: no data for {rel}")
            continue

        data = records[rel]
        template_path = os.path.join(TEMPLATE_DIR, template_file)
        output_path = os.path.join(OUTPUT_DIR, output_file)

        with open(template_path, 'r', encoding='utf-8') as f:
            template_text = f.read()

        # Step 1: 替换所有 {{...}} 占位符
        filled = fill_template(template_text, data)

        # Step 2: 修复输入数据段中的空间事实
        filled = fix_input_spatial_facts(filled, data)

        # Step 3: 修复输出格式段中的拓扑硬编码
        filled = fix_output_format_topo(filled, data)

        # 检查残留占位符
        remaining = set(re.findall(r'\{\{[a-zA-Z_]+\}\}', filled))
        if remaining:
            print(f"  WARNING: {output_file} has unresolved placeholders: {remaining}")
        else:
            ea_name = data["entity_a"]["name_zh"]
            eb_name = data["entity_b"]["name_zh"]
            print(f"  OK {output_file}: {ea_name} -> {eb_name}")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(filled)

    print(f"\nDone! Files saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
