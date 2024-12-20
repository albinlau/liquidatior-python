from typing import List, Dict
import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from web3 import Web3

from .aave_data import AaveDataProvider
from .liquidator import Liquidator
from ..db.models import User, Position, LiquidationOpportunity, TokenPrice
from ..config.config import MONITOR_CONFIG, CONTRACTS, DB_CONFIG

class LiquidationMonitor:
    def __init__(
        self,
        web3: Web3,
        db_session: Session,
        aave_data_provider: AaveDataProvider,
        liquidator: Liquidator
    ):
        self.web3 = web3
        self.db = db_session
        self.aave = aave_data_provider
        self.liquidator = liquidator
        
    def update_user_data(self, user_address: str) -> User:
        """更新用户数据"""
        user_data = self.aave.get_user_data(user_address)
        
        user = self.db.query(User).filter_by(address=user_address).first()
        if not user:
            user = User(address=user_address)
            self.db.add(user)
        
        user.health_factor = user_data['health_factor'] / 1e18
        user.total_collateral_eth = user_data['total_collateral_eth'] / 1e18
        user.total_debt_eth = user_data['total_debt_eth'] / 1e18
        user.last_updated = datetime.now(timezone.utc)
        
        # 更新用户头寸
        positions = self.aave.get_user_positions(user_address)
        for pos_data in positions:
            position = self.db.query(Position).filter_by(
                user_id=user.id,
                token_address=pos_data['token_address']
            ).first()
            
            if not position:
                position = Position(user_id=user.id)
                self.db.add(position)
            
            position.token_address = pos_data['token_address']
            position.collateral_amount = pos_data['collateral_amount'] / 1e18
            position.debt_amount = pos_data['debt_amount'] / 1e18
            position.last_updated = datetime.now(timezone.utc)
        
        self.db.commit()
        return user
    
    def find_liquidation_opportunities(self) -> List[Dict]:
        """查找清算机会"""
        opportunities = []
        
        # 查找健康因子低于阈值的用户
        users = self.db.query(User).filter(
            User.health_factor < MONITOR_CONFIG['min_health_factor']
        ).all()
        
        for user in users:
            # 获取用户最新数据
            updated_user = self.update_user_data(user.address)
            
            # 再次检查健康因子
            if updated_user.health_factor >= MONITOR_CONFIG['min_health_factor']:
                continue
            
            # 检查每个头寸
            for position in updated_user.positions:
                if position.debt_amount > 0:  # 如果有债务
                    # 计算清算利润
                    profit, is_profitable = self.aave.calculate_liquidation_profit(
                        position.token_address,
                        position.token_address,
                        int(position.debt_amount * 1e18),
                        user.address
                    )
                    
                    if is_profitable and profit >= MONITOR_CONFIG['min_profit']:
                        opportunity = LiquidationOpportunity(
                            user_id=user.id,
                            collateral_token=position.token_address,
                            debt_token=position.token_address,
                            collateral_amount=position.collateral_amount,
                            debt_amount=position.debt_amount,
                            health_factor=updated_user.health_factor,
                            estimated_profit_eth=profit,
                            is_profitable=True
                        )
                        self.db.add(opportunity)
                        
                        opportunities.append({
                            'user': user.address,
                            'collateral_token': position.token_address,
                            'debt_token': position.token_address,
                            'debt_amount': position.debt_amount,
                            'estimated_profit': profit
                        })
        
        self.db.commit()
        return opportunities
    
    def execute_liquidations(self, opportunities: List[Dict]) -> None:
        """执行清算"""
        for opp in opportunities:
            # 检查 gas 价格
            if not self.liquidator.check_gas_price(MONITOR_CONFIG['max_gas_price']):
                print(f"Gas 价格过高，跳过清算")
                continue
            
            # 执行清算
            tx_hash = self.liquidator.execute_liquidation(
                opp['user'],
                opp['debt_token'],
                opp['collateral_token'],
                int(opp['debt_amount'] * 1e18),
                None  # Uniswap pool 地址将由合约自动选择
            )
            
            if tx_hash:
                print(f"清算成功: {tx_hash}")
                # 更新数据库
                opportunity = self.db.query(LiquidationOpportunity).filter_by(
                    user_id=opp['user'],
                    debt_token=opp['debt_token']
                ).first()
                
                if opportunity:
                    opportunity.executed = True
                    opportunity.execution_tx = tx_hash
                    self.db.commit()
    
    def run(self) -> None:
        """运行监控程序"""
        print("开始监控清算机会...")
        
        while True:
            try:
                # 1. 更新所有用户数据
                users = self.aave.get_all_users()
                for user_address in users:
                    self.update_user_data(user_address)
                
                # 2. 查找清算机会
                opportunities = self.find_liquidation_opportunities()
                
                # 3. 执行清算
                if opportunities:
                    print(f"发现 {len(opportunities)} 个清算机会")
                    self.execute_liquidations(opportunities)
                
                # 等待下一个扫描周期
                time.sleep(MONITOR_CONFIG['interval'])
                
            except Exception as e:
                print(f"监控过程出错: {str(e)}")
                time.sleep(5)  # 出错后等待一段时间再重试 