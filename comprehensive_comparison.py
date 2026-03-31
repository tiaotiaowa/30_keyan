#!/usr/bin/env python3
"""
Comprehensive comparison analysis: exp05 (Reverse KL) vs exp02 (Forward KL) vs Baseline vs SFT vs Teacher-7B
READ-ONLY analysis - prints all results to console
"""

import json
import re
import numpy as np
from collections import Counter, defaultdict

# ============================================================
# 1. Load all prediction files
# ============================================================
files = {
    "exp05_ReverseKL": "/mnt/workspace/30_keyan/GeoKD-SR/exp/exp05_reverse_kl/outputs/predictions.jsonl",
    "exp02_ForwardKL": "/mnt/workspace/30_keyan/GeoKD-SR/exp/exp02_standard_kd/outputs/predictions.jsonl",
    "Baseline_1.5B": "/mnt/workspace/30_keyan/GeoKD-SR/exp/exp0/exp0/stage1_generation/outputs/predictions_qwen.jsonl",
    "SFT_1.5B": "/mnt/workspace/30_keyan/GeoKD-SR/exp/exp0/qwen-1.5B-sft/eval_results_exp0/predictions.jsonl",
    "Teacher_7B": "/mnt/workspace/30_keyan/GeoKD-SR/exp/exp0/qwen-7B/stage1_generation/outputs/splits_predictions.jsonl",
}

data = {}
for name, path in files.items():
    records = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            records.append(json.loads(line.strip()))
    data[name] = records
    print(f"Loaded {name}: {len(records)} records")

# Build lookup by id
by_id = {}
for name, records in data.items():
    by_id[name] = {r['id']: r for r in records}

# Verify all IDs match
base_ids = set(by_id["exp05_ReverseKL"].keys())
for name in by_id:
    assert set(by_id[name].keys()) == base_ids, f"ID mismatch for {name}"
print(f"\nAll {len(base_ids)} IDs verified identical across all 5 models.\n")

model_names = list(data.keys())
order = ["exp05_ReverseKL", "exp02_ForwardKL", "Baseline_1.5B", "SFT_1.5B", "Teacher_7B"]

# ============================================================
# Helper functions
# ============================================================
def normalize_answer(ans):
    """Normalize answer for comparison."""
    ans = ans.strip().rstrip('。.').strip()
    return ans

def is_correct(pred, ref):
    """Check if prediction matches reference (fuzzy)."""
    pred_norm = normalize_answer(pred)
    ref_norm = normalize_answer(ref)

    # Exact match after normalization
    if pred_norm == ref_norm:
        return True

    # Reference contained in prediction (for longer answers)
    if ref_norm in pred_norm:
        return True

    # Check if the core direction/number is in prediction
    # For directional: check if direction word appears
    directions = ['东', '南', '西', '北', '东南', '东北', '西南', '西北',
                  '正东', '正南', '正西', '正北', '偏东', '偏南', '偏西', '偏北']

    return False

def is_direction_correct(pred, ref_direction):
    """For directional questions, check if the predicted direction matches."""
    pred_norm = normalize_answer(pred)
    # Extract direction from prediction
    # The reference is typically like "东南方向" or "东南"
    ref_dir = ref_direction.replace('方向', '').strip().rstrip('。.').strip()

    # Check exact substring
    if ref_dir in pred_norm:
        return True

    # Check specific direction patterns
    dir_pattern = rf'(?:位于|在|处于)?.*?({ref_dir})'
    if re.search(dir_pattern, pred_norm):
        return True

    # Check if prediction starts with or contains the direction
    eight_dirs = ['东南', '东北', '西南', '西北', '正东', '正南', '正西', '正北', '东', '南', '西', '北']
    pred_dirs = []
    for d in eight_dirs:
        if d in pred_norm:
            pred_dirs.append(d)

    if ref_dir in pred_dirs:
        return True

    return False

def extract_distance_number(text):
    """Extract distance numbers from text."""
    nums = re.findall(r'(\d+\.?\d*)\s*(?:公里|千米|km)', text)
    return [float(n) for n in nums] if nums else []

