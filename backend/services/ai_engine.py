"""
ALIS-X AI Engine — Compatibility Shim
======================================
The monolithic ai_engine has been replaced by the modular ai_services package.
This file is kept for backward compatibility with any existing imports.

All calls are delegated to the new orchestrator.
Do not add new logic here — use ai_services directly.
"""
from ai_services.schemas import AILayer, TaskType
from ai_services.orchestrator import (
    interpret_result,
    analyze_panel,
    check_epidemic,
)
from ai_services.local_llm import cache_stats, is_available as _ollama_up
from ai_services.cloud_llm import is_available as _cloud_up

__all__ = [
    'TaskType', 'AILayer',
    'interpret_result', 'analyze_panel', 'check_epidemic',
    'cache_stats', '_ollama_up', '_cloud_up',
]
