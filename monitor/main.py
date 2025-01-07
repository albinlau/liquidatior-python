import os
import asyncio
import signal
from datetime import timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from monitor.tasks.task_manager import TaskManager
from monitor.utils.aave_data import AaveDataProvider
from monitor.config import WEB3, CONTRACTS, DB_CONFIG, MONITOR_CONFIG
from monitor.db.models import init_db

async def cleanup():
    # 等待所有任务完成
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()

async def main():
    # 加载环境变量
    load_dotenv()
    
    # 初始化数据库
    db_url = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
    engine = init_db(db_url)
    Session = sessionmaker(bind=engine)
    db_session = Session()
    
    # 初始化 Aave 数据提供者
    aave_data_provider = AaveDataProvider(
        WEB3,
        CONTRACTS['AAVE_POOL'],
        CONTRACTS['AAVE_POOL_DATA_PROVIDER']
    )
    
    # 初始化任务管理器
    task_manager = TaskManager(
        db_session,
        aave_data_provider,
    )
    
    def signal_handler(signum, frame):
        print("收到退出信号，正在清理...")
        asyncio.create_task(cleanup())
    
    # 替换 loop.add_signal_handler 的实现
    if os.name == 'posix':  # Unix/Linux/Mac
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)
    else:  # Windows
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        print("启动监控程序...")
        await task_manager.start()
    except asyncio.CancelledError:
        print("程序被取消")
    finally:
        db_session.close()
        engine.dispose()

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close() 