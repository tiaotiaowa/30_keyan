"""
Prompt模板模块
"""

from .inference_prompt import (
    INFERENCE_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
    format_inference_prompt
)

from .eval_prompt import (
    EVAL_PROMPT_TEMPLATE,
    format_eval_prompt
)

__all__ = [
    'INFERENCE_PROMPT_TEMPLATE',
    'SYSTEM_PROMPT',
    'format_inference_prompt',
    'EVAL_PROMPT_TEMPLATE',
    'format_eval_prompt'
]
