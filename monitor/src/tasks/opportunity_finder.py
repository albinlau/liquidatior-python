from datetime import datetime
from typing import List, Dict
from sqlalchemy.orm import Session

from .base_task import BaseTask
from monitor.db.models import User, Position, LiquidationOpportunity
from ..aave_data import AaveDataProvider
from monitor.config import MONITOR_CONFIG

class OpportunityFinderTask(BaseTask):
    def __init__(
        self,
        interval: int,
        db_session: Session,
        aave_data: AaveDataProvider
    ):
        super().__init__("清算机会发现", interval)
        self.db = db_session
        self.aave = aave_data
        
    async def execute(self):
        """查找清算机会"""
        opportunities = []
        
        # 查找健康因子低于阈值的用户
        users = self.db.query(User).filter(
            User.health_factor < MONITOR_CONFIG['min_health_factor']
        ).all()
        
        found_count = 0
        for user in users:
            try:
                # 检查每个头寸
                positions = self.db.query(Position).filter_by(user_id=user.id).all()
                for position in positions:
                    if position.debt_amount > 0:  # 如果有债务
                        # 计算清算利润
                        profit, is_profitable = await self.aave.calculate_liquidation_profit(
                            position.token_address,
                            position.token_address,
                            int(position.debt_amount * 1e18),
                            user.address
                        )
                        
                        if is_profitable and profit >= MONITOR_CONFIG['min_profit']:
                            # 检查是否已存在相同的未执行机会
                            existing = self.db.query(LiquidationOpportunity).filter_by(
                                user_id=user.id,
                                collateral_token=position.token_address,
                                debt_token=position.token_address,
                                executed=False
                            ).first()
                            
                            if not existing:
                                opportunity = LiquidationOpportunity(
                                    user_id=user.id,
                                    collateral_token=position.token_address,
                                    debt_token=position.token_address,
                                    collateral_amount=position.collateral_amount,
                                    debt_amount=position.debt_amount,
                                    health_factor=user.health_factor,
                                    estimated_profit_eth=profit,
                                    is_profitable=True
                                )
                                self.db.add(opportunity)
                                found_count += 1
                                
                                opportunities.append({
                                    'user': user.address,
                                    'collateral_token': position.token_address,
                                    'debt_token': position.token_address,
                                    'debt_amount': position.debt_amount,
                                    'estimated_profit': profit
                                })
                
            except Exception as e:
                print(f"处理用户 {user.address} 的清算机会时出错: {str(e)}")
        
        self.db.commit()
        
        if found_count > 0:
            print(f"发现 {found_count} 个新的清算机会") 