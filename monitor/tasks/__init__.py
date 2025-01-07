"""
任务模块

包含：
- 用户发现任务
- 用户更新任务
- 清算机会发现任务
- 清算执行任务
"""

from .base_task import BaseTask
from .user_discovery import UserDiscoveryTask
from .user_update import UserUpdateTask
from .opportunity_finder import OpportunityFinderTask
from .liquidation_executor import LiquidationExecutorTask
from .task_manager import TaskManager

__all__ = [
    'BaseTask',
    'UserDiscoveryTask',
    'UserUpdateTask',
    'OpportunityFinderTask',
    'LiquidationExecutorTask',
    'TaskManager'
] 