======================================================================
推理链泄露修复报告
======================================================================
生成时间: 2026-03-08 22:33:53

修复统计:
  总记录数: 10106
  总推理步骤数: 50531
  修复relation_type字段: 10106 处
  修复action字段: 10107 处

relation_type分布 (修复前):
  - metric: 3159
  - directional: 2912
  - composite: 2360
  - topological: 1675

action分布 (修复前):
  - calculate_distance: 3159
  - calculate_direction: 2912
  - calculate_composite: 2361
  - determine_topology: 1675

修复映射:
  relation_type: directional→spatial, topological→spatial, metric→spatial, composite→spatial
  action: calculate_distance→process_spatial, determine_topology→process_spatial, calculate_direction→process_spatial, classify_relation→analyze_spatial, calculate_composite→analyze_spatial

======================================================================