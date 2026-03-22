#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
地理实体数据库坐标修复脚本 V2.0
修复 entity_database_expanded_fixed.json 中新发现的问题

创建时间: 2026-03-11
"""

import json
from datetime import datetime
from pathlib import Path

# 需要修复的问题
FIXES = {
    # 坐标微调
    "coordinate_adjustments": {
        "五台山": {
            "old_coords": [113.5833, 39.0333],
            "new_coords": [113.6, 38.9],
            "reason": "五台山位于忻州市五台县，原坐标偏北约100km"
        },
    },

    # 重复实体合并（保留第一个，删除第二个）
    "duplicate_removal": {
        "雪峰山脉": {
            "keep": "雪峰山",
            "remove": "雪峰山脉",
            "reason": "雪峰山和雪峰山脉是同一山脉，存在重复记录"
        }
    },

    # 属性修正
    "attribute_fixes": {
        "长白山脉": {
            "field": "highest_peak",
            "old_value": "白头山",
            "new_value": "将军峰",
            "reason": "白头山为朝鲜称呼，中国官方名称为将军峰"
        }
    }
}


def load_database(file_path: str) -> dict:
    """加载数据库文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_database(data: dict, file_path: str):
    """保存数据库文件"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def apply_fixes(data: dict) -> dict:
    """应用所有修复"""
    report = {
        "coordinate_adjustments": [],
        "duplicate_removal": [],
        "attribute_fixes": [],
        "errors": []
    }

    entities = data.get("entities", {})

    # 1. 坐标微调
    print("=" * 50)
    print("1. 坐标微调")
    print("-" * 50)
    for entity_name, fix_info in FIXES["coordinate_adjustments"].items():
        found = False
        for entity_type, entity_list in entities.items():
            if not isinstance(entity_list, list):
                continue
            for entity in entity_list:
                if entity.get("name") == entity_name:
                    found = True
                    current_coords = entity.get("coords", [])
                    if current_coords == fix_info["old_coords"]:
                        entity["coords"] = fix_info["new_coords"]
                        report["coordinate_adjustments"].append({
                            "name": entity_name,
                            "type": entity_type,
                            "old_coords": fix_info["old_coords"],
                            "new_coords": fix_info["new_coords"],
                            "reason": fix_info["reason"]
                        })
                        print(f"[修复] {entity_name}: {fix_info['old_coords']} -> {fix_info['new_coords']}")
                    else:
                        print(f"[跳过] {entity_name}: 当前坐标与预期不符")
                        print(f"       预期: {fix_info['old_coords']}, 实际: {current_coords}")
                    break
            if found:
                break
        if not found:
            print(f"[未找到] {entity_name}")
            report["errors"].append(f"未找到实体: {entity_name}")

    # 2. 重复实体处理
    print("\n" + "=" * 50)
    print("2. 重复实体检查")
    print("-" * 50)
    for dup_name, fix_info in FIXES["duplicate_removal"].items():
        keep_name = fix_info["keep"]
        found_keep = False
        found_dup = False

        for entity_type, entity_list in entities.items():
            if not isinstance(entity_list, list):
                continue

            # 检查是否存在重复
            indices_to_check = []
            for i, entity in enumerate(entity_list):
                if entity.get("name") == keep_name:
                    found_keep = True
                elif entity.get("name") == dup_name:
                    found_dup = True
                    indices_to_check.append(i)

            # 如果找到重复，标记但不自动删除（需要人工确认）
            if found_dup:
                report["duplicate_removal"].append({
                    "keep": keep_name,
                    "remove": dup_name,
                    "type": entity_type,
                    "reason": fix_info["reason"],
                    "action": "需要人工确认后删除"
                })
                print(f"[发现重复] '{keep_name}' 和 '{dup_name}' 在 {entity_type} 中")
                print(f"           建议保留: {keep_name}, 删除: {dup_name}")

        if not found_keep and not found_dup:
            print(f"[未找到重复] {keep_name} / {dup_name}")

    # 3. 属性修正
    print("\n" + "=" * 50)
    print("3. 属性修正")
    print("-" * 50)
    for entity_name, fix_info in FIXES["attribute_fixes"].items():
        found = False
        for entity_type, entity_list in entities.items():
            if not isinstance(entity_list, list):
                continue
            for entity in entity_list:
                if entity.get("name") == entity_name:
                    found = True
                    field = fix_info["field"]
                    current_value = entity.get(field, "")
                    if current_value == fix_info["old_value"]:
                        entity[field] = fix_info["new_value"]
                        report["attribute_fixes"].append({
                            "name": entity_name,
                            "type": entity_type,
                            "field": field,
                            "old_value": fix_info["old_value"],
                            "new_value": fix_info["new_value"],
                            "reason": fix_info["reason"]
                        })
                        print(f"[修复] {entity_name}.{field}: '{fix_info['old_value']}' -> '{fix_info['new_value']}'")
                    else:
                        print(f"[跳过] {entity_name}.{field}: 当前值为 '{current_value}'")
                    break
            if found:
                break
        if not found:
            print(f"[未找到] {entity_name}")
            report["errors"].append(f"未找到实体: {entity_name}")

    return report


def generate_report(report: dict, output_path: str):
    """生成修复报告"""
    report_content = f"""# 地理实体数据库修复报告 V2.0

