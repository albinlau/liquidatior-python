# 标准库
import os
from datetime import datetime
from typing import List, Dict, Optional

# 第三方库
from sqlalchemy.orm import Session
from web3 import Web3
from eth_account import Account
from eth_account.signers.local import LocalAccount

# 本地导入
from .base_task import BaseTask
from ..db.models import LiquidationOpportunity
from ..config import MONITOR_CONFIG
from ..utils.aave_data import AaveDataProvider

class LiquidationExecutorTask(BaseTask):
    def __init__(
        self,
        interval: int,
        db_session: Session,
        web3: Web3,
        private_key: str,
        liquidator_address: str,
        min_profit_eth: float
    ):
        super().__init__("清算执行", interval)
        self.db = db_session
        self.web3 = web3
        self.account: LocalAccount = Account.from_key(private_key)
        self.contract = AaveDataProvider._load_contract(web3, liquidator_address, 'Liquidator.json')
        self.min_profit_eth = min_profit_eth
        
    def check_gas_price(self, max_gas_price_gwei: int) -> bool:
        """检查 gas 价格是否在可接受范围内"""
        current_gas_price = self.web3.eth.gas_price
        return current_gas_price <= Web3.to_wei(max_gas_price_gwei, 'gwei')
    
    async def execute_liquidation(
        self,
        user: str,
        debt_token: str,
        coll_token: str,
        debt_amount: int,
        uniswap_pool: str,
        gas_price: Optional[int] = None
    ) -> Optional[str]:
        """执行清算"""
        try:
            # 构建交易
            tx = self.contract.functions.liquidate(
                user,
                debt_token,
                coll_token,
                debt_amount,
                uniswap_pool
            ).build_transaction({
                'from': self.account.address,
                'gas': 2000000,  # 预估 gas
                'gasPrice': gas_price if gas_price else self.web3.eth.gas_price,
                'nonce': self.web3.eth.get_transaction_count(self.account.address)
            })
            
            # 签名交易
            signed_tx = self.account.sign_transaction(tx)
            
            # 发送交易
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # 等待交易确认
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt['status'] == 1:
                return self.web3.to_hex(tx_hash)
            return None
            
        except Exception as e:
            print(f"清算执行失败: {str(e)}")
            return None
        
    async def execute(self):
        """执行清算任务"""
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
                if not self.check_gas_price(MONITOR_CONFIG['max_gas_price']):
                    print(f"Gas 价格过高，暂停清算")
                    break
                
                # 获取用户地址
                user = opp.user
                
                # 执行清算
                # 查找最佳 Uniswap 池子
                uniswap_pool = await self.aave.find_best_pool(
                    opp.debt_token,
                    opp.collateral_token
                )
                
                if not uniswap_pool:
                    print(f"未找到合适的 Uniswap 池子，跳过清算")
                    continue
                
                tx_hash = await self.execute_liquidation(
                    user.address,
                    opp.debt_token,
                    opp.collateral_token,
                    int(opp.debt_amount * 1e18),
                    uniswap_pool
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