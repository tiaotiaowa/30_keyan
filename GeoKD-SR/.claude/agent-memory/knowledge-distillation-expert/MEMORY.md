# Knowledge Distillation Expert - Agent Memory

## Project: GeoKD-SR

### Key Technical Facts
- Teacher: Qwen2.5-7B-Instruct (4-bit NF4 quantization)
- Student: Qwen2.5-1.5B-Instruct (LoRA r=16, alpha=32)
- Dataset: ~9463 train / 1124 dev / 1183 test, geo-spatial reasoning QA
- Baseline accuracy: 23.16% (no fine-tuning), 22.06% (SFT failed)
- KD success threshold: Overall Acc > 25%

### Exp02 Standard-KD Design
- Method: Hinton 2015 Forward KL, L = 0.5 * KL(P_T||P_S) * T^2 + 0.5 * CE
- Temperature T=2.0, alpha=0.5
- A10 24GB, batch=2, grad_accum=64, effective_batch=128
- bf16, gradient_checkpointing=True

### Code Review Findings (2026-03-29)
- KL divergence direction: verified correct (F.kl_div computes KL(target||input))
- T^2 scaling: correctly applied
- valid_mask: correctly aligned, only response tokens
- Minor: teacher uses float16 but training uses bf16 (low severity)
- Minor: save_steps=200 is sparse for ~222 total steps (low severity)

### Files
- [Code review notes](exp02-code-review.md)