def direction_match_flexible(pred, ref):
    """More flexible direction matching for directional accuracy."""
    pred_norm = normalize_answer(pred)
    ref_norm = normalize_answer(ref)

    if pred_norm == ref_norm:
        return True
    if ref_norm in pred_norm:
        return True

    # Extract the core compass direction from reference
    ref_core = ref_norm.replace('方向', '').strip()

    # Eight principal directions (check longer ones first)
    all_dirs = ['东南', '东北', '西南', '西北', '正东', '正南', '正西', '正北', '东', '南', '西', '北']

    # Find the best matching direction in reference
    ref_dir_found = None
    for d in all_dirs:
        if d in ref_core:
            ref_dir_found = d
            break

    if ref_dir_found is None:
        return False

    # Check if this direction appears in prediction
    if ref_dir_found in pred_norm:
        # Make sure it's not contradicted by a longer direction
        # e.g., if ref is "东", "东南" in pred should not match
        longer_dirs = [d for d in all_dirs if len(d) > len(ref_dir_found) and ref_dir_found in d]
        has_longer = any(d in pred_norm for d in longer_dirs)

        # If the reference itself is a compound direction like "东南", check exact
        if len(ref_dir_found) >= 2:
            return True
        # If reference is single char like "东", and prediction has "东南", it's wrong
        if has_longer:
            return False
        return True

    return False


# ============================================================
# ACCURACY COMPUTATION (flexible matching)
# ============================================================
print("=" * 100)
print("COMPREHENSIVE COMPARISON: exp05 (Reverse KL) vs exp02 (Forward KL) vs Baseline vs SFT vs Teacher-7B")
print("=" * 100)

# Compute accuracy for each model
# Use a more robust accuracy: normalize and check containment
def compute_accuracy(records):
    correct = 0
    for r in records:
        pred = r['prediction'].strip().rstrip('。.').strip()
        ref = r['reference'].strip().rstrip('。.').strip()
        if pred == ref or ref in pred:
            correct += 1
    return correct / len(records)

def compute_accuracy_by_group(records, key):
    groups = defaultdict(list)
    for r in records:
        groups[r[key]].append(r)
    results = {}
    for g, recs in groups.items():
        results[g] = compute_accuracy(recs)
    return results

# ============================================================
# 2. ANSWER LENGTH STATS
# ============================================================
print("\n" + "=" * 100)
print("1. ANSWER LENGTH STATISTICS (character count)")
print("=" * 100)

print(f"\n{'Model':<20} {'Mean':>8} {'Median':>8} {'Min':>6} {'Max':>6} {'Std':>8} {'Total':>8}")
print("-" * 70)
for name in order:
    lengths = [len(r['prediction']) for r in data[name]]
    print(f"{name:<20} {np.mean(lengths):>8.1f} {np.median(lengths):>8.1f} {min(lengths):>6} {max(lengths):>6} {np.std(lengths):>8.1f} {sum(lengths):>8}")

# ============================================================
# 3. DEFAULT ANSWER FREQUENCY
# ============================================================
print("\n" + "=" * 100)
print("2. DEFAULT ANSWER FREQUENCY")
print("=" * 100)

default_answers = ["约1200公里", "西南方向，约1200公里", "东北方向，约1200公里"]

print(f"\n{'Model':<20}", end="")
for da in default_answers:
    print(f" {'\"'+da+'\"':>22}", end="")
print(f" {'Any Default':>12}")
print("-" * 100)

for name in order:
    preds = [r['prediction'].strip() for r in data[name]]
    counts = []
    for da in default_answers:
        c = sum(1 for p in preds if da in p)
        counts.append(c)
    any_default = sum(1 for p in preds if any(da in p for da in default_answers))
    print(f"{name:<20}", end="")
    for c in counts:
        print(f" {c:>22}", end="")
    print(f" {any_default:>12}")

# ============================================================
# 4. ANSWER DIVERSITY
# ============================================================
print("\n" + "=" * 100)
print("3. ANSWER DIVERSITY")
print("=" * 100)

print(f"\n{'Model':<20} {'Unique':>8} {'Total':>8} {'Ratio':>8} {'Top-1':>30} {'Top-2':>30} {'Top-3':>30}")
print("-" * 130)

