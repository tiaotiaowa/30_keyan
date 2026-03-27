#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoKD-SR数据集偏差分析脚本

分析数据集中的设计偏差，包括：
1. 坐标模式偏差（问题中是否包含坐标信息）
2. 提示词偏差（任务暗示、关系类型泄露、推理模式引导等）
3. 空间关系类型分布
4. 各类型下的偏差交叉分析
"""

import json
import re
import os
from collections import defaultdict, Counter
from datetime import datetime
from typing import Dict, List, Any, Tuple


class DatasetBiasAnalyzer:
    """数据集偏差分析器"""

    @property
    def COORD_PATTERNS(self):
        """坐标相关正则表达式模式"""
        return [
            r'北纬\d+\.?\d*度?',
            r'南纬\d+\.?\d*度?',
            r'东经\d+\.?\d*度?',
            r'西经\d+\.?\d*度?',
            r'\d+\.?\d*°?[NS]',
            r'\d+\.?\d*°?[EW]',
            r'纬度\d+\.?\d*度?',
            r'经度\d+\.?\d*度?',
            r'\(\s*\d+\.?\d*\s*[°,]\s*\d+\.?\d*\s*[°,]\s*\d+\.?\d*\s*[\'"]?\s*[NSEW]\)',
            r'\(\s*\d+\.?\d*°[NSEW]\s*,\s*\d+\.?\d*°[NSEW]\s*\)',
        ]

    @property
    def PROMPT_BIAS_PATTERNS(self):
        """提示词偏差模式"""
        return {
            'task_hint': (r'请判断|请计算|请确定|请分析', '任务暗示类'),
            'relation_leak_topology': (r'从拓扑关系来看|从拓扑角度', '拓扑关系泄露'),
            'relation_leak_spatial': (r'从空间关系来看|从空间角度', '空间关系泄露'),
            'relation_leak_general': (r'从.*关系来看|从.*角度', '一般关系泄露'),
            'reasoning_guide': (r'请逐步推理|请详细推理|请推理', '推理模式引导'),
            'polite_prompt': (r'请估算|请问|请告诉我|请求|请问您', '礼貌性提示'),
        }

    def __init__(self, data_path: str):
        """
        初始化分析器

        Args:
            data_path: JSONL数据文件路径
        """
        self.data_path = data_path
        self.records = []
        self.coord_regex = re.compile('|'.join(self.COORD_PATTERNS), re.IGNORECASE)

        # 编译提示词偏差正则
        self.prompt_bias_regex = {}
        for key, (pattern, desc) in self.PROMPT_BIAS_PATTERNS.items():
            self.prompt_bias_regex[key] = {
                'regex': re.compile(pattern),
                'desc': desc
            }

    def load_data(self) -> None:
        """加载JSONL数据文件"""
        print(f"正在加载数据文件: {self.data_path}")
        with open(self.data_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    if line.strip():
                        self.records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"警告: 第{line_num}行JSON解析失败: {e}")
        print(f"成功加载 {len(self.records)} 条记录")

    def has_coords_in_question(self, question: str) -> bool:
        """
        检测问题中是否包含坐标信息

        Args:
            question: 问题文本

        Returns:
            是否包含坐标
        """
        return bool(self.coord_regex.search(question))

    def detect_prompt_biases(self, question: str) -> Dict[str, bool]:
        """
        检测问题中的提示词偏差

        Args:
            question: 问题文本

        Returns:
            各类偏差的检测结果
        """
        results = {}
        for key, config in self.prompt_bias_regex.items():
            results[key] = bool(config['regex'].search(question))
        return results

    def analyze(self) -> Dict[str, Any]:
        """
        执行完整的偏差分析

        Returns:
            分析结果字典
        """
        if not self.records:
            self.load_data()

        print("\n" + "="*60)
        print("开始分析数据集偏差")
        print("="*60)

        # 统计计数器
        total_count = len(self.records)
        coords_count = 0
        no_coords_count = 0
        prompt_bias_counts = {key: 0 for key in self.PROMPT_BIAS_PATTERNS.keys()}
        relation_type_counts = Counter()
        relation_type_coords = defaultdict(lambda: {'with_coords': 0, 'without_coords': 0})
        relation_type_biases = defaultdict(lambda: {key: 0 for key in self.PROMPT_BIAS_PATTERNS.keys()})

        # 详细记录
        records_with_coords = []
        records_with_prompt_biases = defaultdict(list)

        # 遍历所有记录进行分析
        for record in self.records:
            question = record.get('question', '')
            relation_type = record.get('spatial_relation_type', 'unknown')

            # 统计关系类型
            relation_type_counts[relation_type] += 1

            # 检测坐标
            has_coords = self.has_coords_in_question(question)
            if has_coords:
                coords_count += 1
                records_with_coords.append({
                    'id': record.get('id'),
                    'question': question[:100],
                    'relation_type': relation_type
                })
            else:
                no_coords_count += 1

            # 按关系类型统计坐标分布
            if has_coords:
                relation_type_coords[relation_type]['with_coords'] += 1
            else:
                relation_type_coords[relation_type]['without_coords'] += 1

            # 检测提示词偏差
            biases = self.detect_prompt_biases(question)
            for bias_key, has_bias in biases.items():
                if has_bias:
                    prompt_bias_counts[bias_key] += 1
                    relation_type_biases[relation_type][bias_key] += 1

                    # 记录部分样本
                    if len(records_with_prompt_biases[bias_key]) < 10:
                        records_with_prompt_biases[bias_key].append({
                            'id': record.get('id'),
                            'question': question[:100],
                            'relation_type': relation_type
                        })

        # 构建结果
        results = {
            'metadata': {
                'data_path': self.data_path,
                'analysis_time': datetime.now().isoformat(),
                'total_records': total_count
            },
            'coordinate_analysis': {
                'total_with_coords': coords_count,
                'total_without_coords': no_coords_count,
                'with_coords_ratio': coords_count / total_count if total_count > 0 else 0,
                'without_coords_ratio': no_coords_count / total_count if total_count > 0 else 0,
                'sample_records_with_coords': records_with_coords[:20]
            },
            'prompt_bias_analysis': {
                'counts': prompt_bias_counts,
                'ratios': {k: v / total_count for k, v in prompt_bias_counts.items()},
                'sample_records': dict(records_with_prompt_biases)
            },
            'relation_type_distribution': dict(relation_type_counts),
            'relation_type_coords': dict(relation_type_coords),
            'relation_type_biases': dict(relation_type_biases)
        }

        return results

    def print_summary(self, results: Dict[str, Any]) -> None:
        """打印分析摘要"""
        print("\n" + "="*60)
        print("数据集偏差分析报告")
        print("="*60)

        metadata = results['metadata']
        print(f"\n[数据概览]")
        print(f"  数据文件: {metadata['data_path']}")
        print(f"  分析时间: {metadata['analysis_time']}")
        print(f"  总记录数: {metadata['total_records']}")

        # 坐标模式分析
        coord = results['coordinate_analysis']
        print(f"\n[坐标模式分析]")
        print(f"  包含坐标: {coord['total_with_coords']} 条 ({coord['with_coords_ratio']:.2%})")
        print(f"  不含坐标: {coord['total_without_coords']} 条 ({coord['without_coords_ratio']:.2%})")

        # 提示词偏差分析
        print(f"\n[提示词偏差分析]")
        bias_counts = results['prompt_bias_analysis']['counts']
        bias_ratios = results['prompt_bias_analysis']['ratios']
        for key, pattern_desc in self.PROMPT_BIAS_PATTERNS.items():
            desc = pattern_desc[1]
            count = bias_counts.get(key, 0)
            ratio = bias_ratios.get(key, 0)
            print(f"  {desc}: {count} 条 ({ratio:.2%})")

        # 关系类型分布
        print(f"\n[空间关系类型分布]")
        for rel_type, count in sorted(results['relation_type_distribution'].items()):
            ratio = count / metadata['total_records']
            print(f"  {rel_type}: {count} 条 ({ratio:.2%})")

        # 交叉分析
        print(f"\n[各关系类型的坐标分布]")
        for rel_type in sorted(results['relation_type_coords'].keys()):
            coords_data = results['relation_type_coords'][rel_type]
            total = coords_data['with_coords'] + coords_data['without_coords']
            with_ratio = coords_data['with_coords'] / total if total > 0 else 0
            print(f"  {rel_type}: 含坐标 {coords_data['with_coords']} ({with_ratio:.2%}) / "
                  f"不含坐标 {coords_data['without_coords']} ({1-with_ratio:.2%})")

        print("\n" + "="*60)

    def save_results(self, results: Dict[str, Any], output_dir: str) -> None:
        """
        保存分析结果

        Args:
            results: 分析结果
            output_dir: 输出目录
        """
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存JSON格式统计结果
        json_path = os.path.join(output_dir, f"bias_statistics_{timestamp}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n统计结果已保存至: {json_path}")

        # 生成Markdown格式报告
        md_path = os.path.join(output_dir, f"bias_report_{timestamp}.md")
        self._generate_markdown_report(results, md_path)
        print(f"分析报告已保存至: {md_path}")

    def _generate_markdown_report(self, results: Dict[str, Any], output_path: str) -> None:
        """生成Markdown格式的分析报告"""
        metadata = results['metadata']
        coord = results['coordinate_analysis']
        bias_analysis = results['prompt_bias_analysis']

        lines = [
            "# GeoKD-SR 数据集偏差分析报告",
            "",
            f"**生成时间**: {metadata['analysis_time']}",
            f"**数据文件**: {metadata['data_path']}",
            f"**总记录数**: {metadata['total_records']}",
            "",
            "---",
            "",
            "## 1. 数据概览",
            "",
            f"| 指标 | 数值 |",
            f"|------|------|",
            f"| 总记录数 | {metadata['total_records']} |",
            f"| 空间关系类型数 | {len(results['relation_type_distribution'])} |",
            "",
            "## 2. 坐标模式分析",
            "",
            "检测问题文本中是否包含显式坐标信息（如北纬、东经、度数标记等）。",
            "",
            f"| 类别 | 数量 | 占比 |",
            f"|------|------|------|",
            f"| 包含坐标 | {coord['total_with_coords']} | {coord['with_coords_ratio']:.2%} |",
            f"| 不含坐标 | {coord['total_without_coords']} | {coord['without_coords_ratio']:.2%} |",
            "",
            "**检测模式**:",
        ]

        for pattern in self.COORD_PATTERNS:
            lines.append(f"- `{pattern}`")

        lines.extend([
            "",
            "## 3. 提示词偏差分析",
            "",
            "检测问题文本中可能引导模型行为的提示词模式。",
            "",
            f"| 偏差类型 | 数量 | 占比 | 说明 |",
            f"|----------|------|------|------|",
        ])

        for key, count in bias_analysis['counts'].items():
            desc = self.PROMPT_BIAS_PATTERNS[key][1]
            ratio = bias_analysis['ratios'][key]
            lines.append(f"| {desc} | {count} | {ratio:.2%} | `{self.PROMPT_BIAS_PATTERNS[key][0]}` |")

        lines.extend([
            "",
            "## 4. 空间关系类型分布",
            "",
            f"| 关系类型 | 数量 | 占比 |",
            f"|----------|------|------|",
        ])

        total = metadata['total_records']
        for rel_type, count in sorted(results['relation_type_distribution'].items()):
            ratio = count / total
            lines.append(f"| {rel_type} | {count} | {ratio:.2%} |")

        lines.extend([
            "",
            "## 5. 交叉分析：各关系类型的坐标分布",
            "",
            f"| 关系类型 | 含坐标 | 不含坐标 | 含坐标占比 |",
            f"|----------|--------|----------|------------|",
        ])

        for rel_type in sorted(results['relation_type_coords'].keys()):
            coords_data = results['relation_type_coords'][rel_type]
            total_type = coords_data['with_coords'] + coords_data['without_coords']
            with_ratio = coords_data['with_coords'] / total_type if total_type > 0 else 0
            lines.append(f"| {rel_type} | {coords_data['with_coords']} | {coords_data['without_coords']} | {with_ratio:.2%} |")

        lines.extend([
            "",
            "## 6. 交叉分析：各关系类型的提示词偏差",
            "",
            f"| 关系类型 | 任务暗示 | 关系泄露 | 推理引导 | 礼貌提示 |",
            f"|----------|----------|----------|----------|----------|",
        ])

        bias_order = ['task_hint', 'relation_leak_topology', 'relation_leak_spatial',
                      'relation_leak_general', 'reasoning_guide', 'polite_prompt']

        for rel_type in sorted(results['relation_type_biases'].keys()):
            biases = results['relation_type_biases'][rel_type]
            total_type = sum(results['relation_type_coords'][rel_type].values())

            # 合并所有关系泄露
            relation_leak = biases.get('relation_leak_topology', 0) + \
                           biases.get('relation_leak_spatial', 0) + \
                           biases.get('relation_leak_general', 0)
            task_hint = biases.get('task_hint', 0)
            reasoning = biases.get('reasoning_guide', 0)
            polite = biases.get('polite_prompt', 0)

            lines.append(f"| {rel_type} | {task_hint} | {relation_leak} | {reasoning} | {polite} |")

        lines.extend([
            "",
            "## 7. 样本记录",
            "",
            "### 7.1 包含坐标的样本",
            "",
        ])

        for i, sample in enumerate(coord['sample_records_with_coords'][:10], 1):
            lines.extend([
                f"**样本 {i}** (ID: {sample['id']}, 类型: {sample['relation_type']})",
                "",
                f"> {sample['question']}...",
                "",
            ])

        lines.extend([
            "### 7.2 包含提示词偏差的样本",
            "",
        ])

        for bias_key, samples in bias_analysis['sample_records'].items():
            desc = self.PROMPT_BIAS_PATTERNS[bias_key][1]
            lines.append(f"#### {desc}")
            lines.append("")
            for i, sample in enumerate(samples[:5], 1):
                lines.extend([
                    f"**样本 {i}** (ID: {sample['id']}, 类型: {sample['relation_type']})",
                    "",
                    f"> {sample['question']}...",
                    "",
                ])

        lines.extend([
            "---",
            "",
            "*本报告由 analyze_dataset_bias.py 自动生成*",
        ])

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))


def main():
    """主函数"""
    # 配置路径
    data_path = "D:/30_keyan/GeoKD-SR/data/geosr_chain/balanced_topology_final.jsonl"
    output_dir = "D:/30_keyan/GeoKD-SR/outputs/bias_analysis"

    # 检查数据文件是否存在
    if not os.path.exists(data_path):
        print(f"错误: 数据文件不存在: {data_path}")
        return

    # 创建分析器并执行分析
    analyzer = DatasetBiasAnalyzer(data_path)

    # 执行分析
    results = analyzer.analyze()

    # 打印摘要
    analyzer.print_summary(results)

    # 保存结果
    analyzer.save_results(results, output_dir)

    print("\n分析完成!")


if __name__ == "__main__":
    main()
