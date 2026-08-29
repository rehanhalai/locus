"""Core shared utilities and configuration."""

from app.core.config import settings
from app.core.task_manager import TaskManager, task_manager

__all__ = ["TaskManager", "settings", "task_manager"]
