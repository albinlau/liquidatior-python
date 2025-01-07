# 标准库
from datetime import datetime
from typing import List, Dict

# 第三方库
from sqlalchemy.orm import Session

# 本地导入
from .base_task import BaseTask
from ..db.models import User, Position, LiquidationOpportunity
from ..utils.aave_data import AaveDataProvider
from ..config import MONITOR_CONFIG, CONTRACTS

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
        
        # 获取 ETH 价格
        eth_price = await self.aave.get_asset_price(CONTRACTS['WETH'])
        if not eth_price:
            print("无法获取 ETH 价格")
            return
            
        # 查找健康因子低于阈值的用户
        users = self.db.query(User).filter(
            User.health_factor < MONITOR_CONFIG['min_health_factor']
        ).all()
        
        found_count = 0
        for user in users:
            try:
                # 获取用户的所有头寸
                collateral_positions = self.db.query(Position).filter(
                    Position.user_id == user.id,
                    Position.collateral_amount > 0
                ).all()
                
                debt_positions = self.db.query(Position).filter(
                    Position.user_id == user.id,
                    Position.debt_amount > 0
                ).all()
                
                # 检查每个抵押品和债务组合
                for debt_pos in debt_positions:
                    for coll_pos in collateral_positions:
                        # 计算清算利润（USD）
                        profit_usd, is_profitable = await self.aave.calculate_liquidation_profit(
                            coll_pos.token_address,  # 抵押品代币
                            debt_pos.token_address,  # 债务代币
                            int(debt_pos.debt_amount * 1e18)  # 债务金额
                        )
                        
                        # 将 USD 利润转换为 ETH
                        profit_eth = profit_usd / eth_price
                        
                        if is_profitable and profit_eth >= MONITOR_CONFIG['min_profit']:
                            # 检查是否已存在相同的未执行机会
                            existing = self.db.query(LiquidationOpportunity).filter_by(
                                user_id=user.id,
                                collateral_token=coll_pos.token_address,
                                debt_token=debt_pos.token_address,
                                executed=False
                            ).first()
                            
                            if not existing:
                                opportunity = LiquidationOpportunity(
                                    user_id=user.id,
                                    collateral_token=coll_pos.token_address,
                                    debt_token=debt_pos.token_address,
                                    collateral_amount=coll_pos.collateral_amount,
                                    debt_amount=debt_pos.debt_amount,
                                    health_factor=user.health_factor,
                                    estimated_profit_eth=profit_eth,
                                    is_profitable=True
                                )
                                self.db.add(opportunity)
                                found_count += 1
                                
                                opportunities.append({
                                    'user': user.address,
                                    'collateral_token': coll_pos.token_address,
                                    'debt_token': debt_pos.token_address,
                                    'debt_amount': debt_pos.debt_amount,
                                    'estimated_profit': profit_eth
                                })
                
            except Exception as e:
                print(f"处理用户 {user.address} 的清算机会时出错: {str(e)}")
        
        self.db.commit()
        
        if found_count > 0:
            print(f"发现 {found_count} 个新的清算机会") 