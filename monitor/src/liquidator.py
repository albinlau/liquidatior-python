from web3 import Web3
from typing import Dict, Optional
import json
import os
from eth_account import Account
from eth_account.signers.local import LocalAccount

class Liquidator:
    def __init__(
        self,
        web3: Web3,
        private_key: str,
        liquidator_address: str,
        min_profit_eth: float
    ):
        self.web3 = web3
        self.account: LocalAccount = Account.from_key(private_key)
        self.contract = self._load_contract(liquidator_address, 'Liquidator.json')
        self.min_profit_eth = min_profit_eth
        
    def _load_contract(self, address: str, abi_file: str) -> object:
        """加载合约"""
        abi_path = os.path.join(os.path.dirname(__file__), '..\\abi', abi_file)
        with open(abi_path) as f:
            contract_json = json.load(f)
            # 直接获取 abi 数组
            if isinstance(contract_json, dict):
                abi = contract_json['abi']
            else:
                abi = contract_json
                
            # 确保 abi 是一个列表
            if not isinstance(abi, list):
                raise ValueError(f"Invalid ABI format in {abi_file}. Expected list, got {type(abi)}")
                
            # 确保 abi 是一个普通的 Python 列表，而不是嵌套的字典
            if isinstance(abi, list) and len(abi) == 1 and isinstance(abi[0], dict) and 'abi' in abi[0]:
                abi = abi[0]['abi']
        
        return self.web3.eth.contract(address=address, abi=abi)
    
    def execute_liquidation(
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
    
    def check_gas_price(self, max_gas_price_gwei: int) -> bool:
        """检查 gas 价格是否在可接受范围内"""
        current_gas_price = self.web3.eth.gas_price
        return current_gas_price <= Web3.to_wei(max_gas_price_gwei, 'gwei')
    
    def estimate_gas(
        self,
        user: str,
        debt_token: str,
        coll_token: str,
        debt_amount: int,
        uniswap_pool: str
    ) -> int:
        """估算 gas 消耗"""
        try:
            gas = self.contract.functions.liquidate(
                user,
                debt_token,
                coll_token,
                debt_amount,
                uniswap_pool
            ).estimate_gas({
                'from': self.account.address
            })
            return gas
        except Exception as e:
            print(f"Gas 估算失败: {str(e)}")
            return 0 