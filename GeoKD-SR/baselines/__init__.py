"""
GeoKD-SR Baseline Methods

本模块包含4个核心基线方法用于对比实验:

B1: Direct-SFT    - 直接监督微调，无蒸馏（对照组）
B2: Standard-KD   - Hinton 2015 经典KL蒸馏（Forward KL）
B3: MiniLLM       - Microsoft 2024 逆向KL蒸馏（Reverse KL）
B4: CoT-Distill   - 思维链蒸馏（ACL 2023 Findings）

设计文档: plan/2026-03-01-GeoKD-SR-研究设计方案.md

参考文献:
- Hinton et al. (2015): Distilling the knowledge in a neural network. NeurIPS.
- Gu et al. (2024): MiniLLM: Knowledge Distillation of Large Language Models. ICLR.
- Shridhar et al. (2023): Distilling Reasoning Capabilities into Smaller Language Models. ACL Findings.
"""

from .direct_sft import (
    DirectSFTConfig,
    DirectSFTLoss,
    direct_sft_loss,
)

from .standard_kd import (
    StandardKDConfig,
    StandardKDLoss,
    standard_kd_loss,
)

from .minillm import (
    MiniLLMConfig,
    MiniLLMLoss,
    minillm_loss,
    reverse_kl_loss,
)

from .cot_distill import (
    CoTDistillConfig,
    CoTDistillLoss,
    cot_distill_loss,
)

__all__ = [
    # B1: Direct-SFT
    "DirectSFTConfig",
    "DirectSFTLoss",
    "direct_sft_loss",
    # B2: Standard-KD
    "StandardKDConfig",
    "StandardKDLoss",
    "standard_kd_loss",
    # B3: MiniLLM
    "MiniLLMConfig",
    "MiniLLMLoss",
    "minillm_loss",
    "reverse_kl_loss",
    # B4: CoT-Distill
    "CoTDistillConfig",
    "CoTDistillLoss",
    "cot_distill_loss",
]

# 基线方法注册表
BASELINE_REGISTRY = {
    "direct_sft": {
        "name": "Direct-SFT",
        "description": "直接监督微调，无知识蒸馏",
        "loss_class": DirectSFTLoss,
        "config_class": DirectSFTConfig,
        "reference": "标准监督学习",
        "year": "-",
    },
    "standard_kd": {
        "name": "Standard-KD",
        "description": "Hinton 2015 经典KL蒸馏 (Forward KL)",
        "loss_class": StandardKDLoss,
        "config_class": StandardKDConfig,
        "reference": "Hinton et al. (2015), NeurIPS",
        "year": "2015",
    },
    "minillm": {
        "name": "MiniLLM",
        "description": "Microsoft 2024 逆向KL蒸馏 (Reverse KL)",
        "loss_class": MiniLLMLoss,
        "config_class": MiniLLMConfig,
        "reference": "Gu et al. (2024), ICLR",
        "year": "2024",
    },
    "cot_distill": {
        "name": "CoT-Distill",
        "description": "思维链蒸馏，学习推理过程",
        "loss_class": CoTDistillLoss,
        "config_class": CoTDistillConfig,
        "reference": "Shridhar et al. (2023), ACL Findings",
        "year": "2023",
    },
}


def get_baseline(method_name: str):
    """获取基线方法配置"""
    if method_name not in BASELINE_REGISTRY:
        available = list(BASELINE_REGISTRY.keys())
        raise ValueError(f"未知的基线方法: {method_name}。可用方法: {available}")
    return BASELINE_REGISTRY[method_name]


def list_baselines():
    """列出所有可用的基线方法"""
    print("=" * 60)
    print("GeoKD-SR 可用基线方法")
    print("=" * 60)
    for key, info in BASELINE_REGISTRY.items():
        print(f"\n{key}:")
        print(f"  名称: {info['name']} ({info['year']})")
        print(f"  描述: {info['description']}")
        print(f"  参考: {info['reference']}")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    list_baselines()
