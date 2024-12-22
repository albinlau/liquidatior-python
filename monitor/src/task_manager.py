import asyncio
from typing import List
from sqlalchemy.orm import Session

from .tasks.base_task import BaseTask
from .tasks.user_discovery import UserDiscoveryTask
from .tasks.user_update import UserUpdateTask
from .tasks.opportunity_finder import OpportunityFinderTask
from .tasks.liquidation_executor import LiquidationExecutorTask
from .aave_data import AaveDataProvider
from .liquidator import Liquidator
from monitor.config import MONITOR_CONFIG

class TaskManager:
    def __init__(
        self,
        db_session: Session,
        aave_data: AaveDataProvider,
        liquidator: Liquidator
    ):
        self.tasks: List[BaseTask] = []
        self.db = db_session
        self.aave = aave_data
        self.liquidator = liquidator
        
        # 初始化任务
        self._init_tasks()
    
    def _init_tasks(self):
        """初始化所有任务"""
        # 用户发现任务 - 每60分钟执行一次
        user_discovery = UserDiscoveryTask(
            interval=60*60,
            db_session=self.db,
            aave_pool=self.aave.pool
        )
        
        # 用户更新任务 - 每30分钟执行一次
        user_update = UserUpdateTask(
            interval=30*60,
            db_session=self.db,
            aave_data=self.aave
        )
        
        # 清算机会发现任务 - 每1分钟执行一次
        opportunity_finder = OpportunityFinderTask(
            interval=5*60,
            db_session=self.db,
            aave_data=self.aave
        )
        
        # 清算执行任务 - 每1分钟执行一次
        liquidation_executor = LiquidationExecutorTask(
            interval=1*60,
            db_session=self.db,
            liquidator=self.liquidator
        )
        
        self.tasks.extend([
            user_discovery,
            user_update,
            opportunity_finder,
            liquidation_executor
        ])
    
    async def start(self):
        """启动所有任务"""
        print("启动任务管理器...")
        tasks = [asyncio.create_task(task.start()) for task in self.tasks]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            print("正在停止所有任务...")
            for task in self.tasks:
                await task.stop()
    
    async def stop(self):
        """停止所有任务"""
        for task in self.tasks:
            await task.stop() 