for name in order:
    preds = [r['prediction'].strip() for r in data[name]]
    counter = Counter(preds)
    unique = len(counter)
    total = len(preds)
    ratio = unique / total * 100
    top3 = counter.most_common(3)
    top_strs = [f"{t[0][:15]}...({t[1]})" if len(t[0]) > 15 else f"{t[0]}({t[1]})" for t in top3]
    while len(top_strs) < 3:
        top_strs.append("N/A")
    print(f"{name:<20} {unique:>8} {total:>8} {ratio:>7.1f}% {top_strs[0]:>30} {top_strs[1]:>30} {top_strs[2]:>30}")

# Print full top-5 for each model
print("\n--- Detailed Top-5 Most Frequent Predictions per Model ---")
for name in order:
    preds = [r['prediction'].strip() for r in data[name]]
    counter = Counter(preds)
    print(f"\n  {name}:")
    for i, (pred, count) in enumerate(counter.most_common(5)):
        pct = count / len(preds) * 100
        display = pred[:60] + "..." if len(pred) > 60 else pred
        print(f"    #{i+1}: [{count:4d}] ({pct:5.1f}%) \"{display}\"")

# ============================================================
# 5. FORMAT PATTERNS
# ============================================================
print("\n" + "=" * 100)
print("4. FORMAT PATTERNS")
print("=" * 100)

patterns = {
    "位于...内部": lambda p: bool(re.search(r'位于.*内部', p)),
    "是的,...": lambda p: p.startswith('是的'),
    "包含方向词": lambda p: bool(re.search(r'[东西南北]+方向?', p)),
    "包含距离数字": lambda p: bool(re.search(r'\d+\s*(?:公里|千米|km)', p)),
    "包含句号": lambda p: '。' in p,
    "纯方向词": lambda p: bool(re.fullmatch(r'[东南西北东西南北]{1,2}方向?', p.strip())),
    "包含bullet(•/)": lambda p: bool(re.search(r'[•/\-]\s*', p)),
}

print(f"\n{'Pattern':<20}", end="")
for name in order:
    short = name.split('_')[0] + '_' + name.split('_')[1][:6] if '_' in name else name[:15]
    print(f" {short:>15}", end="")
print()
print("-" * 95)

for pname, check_fn in patterns.items():
    print(f"{pname:<20}", end="")
    for name in order:
        count = sum(1 for r in data[name] if check_fn(r['prediction']))
        pct = count / len(data[name]) * 100
        print(f" {count:>7}({pct:4.1f}%)", end="")
    print()

# ============================================================
# 6. PER-TYPE ACCURACY COMPARISON
# ============================================================
print("\n" + "=" * 100)
print("5. PER-TYPE ACCURACY COMPARISON")
print("=" * 100)

# Get all spatial types
all_types = set()
for name in order:
    for r in data[name]:
        all_types.add(r['spatial_type'])
all_types = sorted(all_types)

print(f"\n{'Spatial Type':<15}", end="")
for name in order:
    short = name.replace("exp05_", "RKL:").replace("exp02_", "FKL:").replace("Baseline_", "BL:").replace("SFT_", "SFT:").replace("Teacher_", "T:")
    print(f" {short:>15}", end="")
print(f" {'Count':>6}")
print("-" * 100)

for stype in all_types:
    print(f"{stype:<15}", end="")
    count = 0
    for name in order:
        subset = [r for r in data[name] if r['spatial_type'] == stype]
        if count == 0:
            count = len(subset)
        acc = compute_accuracy(subset)
        print(f" {acc:>14.3f}", end="")
    print(f" {count:>6}")

# Overall
print(f"{'OVERALL':<15}", end="")
for name in order:
    acc = compute_accuracy(data[name])
    print(f" {acc:>14.3f}", end="")
print(f" {len(data[order[0]]):>6}")

# ============================================================
# 7. PER-DIFFICULTY ACCURACY COMPARISON
# ============================================================
print("\n" + "=" * 100)
print("6. PER-DIFFICULTY ACCURACY COMPARISON")
print("=" * 100)

difficulties = ['easy', 'medium', 'hard']

print(f"\n{'Difficulty':<15}", end="")
for name in order:
    short = name.replace("exp05_", "RKL:").replace("exp02_", "FKL:").replace("Baseline_", "BL:").replace("SFT_", "SFT:").replace("Teacher_", "T:")
    print(f" {short:>15}", end="")
