from datetime import datetime
from typing import List
from sqlalchemy.orm import Session

from monitor.db.models import LiquidationOpportunity
from monitor.src.liquidator import Liquidator
from monitor.config import MONITOR_CONFIG
from .base_task import BaseTask

class LiquidationExecutorTask(BaseTask):
    def __init__(
        self,
        interval: int,
        db_session: Session,
        liquidator: Liquidator
    ):
        super().__init__("清算执行", interval)
        self.db = db_session
        self.liquidator = liquidator
        
    async def execute(self):
        """执行清算"""
        # 获取未执行的清算机会
        opportunities = self.db.query(LiquidationOpportunity).filter_by(
            executed=False,
            is_profitable=True
        ).order_by(
            LiquidationOpportunity.estimated_profit_eth.desc()
        ).all()
        
        executed_count = 0
        for opp in opportunities:
            try:
                # 检查 gas 价格
                if not self.liquidator.check_gas_price(MONITOR_CONFIG['max_gas_price']):
                    print(f"Gas 价格过高，暂停清算")
                    break
                
                # 获取用户地址
                user = opp.user
                
                # 执行清算
                tx_hash = await self.liquidator.execute_liquidation(
                    user.address,
                    opp.debt_token,
                    opp.collateral_token,
                    int(opp.debt_amount * 1e18),
                    None  # Uniswap pool 地址将由合约自动选择
                )
                
                if tx_hash:
                    print(f"清算成功: {tx_hash}")
                    opp.executed = True
                    opp.execution_tx = tx_hash
                    executed_count += 1
                    
                    # 每次执行成功后提交
                    self.db.commit()
                
            except Exception as e:
                print(f"执行清算失败: {str(e)}")
        
        if executed_count > 0:
            print(f"成功执行了 {executed_count} 笔清算") 