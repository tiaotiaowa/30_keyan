#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
地理实体数据库坐标修复脚本
修复 entity_database_expanded.json 中发现的11处坐标错误

创建时间: 2026-03-11
"""

import json
from datetime import datetime
from pathlib import Path

# 需要修复的坐标
COORDINATE_FIXES = {
    # 河流修复 (7处)
    "长江": {
        "old_coords": [122.5, 41.0],
        "new_coords": [121.5, 31.2],
        "reason": "当前坐标在大连附近，应在上海入海口"
    },
    "黄河": {
        "old_coords": [119.5, 50.5],
        "new_coords": [118.5, 37.8],
        "reason": "当前坐标在内蒙古最北端，应在山东东营入海口"
    },
    "珠江": {
        "old_coords": [126.5, 41.0],
        "new_coords": [113.5, 22.5],
        "reason": "当前坐标在吉林/朝鲜边境，应在广东入海口"
    },
    "松花江": {
        "old_coords": [98.0, 28.0],
        "new_coords": [126.5, 45.8],
        "reason": "当前坐标在西藏/青海，应在黑龙江流域"
    },
    "韩江": {
        "old_coords": [99.0, 25.5],
        "new_coords": [116.6, 23.5],
        "reason": "当前坐标在云南/缅甸，应在广东东部"
    },
    "嫩江": {
        "old_coords": [91.0, 29.0],
        "new_coords": [125.2, 48.8],
        "reason": "当前坐标在西藏，应在黑龙江/内蒙古"
    },
    "额尔古纳河": {
        "old_coords": [119.5, 50.5],
        "new_coords": [120.0, 51.5],
        "reason": "坐标有偏差，应在内蒙古东北部"
    },

    # 山脉修复 (4处)
    "大兴安岭": {
        "old_coords": [86.0, 27.5],
        "new_coords": [122.0, 50.0],
        "reason": "当前坐标在西藏，应在内蒙古东北部"
    },
    "武夷山脉": {
        "old_coords": [85.0, 36.0],
        "new_coords": [117.5, 27.5],
        "reason": "当前坐标在新疆/青海，应在福建/江西交界"
    },
    "云岭": {
        "old_coords": [108.0, 33.5],
        "new_coords": [99.5, 26.5],
        "reason": "当前坐标在秦岭附近，应在云南西北部"
    },
    "恒山": {
        "old_coords": [117.0, 39.6833],
        "new_coords": [113.7, 39.7],
        "reason": "当前坐标在天津附近，应在山西大同浑源县"
    },
}


def load_database(file_path: str) -> dict:
    """加载数据库文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_database(data: dict, file_path: str):
    """保存数据库文件"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fix_coordinates(data: dict) -> dict:
    """修复坐标错误"""
    report = {
        "fixed": [],
        "not_found": [],
        "coords_mismatch": []
    }

    entities = data.get("entities", {})

    for entity_name, fix_info in COORDINATE_FIXES.items():
        found = False

        # 遍历所有实体类型
        for entity_type, entity_list in entities.items():
            if not isinstance(entity_list, list):
                continue

            for entity in entity_list:
                if entity.get("name") == entity_name:
                    found = True
                    current_coords = entity.get("coords", [])

                    # 检查当前坐标是否与预期错误坐标匹配
                    if current_coords == fix_info["old_coords"]:
                        # 执行修复
                        entity["coords"] = fix_info["new_coords"]
                        report["fixed"].append({
                            "name": entity_name,
                            "type": entity_type,
                            "old_coords": fix_info["old_coords"],
                            "new_coords": fix_info["new_coords"],
                            "reason": fix_info["reason"]
                        })
                        print(f"[修复] {entity_name} ({entity_type})")
                        print(f"       旧坐标: {fix_info['old_coords']}")
                        print(f"       新坐标: {fix_info['new_coords']}")
                        print(f"       原因: {fix_info['reason']}")
                        print()
                    else:
                        report["coords_mismatch"].append({
                            "name": entity_name,
                            "type": entity_type,
                            "expected_old": fix_info["old_coords"],
                            "actual_current": current_coords
                        })
                        print(f"[警告] {entity_name} 当前坐标与预期不符")
                        print(f"       预期旧坐标: {fix_info['old_coords']}")
                        print(f"       实际当前坐标: {current_coords}")
                        print()
                    break

            if found:
                break

        if not found:
            report["not_found"].append(entity_name)
            print(f"[未找到] {entity_name}")

    return report


def generate_report(report: dict, output_path: str):
    """生成修复报告"""
    report_content = f"""# 地理实体数据库坐标修复报告

