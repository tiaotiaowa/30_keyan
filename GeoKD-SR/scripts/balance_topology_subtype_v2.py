"""
拓扑子类型平衡脚本 v2
执行阶段2：平衡拓扑关系子类型分布
"""
import json
import random
from collections import defaultdict, Counter

random.seed(42)

# 文件路径
input_file = 'D:/30_keyan/GeoKD-SR/data/geosr_chain/balanced_topology.jsonl'
output_file = 'D:/30_keyan/GeoKD-SR/data/geosr_chain/balanced_topology_v3.jsonl'

# 读取数据
print("正在读取数据...")
data = []
with open(input_file, 'r', encoding='utf-8') as f:
    for line in f:
        if line.strip():
            data.append(json.loads(line))

print(f"总数据量: {len(data)} 条")

# 分离拓扑和非拓扑数据
topo_records = [r for r in data if r.get('spatial_relation_type') == 'topological']
other_records = [r for r in data if r.get('spatial_relation_type') != 'topological']

print(f"\n拓扑关系数据: {len(topo_records)} 条")
print(f"非拓扑关系数据: {len(other_records)} 条")

# 统计当前拓扑子类型分布
print("\n=== 当前拓扑子类型分布 ===")
subtype_counter = Counter(r.get('topology_subtype', 'unknown') for r in topo_records)
for subtype, count in sorted(subtype_counter.items(), key=lambda x: -x[1]):
    pct = count / len(topo_records) * 100 if topo_records else 0
    print(f"  {subtype}: {count} ({pct:.1f}%)")

# 标准子类型
standard_subtypes = {'within', 'contains', 'adjacent', 'overlap', 'disjoint'}

# 删除非标准子类型
print("\n=== 删除非标准子类型 ===")
non_standard = [r for r in topo_records if r.get('topology_subtype') not in standard_subtypes]
print(f"删除非标准子类型数据: {len(non_standard)} 条")
for r in non_standard:
    subtype = r.get('topology_subtype', 'unknown')
    print(f"  - {subtype}")

cleaned_topo = [r for r in topo_records if r.get('topology_subtype') in standard_subtypes]
print(f"清理后拓扑数据: {len(cleaned_topo)} 条")

# 按子类型分组
by_subtype = defaultdict(list)
for r in cleaned_topo:
    subtype = r.get('topology_subtype')
    by_subtype[subtype].append(r)

# 确定每个类型的保留数量（以最小overlap数量为基准）
print("\n=== 平衡处理 ===")
subtype_counts = {k: len(v) for k, v in by_subtype.items()}
min_count = min(subtype_counts.values())
print(f"最小子类型数量(基准): {min_count} 条")
target_per_type = min_count

# 计算需要删除的数量
for subtype in standard_subtypes:
    count = len(by_subtype.get(subtype, []))
    to_delete = count - target_per_type if count > target_per_type else 0
    print(f"  {subtype}: {count} -> {target_per_type} (删除 {to_delete} 条)")

# 平衡拓扑数据
balanced_topo = []
for subtype in standard_subtypes:
    records = by_subtype.get(subtype, [])
    random.shuffle(records)
    balanced_topo.extend(records[:target_per_type])

# 合并数据
final_data = other_records + balanced_topo

# 保存结果
print(f"\n=== 保存结果 ===")
with open(output_file, 'w', encoding='utf-8') as f:
    for r in final_data:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')

print(f"输出文件: {output_file}")
print(f"最终数据量: {len(final_data)} 条")
print(f"  - 非拓扑关系: {len(other_records)} 条")
print(f"  - 拓扑关系(平衡后): {len(balanced_topo)} 条")

# 最终拓扑子类型分布验证
print("\n=== 最终拓扑子类型分布验证 ===")
final_topo = [r for r in final_data if r.get('spatial_relation_type') == 'topological']
final_subtype_counter = Counter(r.get('topology_subtype') for r in final_topo)
for subtype in standard_subtypes:
    count = final_subtype_counter.get(subtype, 0)
    pct = count / len(final_topo) * 100 if final_topo else 0
    print(f"  {subtype}: {count} ({pct:.1f}%)")

print("\n处理完成！")
