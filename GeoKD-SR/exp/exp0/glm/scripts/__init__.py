"""
GLM-4.7 评测脚本模块
"""

from .glm47_client import GLM47Client
from .evaluate_glm47 import (
    load_test_data,
    run_inference,
    calculate_all_metrics,
    generate_report
)

__all__ = [
    'GLM47Client',
    'load_test_data',
    'run_inference',
    'calculate_all_metrics',
    'generate_report'
]
