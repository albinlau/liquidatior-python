# 标准库
import os
import asyncio
from typing import List

# 第三方库
from sqlalchemy.orm import Session

# 本地导入
from .base_task import BaseTask
from .user_discovery import UserDiscoveryTask
from .user_update import UserUpdateTask
from .opportunity_finder import OpportunityFinderTask
from .liquidation_executor import LiquidationExecutorTask
from ..utils.aave_data import AaveDataProvider
from ..config import MONITOR_CONFIG, CONTRACTS, WEB3

class TaskManager:
    def __init__(
        self,
        db_session: Session,
        aave_data: AaveDataProvider,
    ):
        self.tasks: List[BaseTask] = []
        self.db = db_session
        self.aave = aave_data
        
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
        
        # 清算机会发现任务 - 每5分钟执行一次
        opportunity_finder = OpportunityFinderTask(
            interval=5*60,
            db_session=self.db,
            aave_data=self.aave
        )
        
        # 清算执行任务 - 每1分钟执行一次
        liquidation_executor = LiquidationExecutorTask(
            interval=1*60,
            db_session=self.db,
            web3=WEB3,
            private_key=os.getenv('PRIVATE_KEY'),
            liquidator_address=CONTRACTS['LIQUIDATOR'],
            min_profit_eth=MONITOR_CONFIG['min_profit']
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