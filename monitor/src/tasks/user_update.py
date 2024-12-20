from datetime import datetime, timedelta, timezone
from typing import List
from sqlalchemy.orm import Session
from web3.contract import Contract

from .base_task import BaseTask
from monitor.db.models import User, Position
from ..aave_data import AaveDataProvider

class UserUpdateTask(BaseTask):
    def __init__(
        self,
        interval: int,
        db_session: Session,
        aave_data: AaveDataProvider,
        update_interval: int = 300  # 5分钟更新一次
    ):
        super().__init__("用户更新", interval)
        self.db = db_session
        self.aave = aave_data
        self.update_interval = update_interval
        
    async def execute(self):
        """更新用户数据"""
        # 获取需要更新的用户
        update_before = datetime.now(timezone.utc) - timedelta(seconds=self.update_interval)
        users: List[User] = self.db.query(User).filter(
            User.last_updated < update_before
        ).all()
        
        updated_count = 0
        for user in users:
            try:
                # 获取用户数据
                user_data = await self.aave.get_user_data(user.address)
                if not user_data:
                    print(f"无法获取用户 {user.address} 的数据")
                    continue
                
                # 更新用户数据
                try:
                    user.health_factor = int(user_data['health_factor']) / 1e18
                    user.total_collateral_eth = int(user_data['total_collateral_eth']) / 1e18
                    user.total_debt_eth = int(user_data['total_debt_eth']) / 1e18
                    user.last_updated = datetime.now(timezone.utc)
                except (TypeError, ValueError) as e:
                    print(f"转换用户 {user.address} 数据时出错: {str(e)}")
                    continue
                
                # 更新用户头寸
                positions = await self.aave.get_user_positions(user.address)
                for pos_data in positions:
                    try:
                        position = self.db.query(Position).filter_by(
                            user_id=user.id,
                            token_address=pos_data['token_address']
                        ).first()
                        
                        if not position:
                            position = Position(user_id=user.id)
                            self.db.add(position)
                        
                        position.token_address = pos_data['token_address']
                        position.collateral_amount = int(pos_data['collateral_amount']) / 1e18
                        position.debt_amount = int(pos_data['debt_amount']) / 1e18
                        position.last_updated = datetime.now(timezone.utc)
                    except (TypeError, ValueError) as e:
                        print(f"转换头寸数据时出错: {str(e)}")
                        continue
                
                updated_count += 1
                
                # 每10个用户提交一次
                if updated_count % 10 == 0:
                    self.db.commit()
                    
            except Exception as e:
                print(f"更新用户 {user.address} 数据失败: {str(e)}")
                continue
        
        # 最后提交
        self.db.commit()
        
        if updated_count > 0:
            print(f"更新了 {updated_count} 个用户的数据") 