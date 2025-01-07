# 标准库
import asyncio
from datetime import datetime, timezone
from typing import Optional

class BaseTask:
    def __init__(self, name: str, interval: int):
        self.name = name
        self.interval = interval
        self.last_run: Optional[datetime] = None
        self._running = False
        
    async def start(self):
        """启动任务"""
        self._running = True
        while self._running:
            try:
                self.last_run = datetime.now(timezone.utc)
                await self.execute()
            except Exception as e:
                print(f"{self.name} 任务执行出错: {str(e)}")
            finally:
                await asyncio.sleep(self.interval)
    
    async def stop(self):
        """停止任务"""
        self._running = False
    
    async def execute(self):
        """执行任务，需要子类实现"""
        raise NotImplementedError() 