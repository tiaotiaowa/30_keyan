#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GeoKD-SR 数据字段修复脚本""" 
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from collections import Counter
import sys

DIFFICULTY_SCORE_MAP = {"easy": 1.5, "medium": 2.75, "hard": 4.0}
SPATIAL_TYPE_BONUS = {"directional": 1.2, "topological": 2.2, "metric": 1.3, "composite": 3.2}
TOPOLOGY_BONUS = {"within": 0.0, "contains": 0.1, "adjacent": 0.3, "disjoint": 0.4, "overlap": 0.6}

def calculate_difficulty_score(data: dict) -> float:
    difficulty = data.get("difficulty", "medium")
    base_score = DIFFICULTY_SCORE_MAP.get(difficulty, 2.75)
    spatial_type = data.get("spatial_relation_type", "metric")
    type_bonus = SPATIAL_TYPE_BONUS.get(spatial_type, 1.3) - 1.0
    topo_bonus = 0.0
    if spatial_type == "topological":
        topo_subtype = data.get("topology_subtype", "")
        topo_bonus = TOPOLOGY_BONUS.get(topo_subtype, 0.0)
    final_score = base_score + type_bonus * 0.5 + topo_bonus * 0.3
    return round(max(1.0, min(5.0, final_score)), 1)

def add_entity_to_token(data: dict) -> dict:
    if "entity_to_token" in data and data["entity_to_token"]:
        return data
    question = data.get("question", "")
    entities = data.get("entities", [])
    entity_to_token = {}
    for entity in entities:
        name = entity.get("name", "")
        if name:
            char_start = question.find(name)
            if char_start >= 0:
                char_end = char_start + len(name)
                entity_to_token[name] = {"char_start": char_start, "char_end": char_end, "token_indices": list(range(char_start, char_end))}
    data["entity_to_token"] = entity_to_token
    return data

def process_file(input_path: Path, stats: dict) -> List[dict]:
    records = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                record = json.loads(line)
                stats["total"] += 1
                if "difficulty_score" not in record:
                    stats["missing_difficulty_score"] += 1
                if "entity_to_token" not in record or not record.get("entity_to_token"):
                    stats["missing_entity_to_token"] += 1
                if "difficulty_score" not in record:
                    record["difficulty_score"] = calculate_difficulty_score(record)
                record = add_entity_to_token(record)
                records.append(record)
    return records

def process_directory(input_dir: Path, output_file: Path):
    all_records = []
    stats = {"total": 0, "missing_difficulty_score": 0, "missing_entity_to_token": 0, "files_processed": 0}
    jsonl_files = sorted(input_dir.glob("*.jsonl"))
    print(f"Found {len(jsonl_files)} JSONL files")
    for jsonl_file in jsonl_files:
        print(f"Processing: {jsonl_file.name}")
        records = process_file(jsonl_file, stats)
        all_records.extend(records)
        stats["files_processed"] += 1
        print(f"  Records: {len(records)}")
    print(f"Total records: {stats['total']}")
    print(f"Missing difficulty_score: {stats['missing_difficulty_score']}")
    print(f"Missing entity_to_token: {stats['missing_entity_to_token']}")
    with open(output_file, "w", encoding="utf-8") as f:
        for record in all_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"Output: {output_file}")
    print(f"Total written: {len(all_records)}")
    return stats

def main():
    parser = argparse.ArgumentParser(description="GeoKD-SR Data Field Fix")
    parser.add_argument("--input", "-i", default="c:/Users/60207/Documents/hibiki works")
    parser.add_argument("--output", "-o", default="D:/30_keyan/GeoKD-SR/data/geosr_chain/generated_fixed.jsonl")
    args = parser.parse_args()
    input_dir = Path(args.input)
    output_file = Path(args.output)
    if not input_dir.exists():
        print(f"Error: Input directory not found - {input_dir}")
        sys.exit(1)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    print("=" * 60)
    print("GeoKD-SR Data Field Fix Script")
    print("=" * 60)
    print(f"Input: {input_dir}")
    print(f"Output: {output_file}")
    process_directory(input_dir, output_file)
    print("Done!")

if __name__ == "__main__":
    main()