生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 修复统计

- 坐标微调: {len(report['coordinate_adjustments'])} 处
- 重复实体检查: {len(report['duplicate_removal'])} 处
- 属性修正: {len(report['attribute_fixes'])} 处
- 错误: {len(report['errors'])} 处

## 详细修复记录

### 1. 坐标微调

"""

    for item in report["coordinate_adjustments"]:
        report_content += f"- **{item['name']}** ({item['type']})\n"
        report_content += f"  - 旧坐标: {item['old_coords']}\n"
        report_content += f"  - 新坐标: {item['new_coords']}\n"
        report_content += f"  - 原因: {item['reason']}\n\n"

    report_content += "\n### 2. 重复实体检查\n\n"

    for item in report["duplicate_removal"]:
        report_content += f"- **{item['keep']}** / **{item['remove']}** ({item['type']})\n"
        report_content += f"  - 原因: {item['reason']}\n"
        report_content += f"  - 操作: {item['action']}\n\n"

    report_content += "\n### 3. 属性修正\n\n"

    for item in report["attribute_fixes"]:
        report_content += f"- **{item['name']}** ({item['type']})\n"
        report_content += f"  - 字段: {item['field']}\n"
        report_content += f"  - 旧值: {item['old_value']}\n"
        report_content += f"  - 新值: {item['new_value']}\n"
        report_content += f"  - 原因: {item['reason']}\n\n"

    if report["errors"]:
        report_content += "\n### 4. 错误\n\n"
        for error in report["errors"]:
            report_content += f"- {error}\n"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report_content)

    print(f"\n修复报告已保存到: {output_path}")


def main():
    """主函数"""
    # 文件路径
    input_file = Path(__file__).parent.parent / "data" / "final" / "entity_database_expanded_fixed.json"
    output_file = Path(__file__).parent.parent / "data" / "final" / "entity_database_expanded_v2.json"
    report_file = Path(__file__).parent.parent / "reports" / "coordinate_fix_report_v2_20260311.md"

    print("=" * 60)
    print("地理实体数据库坐标修复脚本 V2.0")
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
    report = apply_fixes(data)

    # 更新元数据
    data["metadata"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    data["metadata"]["coordinate_fixes_v2"] = len(report["coordinate_adjustments"])

    # 保存修复后的数据
    print(f"\n正在保存修复后的数据到: {output_file}")
    save_database(data, str(output_file))

    # 生成报告
    generate_report(report, str(report_file))

    # 打印总结
    print("\n" + "=" * 60)
    print("修复完成!")
    print("=" * 60)
    print(f"坐标微调: {len(report['coordinate_adjustments'])} 处")
    print(f"重复实体: {len(report['duplicate_removal'])} 处 (需人工确认)")
    print(f"属性修正: {len(report['attribute_fixes'])} 处")
    print(f"错误: {len(report['errors'])} 处")

    return report


if __name__ == "__main__":
    main()