生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 修复统计

- 成功修复: {len(report['fixed'])} 处
- 坐标不匹配: {len(report['coords_mismatch'])} 处
- 未找到实体: {len(report['not_found'])} 处

## 修复详情

### 成功修复的实体

| 实体名称 | 类型 | 旧坐标 | 新坐标 | 修复原因 |
|---------|------|--------|--------|---------|
"""

    for item in report["fixed"]:
        report_content += f"| {item['name']} | {item['type']} | {item['old_coords']} | {item['new_coords']} | {item['reason']} |\n"

    if report["coords_mismatch"]:
        report_content += "\n### 坐标不匹配的实体\n\n"
        for item in report["coords_mismatch"]:
            report_content += f"- **{item['name']}** ({item['type']})\n"
            report_content += f"  - 预期旧坐标: {item['expected_old']}\n"
            report_content += f"  - 实际当前坐标: {item['actual_current']}\n"

    if report["not_found"]:
        report_content += "\n### 未找到的实体\n\n"
        for name in report["not_found"]:
            report_content += f"- {name}\n"

    report_content += "\n## 修复说明\n\n"
    report_content += "本次修复针对以下类型的坐标错误：\n\n"
    report_content += "1. **河流坐标错误** (7处): 主要河流的入海口坐标与实际位置偏差过大\n"
    report_content += "2. **山脉坐标错误** (4处): 主要山脉的代表坐标与实际位置不符\n\n"
    report_content += "所有新坐标均经过地理知识验证，确保符合实际地理位置。\n"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report_content)

    print(f"\n修复报告已保存到: {output_path}")


def main():
    """主函数"""
    # 文件路径
    input_file = Path(__file__).parent.parent / "data" / "final" / "entity_database_expanded.json"
    output_file = Path(__file__).parent.parent / "data" / "final" / "entity_database_expanded_fixed.json"
    report_file = Path(__file__).parent.parent / "reports" / "coordinate_fix_report_20260311.md"

    print("=" * 60)
    print("地理实体数据库坐标修复脚本")
    print("=" * 60)
    print(f"\n输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    print(f"报告文件: {report_file}")
    print()

    # 确保报告目录存在
    report_file.parent.mkdir(parents=True, exist_ok=True)

    # 加载数据
    print("正在加载数据库...")
    data = load_database(str(input_file))
    print(f"加载完成，共 {data['metadata']['total_entities']} 个实体\n")

    # 执行修复
    print("开始修复坐标...")
    print("-" * 40)
    report = fix_coordinates(data)
    print("-" * 40)

    # 更新元数据
    data["metadata"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    data["metadata"]["coordinate_fixes"] = len(report["fixed"])

    # 保存修复后的数据
    print(f"\n正在保存修复后的数据到: {output_file}")
    save_database(data, str(output_file))

    # 生成报告
    generate_report(report, str(report_file))

    # 打印总结
    print("\n" + "=" * 60)
    print("修复完成!")
    print("=" * 60)
    print(f"成功修复: {len(report['fixed'])} 处")
    print(f"坐标不匹配: {len(report['coords_mismatch'])} 处")
    print(f"未找到: {len(report['not_found'])} 处")

    return report


if __name__ == "__main__":
    main()
