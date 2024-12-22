from typing import Set
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from web3.contract import Contract

from monitor.config.config import AAVE_V3_DEPLOY_BLOCK, BLOCK_CHUNK

from .base_task import BaseTask
from monitor.db.models import User, ScanStatus
from monitor.config import WEB3

# Aave V3 在 Arbitrum 上的部署区块
# 参考: https://docs.aave.com/developers/deployed-contracts/v3-mainnet/arbitrum
# AAVE_V3_DEPLOY_BLOCK = 7742429

class UserDiscoveryTask(BaseTask):
    def __init__(
        self,
        interval: int,
        db_session: Session,
        aave_pool: Contract,
        start_block: int = AAVE_V3_DEPLOY_BLOCK,  # 从 Aave V3 部署开始
        block_chunk: int = BLOCK_CHUNK  # 每次扫描的区块数
    ):
        super().__init__("用户发现", interval)
        self.db = db_session
        self.pool = aave_pool
        self.block_chunk = block_chunk
        
        # 从数据库中获取最后扫描的区块
        scan_status = self.db.query(ScanStatus).first()
        if scan_status:
            self.last_scanned_block = scan_status.last_scanned_block
        else:
            self.last_scanned_block = start_block
            new_scan_status = ScanStatus(last_scanned_block=start_block)
            self.db.add(new_scan_status)
            self.db.commit()
        
    async def execute(self):
        """发现新用户"""
        try:
            while True:
                # 获取当前区块号
                current_block = WEB3.eth.block_number
                
                # 计算本次扫描的区块范围
                from_block = self.last_scanned_block
                to_block = min(from_block + self.block_chunk, current_block)
                
                if from_block >= current_block:
                    print("已扫描到最新区块")
                    self.last_scanned_block = current_block - self.block_chunk  # 回退一段时间以防遗漏
                    break
                
                print(f"扫描区块: {from_block} -> {to_block}")
                
                # 获取所有用户地址
                supply_events = self.pool.events.Supply().get_logs(
                    from_block=from_block,
                    to_block=to_block
                )
                
                # 收集用户地址
                users: Set[str] = set()
                for event in supply_events:
                    users.add(event.args.user)
                
                # 添加新用户到数据库
                added_count = 0
                for address in users:
                    user = self.db.query(User).filter_by(address=address).first()
                    if not user:
                        user = User(address=address)
                        self.db.add(user)
                        added_count += 1
                        
                        # 每10个用户提交一次
                        if added_count % 10 == 0:
                            self.db.commit()
                
                # 更新最后扫描的区块
                self.last_scanned_block = to_block + 1
                scan_status = self.db.query(ScanStatus).first()
                if scan_status:
                    scan_status.last_scanned_block = self.last_scanned_block
                else:
                    scan_status = ScanStatus(last_scanned_block=self.last_scanned_block)
                    self.db.add(scan_status)
                self.db.commit()
                
                if added_count > 0:
                    print(f"发现了 {added_count} 个新用户")
                
                if from_block + self.block_chunk >= current_block:
                    print("已扫描到最新区块")
                    break

        except Exception as e:
            print(f"用户发现任务出错: {str(e)}")
            # 确保发生错误时也提交已有的更改
            self.db.commit()