print(f" {'Count':>6}")
print("-" * 100)

for diff in difficulties:
    print(f"{diff:<15}", end="")
    count = 0
    for name in order:
        subset = [r for r in data[name] if r['difficulty'] == diff]
        if count == 0:
            count = len(subset)
        acc = compute_accuracy(subset)
        print(f" {acc:>14.3f}", end="")
    print(f" {count:>6}")

# ============================================================
# 8. MODEL AGREEMENT MATRIX
# ============================================================
print("\n" + "=" * 100)
print("7. MODEL AGREEMENT MATRIX (pairwise exact prediction match rate)")
print("=" * 100)

short_names = ["RKL", "FKL", "BL", "SFT", "T7B"]

# Build prediction lookup
pred_by_id = {}
for name in order:
    pred_by_id[name] = {}
    for r in data[name]:
        pred_by_id[name][r['id']] = r['prediction'].strip()

print(f"\n{'':>12}", end="")
for sn in short_names:
    print(f" {sn:>12}", end="")
print()
print("-" * 75)

for i, name1 in enumerate(order):
    print(f"{short_names[i]:>12}", end="")
    for j, name2 in enumerate(order):
        if i == j:
            print(f" {'---':>12}", end="")
        else:
            matches = sum(1 for rid in base_ids if pred_by_id[name1][rid] == pred_by_id[name2][rid])
            rate = matches / len(base_ids) * 100
            print(f" {rate:>11.1f}%", end="")
    print()

# ============================================================
# 9. EXP05 vs EXP02 SPECIFIC COMPARISON
# ============================================================
print("\n" + "=" * 100)
print("8. EXP05 (Reverse KL) vs EXP02 (Forward KL) - HEAD-TO-HEAD")
print("=" * 100)

exp05 = by_id["exp05_ReverseKL"]
exp02 = by_id["exp02_ForwardKL"]

exp05_wins = []  # exp05 correct, exp02 wrong
exp02_wins = []  # exp02 correct, exp05 wrong
both_correct = []
both_wrong = []

for rid in base_ids:
    r05 = exp05[rid]
    r02 = exp02[rid]
    ref = r05['reference']

    c05 = is_correct(r05['prediction'], ref)
    c02 = is_correct(r02['prediction'], ref)

    if c05 and c02:
        both_correct.append(rid)
    elif c05:
        exp05_wins.append(rid)
    elif c02:
        exp02_wins.append(rid)
    else:
        both_wrong.append(rid)

print(f"\n  Overall Head-to-Head:")
print(f"    Both correct:   {len(both_correct):>5} ({len(both_correct)/len(base_ids)*100:.1f}%)")
print(f"    exp05 wins:     {len(exp05_wins):>5} ({len(exp05_wins)/len(base_ids)*100:.1f}%)")
print(f"    exp02 wins:     {len(exp02_wins):>5} ({len(exp02_wins)/len(base_ids)*100:.1f}%)")
print(f"    Both wrong:     {len(both_wrong):>5} ({len(both_wrong)/len(base_ids)*100:.1f}%)")

print(f"\n  By Spatial Type:")
print(f"  {'Type':<15} {'exp05 wins':>12} {'exp02 wins':>12} {'05-02 diff':>12}")
print("  " + "-" * 55)
for stype in all_types:
    type_ids = [rid for rid in base_ids if exp05[rid]['spatial_type'] == stype]
    w05 = sum(1 for rid in type_ids if rid in exp05_wins)
    w02 = sum(1 for rid in type_ids if rid in exp02_wins)
    print(f"  {stype:<15} {w05:>12} {w02:>12} {w05-w02:>+12}")

print(f"\n  By Difficulty:")
print(f"  {'Difficulty':<15} {'exp05 wins':>12} {'exp02 wins':>12} {'05-02 diff':>12}")
print("  " + "-" * 55)
for diff in difficulties:
    diff_ids = [rid for rid in base_ids if exp05[rid]['difficulty'] == diff]
    w05 = sum(1 for rid in diff_ids if rid in exp05_wins)
    w02 = sum(1 for rid in diff_ids if rid in exp02_wins)
    print(f"  {diff:<15} {w05:>12} {w02:>12} {w05-w02:>+12}")

