"""
检查数据结构
"""
import json
from pathlib import Path

def check_jsonl_structure(filepath, num_samples=3):
    """检查JSONL文件的数据结构"""
    print(f"\n检查文件: {filepath}")
    print("="*60)

    with open(filepath, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= num_samples:
                break
            data = json.loads(line.strip())
            print(f"\n样本 {i+1}:")
            print(json.dumps(data, ensure_ascii=False, indent=2))

# 检查正例和负例数据
check_jsonl_structure(Path(r"D:\gis_data\output\pairs_positive.jsonl"))
check_jsonl_structure(Path(r"D:\gis_data\output\pairs_negative.jsonl"))
