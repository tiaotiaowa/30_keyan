---
name: exp02-code-review
description: Exp02 Standard-KD code review findings and technical notes
type: reference
---

# Exp02 Standard-KD Code Review

## PyTorch F.kl_div Direction Convention

`F.kl_div(input, target)` computes `target * (log(target) - input)`:
- `input` must be log-probabilities (student)
- `target` must be probabilities (teacher)
- Result is KL(target || input) = KL(P_T || P_S) -- Forward KL

## Key Implementation Pattern

```python
p_teacher = F.softmax(teacher_logits / T, dim=-1)
log_p_student = F.log_softmax(student_logits / T, dim=-1)
kl_loss = F.kl_div(log_p_student, p_teacher, reduction='batchmean')
return kl_loss * (T ** 2)
```

## valid_mask Alignment

When using shifted logits for causal LM:
- `labels[..., 1:]` aligns with `logits[..., :-1, :]`
- `valid_mask = labels[..., 1:] != -100` selects response tokens only
- Both soft_loss and hard_loss compute on identical valid positions

## Mixed Precision Note

If teacher uses 4-bit quantization with float16 compute, and student training uses bf16:
- Logits will be in teacher's dtype, then auto-cast to training dtype
- Recommend unifying to bfloat16 for consistency