# Show some example exp05 wins
print(f"\n  Example exp05 wins (first 5):")
for rid in exp05_wins[:5]:
    r = exp05[rid]
    print(f"    ID: {rid}")
    print(f"      Q: {r['question'][:60]}...")
    print(f"      Ref: {r['reference']}")
    print(f"      exp05: {r['prediction'][:80]}")
    print(f"      exp02: {exp02[rid]['prediction'][:80]}")
    print()

print(f"  Example exp02 wins (first 5):")
for rid in exp02_wins[:5]:
    r = exp02[rid]
    print(f"    ID: {rid}")
    print(f"      Q: {r['question'][:60]}...")
    print(f"      Ref: {r['reference']}")
    print(f"      exp02: {r['prediction'][:80]}")
    print(f"      exp05: {exp05[rid]['prediction'][:80]}")
    print()

# ============================================================
# 10. MODE COLLAPSE ANALYSIS
# ============================================================
print("\n" + "=" * 100)
print("9. MODE COLLAPSE ANALYSIS")
print("=" * 100)

print(f"\n{'Model':<20} {'Unique Preds':>14} {'Total Preds':>14} {'Unique Ratio':>14} {'Top-1 Freq':>12} {'Top-1 %':>10} {'Top-5 Cover':>12}")
print("-" * 90)

for name in order:
    preds = [r['prediction'].strip() for r in data[name]]
    counter = Counter(preds)
    unique = len(counter)
    total = len(preds)
    ratio = unique / total * 100
    top1_freq = counter.most_common(1)[0][1]
    top1_pct = top1_freq / total * 100
    top5_cover = sum(c for _, c in counter.most_common(5)) / total * 100
    print(f"{name:<20} {unique:>14} {total:>14} {ratio:>13.1f}% {top1_freq:>12} {top1_pct:>9.1f}% {top5_cover:>11.1f}%")

# Concentration analysis
print(f"\n  Prediction Concentration (how many unique preds cover 50%/80%/90% of all answers):")
for name in order:
    preds = [r['prediction'].strip() for r in data[name]]
    counter = Counter(preds)
    total = len(preds)
    sorted_counts = sorted(counter.values(), reverse=True)

    cumsum = 0
    c50 = c80 = c90 = 0
    for i, c in enumerate(sorted_counts):
        cumsum += c
        if cumsum >= total * 0.5 and c50 == 0:
            c50 = i + 1
        if cumsum >= total * 0.8 and c80 == 0:
            c80 = i + 1
        if cumsum >= total * 0.9 and c90 == 0:
            c90 = i + 1
            break
    print(f"    {name:<20} 50% covered by {c50:>4} preds, 80% by {c80:>4} preds, 90% by {c90:>4} preds")

# ============================================================
# 11. DIRECTION ACCURACY
# ============================================================
print("\n" + "=" * 100)
print("10. DIRECTION ACCURACY (directional questions only)")
print("=" * 100)

dir_ids = [rid for rid in base_ids if exp05[rid]['spatial_type'] == 'directional']
print(f"\n  Total directional questions: {len(dir_ids)}")

# Analyze reference direction distribution
ref_dirs = Counter()
for rid in dir_ids:
    ref = exp05[rid]['reference']
    ref_clean = ref.replace('方向', '').strip()
    ref_dirs[ref_clean] += 1

print(f"\n  Reference Direction Distribution:")
for d, c in ref_dirs.most_common():
    print(f"    {d}: {c}")

print(f"\n  Direction Accuracy by Model:")
print(f"  {'Model':<20} {'Correct':>10} {'Total':>8} {'Accuracy':>10} {'Wrong Direction':>16} {'No Direction':>14}")
print("  " + "-" * 85)

for name in order:
    correct = 0
    wrong_dir = 0
    no_dir = 0
    total_dir = 0

    for rid in dir_ids:
        r = by_id[name][rid]
        ref = r['reference']
        pred = r['prediction']

        # Check using flexible direction matching
        if direction_match_flexible(pred, ref):
            correct += 1
        else:
            # Check if prediction contains any direction at all
            has_dir = bool(re.search(r'[东南西北东西南北]{1,2}方向?', pred))
            if has_dir:
                wrong_dir += 1
            else:
                no_dir += 1

    total_d = len(dir_ids)
    acc = correct / total_d * 100
    print(f"  {name:<20} {correct:>10} {total_d:>8} {acc:>9.1f}% {wrong_dir:>16} {no_dir:>14}")

