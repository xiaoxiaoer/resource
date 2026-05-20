"""程序化校验引擎。

入口：
    from web.services.validators import run_validation, render_markdown
"""

from web.services.validators.core import (
    CheckItem,
    ValidationResult,
    STATUS_ICON,
    run_validation,
)
from web.services.validators.markdown_renderer import render_markdown

__all__ = [
    'CheckItem',
    'ValidationResult',
    'STATUS_ICON',
    'run_validation',
    'render_markdown',
]