# Per-reference-direction accuracy
print(f"\n  Per-Reference-Direction Accuracy:")
eight_dirs = ['东', '南', '西', '北', '东南', '东北', '西南', '西北']

print(f"  {'Ref Direction':<15}", end="")
for name in order:
    short = name.replace("exp05_", "RKL:").replace("exp02_", "FKL:").replace("Baseline_", "BL:").replace("SFT_", "SFT:").replace("Teacher_", "T:")
    print(f" {short:>12}", end="")
print(f" {'Count':>6}")
print("  " + "-""-" * 80)

for d in eight_dirs:
    # Find reference that contains this direction
    d_ids = [rid for rid in dir_ids if d in exp05[rid]['reference'].replace('方向', '')]
    if not d_ids:
        continue
    print(f"  {d+'方向':<15}", end="")
    for name in order:
        correct = sum(1 for rid in d_ids if direction_match_flexible(by_id[name][rid]['prediction'], by_id[name][rid]['reference']))
        acc = correct / len(d_ids) * 100
        print(f" {acc:>11.1f}%", end="")
    print(f" {len(d_ids):>6}")

# ============================================================
# SUMMARY TABLE
# ============================================================
print("\n" + "=" * 100)
print("SUMMARY: KEY METRICS COMPARISON")
print("=" * 100)

print(f"\n{'Metric':<35}", end="")
for name in order:
    short = name.replace("exp05_", "RKL:").replace("exp02_", "FKL:").replace("Baseline_", "BL:").replace("SFT_", "SFT:").replace("Teacher_", "T:")
    print(f" {short:>12}", end="")
print()
print("-" * 100)

# Row 1: Overall accuracy
print(f"{'Overall Accuracy':<35}", end="")
for name in order:
    acc = compute_accuracy(data[name])
    print(f" {acc:>11.3f}", end="")
print()

# Row 2: Unique prediction ratio
print(f"{'Unique Pred Ratio':<35}", end="")
for name in order:
    preds = [r['prediction'].strip() for r in data[name]]
    ratio = len(set(preds)) / len(preds) * 100
    print(f" {ratio:>10.1f}%", end="")
print()

# Row 3: Mean answer length
print(f"{'Mean Answer Length (chars)':<35}", end="")
for name in order:
    lengths = [len(r['prediction']) for r in data[name]]
    print(f" {np.mean(lengths):>11.1f}", end="")
print()

# Row 4: Default answer count
print(f"{'Default Answer Count':<35}", end="")
for name in order:
    preds = [r['prediction'].strip() for r in data[name]]
    any_default = sum(1 for p in preds if any(da in p for da in default_answers))
    print(f" {any_default:>12}", end="")
print()

# Row 5: Top-1 frequency
print(f"{'Top-1 Prediction Freq':<35}", end="")
for name in order:
    preds = [r['prediction'].strip() for r in data[name]]
    counter = Counter(preds)
    top1_pct = counter.most_common(1)[0][1] / len(preds) * 100
    print(f" {top1_pct:>10.1f}%", end="")
print()

# Row 6: Directional accuracy
print(f"{'Directional Accuracy':<35}", end="")
for name in order:
    correct = sum(1 for rid in dir_ids if direction_match_flexible(by_id[name][rid]['prediction'], by_id[name][rid]['reference']))
    acc = correct / len(dir_ids) * 100
    print(f" {acc:>10.1f}%", end="")
print()

# Row 7: exp05 vs exp02 head-to-head
print(f"{'exp05 vs exp02 (05 wins)':<35}", end="")
print(f" {len(exp05_wins):>12}", end="")
print()

print(f"{'exp05 vs exp02 (02 wins)':<35}", end="")
print(f" {'':>12}", end="")
print(f" {len(exp02_wins):>12}", end="")
print()

print("\n" + "=" * 100)
print("ANALYSIS COMPLETE")
print("=" * 100)
