from web3 import Web3
from typing import List, Dict, Tuple
import json
import os
from datetime import datetime

class AaveDataProvider:
    def __init__(self, web3: Web3, pool_address: str, data_provider_address: str):
        self.web3 = web3
        self.pool = self._load_contract(pool_address, 'AavePool.json')
        self.data_provider = self._load_contract(data_provider_address, 'AaveDataProvider.json')
        
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
    
    async def get_user_data(self, user_address: str) -> Dict:
        """获取用户数据"""
        try:
            # 调用合约方法
            values = self.pool.functions.getUserAccountData(user_address).call()
            
            # # 构建调用数据
            # call_data = func.buildTransaction({})['data']
            
            # # 构建交易对象
            # tx = {
            #     'to': self.pool.address,
            #     'data': call_data,
            #     # 使用零地址作为调用者，因为这是只读操作
            #     'from': '0x0000000000000000000000000000000000000000'
            # }
            
            # # 调用合约并获取原始数据
            # raw_data = await self.web3.eth.call(tx)
            
            if not values or len(values) < 6:  # 6 * 32 bytes
                print(f"获取用户 {user_address} 数据返回值长度不足: {len(values) if values else 0} bytes")
                return None
            
            try:
                # # 手动解码返回值
                # values = []
                # for i in range(0, len(raw_data), 32):
                #     value = int.from_bytes(raw_data[i:i+32], byteorder='big')
                #     values.append(value)
                
                # if len(values) < 6:
                #     print(f"解码后的数据项数量不足: {len(values)}")
                #     return None
                
                return {
                    'total_collateral_eth': values[0],
                    'total_debt_eth': values[1],
                    'available_borrow_eth': values[2],
                    'current_liquidation_threshold': values[3],
                    'ltv': values[4],
                    'health_factor': values[5]
                }
            except Exception as e:
                print(f"解码用户 {user_address} 数据时出错: {str(e)}")
                print(f"原始数据: {values}")
                return None
                
        except Exception as e:
            print(f"调用合约获取用户 {user_address} 数据时出错: {str(e)}")
            if hasattr(e, 'args') and len(e.args) > 0:
                print(f"错误详情: {e.args[0]}")
            return None
    
    async def get_user_positions(self, user_address: str) -> List[Dict]:
        """获取用户所有头寸"""
        positions = []
        
        try:
            # 获取所有代币列表
            raw_data = self.pool.functions.getReservesList().call()
            # call_data = func.encode_input()
            # tx = {
            #     'to': self.pool.address,
            #     'data': call_data,
            #     'from': '0x0000000000000000000000000000000000000000'
            # }
            # raw_data = await self.web3.eth.call(tx)
            
            # 解码返回值
            # reserves_list = self.web3.codec.decode_abi(['address[]'], raw_data)[0]
            reserves_list = raw_data
            
            for token in reserves_list:
                try:
                    # 获取用户在该代币上的数据
                    raw_data = self.data_provider.functions.getUserReserveData(token, user_address).call()
                    # call_data = func.encode_input()
                    # tx = {
                    #     'to': self.data_provider.address,
                    #     'data': call_data,
                    #     'from': '0x0000000000000000000000000000000000000000'
                    # }
                    # raw_data = await self.web3.eth.call(tx)
                    
                    # 解码返回值
                    # output_types = [
                    #     'uint256',  # currentATokenBalance
                    #     'uint256',  # currentStableDebt
                    #     'uint256',  # currentVariableDebt
                    #     'uint256',  # principalStableDebt
                    #     'uint256',  # scaledVariableDebt
                    #     'uint256',  # stableBorrowRate
                    #     'uint256',  # liquidityRate
                    #     'uint40',   # stableRateLastUpdated
                    #     'bool',     # usageAsCollateralEnabled
                    # ]
                    # decoded = self.web3.codec.decode_abi(output_types, raw_data)
                    # decoded = raw_data
                    
                    # if decoded[0] > 0 or decoded[1] > 0 or decoded[2] > 0:  # 如果有存款或借款
                    #     # 获取代币配置
                    #     raw_data = self.data_provider.functions.getReserveConfigurationData(token).call()
                    #     # call_data = func.encode_input()
                    #     # tx = {
                    #     #     'to': self.data_provider.address,
                    #     #     'data': call_data,
                    #     #     'from': '0x0000000000000000000000000000000000000000'
                    #     # }
                    #     # raw_data = await self.web3.eth.call(tx)
                        
                    #     # # 解码返回值
                    #     # config_data = int.from_bytes(raw_data[:32], byteorder='big')
                    #     config_data = raw_data
                        
                    #     positions.append({
                    #         'token_address': token,
                    #         'collateral_amount': decoded[0],
                    #         'debt_amount': decoded[1] + decoded[2],  # stableDebt + variableDebt
                    #         'borrowing_enabled': config_data[6],  # 这个信息在其他位置
                    #         'ltv': config_data[1],
                    #         'liquidation_threshold': config_data[2],
                    #         'liquidation_bonus': config_data[3]
                    #     })
                    positions.append({
                        'token_address': token,
                        'collateral_amount': raw_data[0],
                        'debt_amount': raw_data[1] + raw_data[2],  # stableDebt + variableDebt
                    })
                except Exception as e:
                    print(f"处理代币 {token} 数据时出错: {str(e)}")
                    continue
            
            return positions
        except Exception as e:
            print(f"获取用户 {user_address} 头寸数据时出错: {str(e)}")
            return []
    
    async def get_all_users(self) -> List[str]:
        """获取所有用户地址"""
        # 通过事件过滤获取所有用户
        supply_filter = self.pool.events.Supply().get_logs(
            from_block=self.web3.eth.block_number - 1000,
            to_block='latest'
        )
        borrow_filter = self.pool.events.Borrow().get_logs(
            from_block=self.web3.eth.block_number - 1000,
            to_block='latest'
        )
        
        users = set()
        for event in supply_filter + borrow_filter:
            users.add(event.args.user)
        
        return list(users)
    
    async def get_token_data(self, token_address: str) -> Dict:
        """获取代币数据"""
        token_decoded = self.data_provider.functions.getReserveData(token_address).call()
        
        config_decoded = self.data_provider.functions.getReserveConfigurationData(token_address).call()
        
        # # 解码返回值
        # token_types = ['uint256', 'uint256']
        # config_types = ['uint256', 'uint256', 'uint256', 'uint256', 'uint256', 'uint256']
        
        # token_decoded = self.web3.codec.decode_abi(token_types, token_data)
        # config_decoded = self.web3.codec.decode_abi(config_types, config_data)
        
        return {
            'liquidity': token_decoded[0],
            'utilization_rate': token_decoded[1],
            'borrowing_enabled': config_decoded[1],
            'ltv': config_decoded[2],
            'liquidation_threshold': config_decoded[3],
            'liquidation_bonus': config_decoded[4],
            'decimals': config_decoded[0]
        }
    
    async def calculate_liquidation_profit(
        self,
        collateral_token: str,
        debt_token: str,
        debt_amount: int
    ) -> Tuple[float, bool]:
        """计算清算利润"""
        # 获取清算奖励
        raw_data = self.data_provider.functions.getReserveConfigurationData(collateral_token).call()
        # token_data = await self.web3.eth.call(func._build_transaction({
        #     'from': self.web3.eth.default_account or self.web3.eth.accounts[0]
        # }))
        # config_types = ['uint256', 'uint256', 'uint256', 'uint256', 'uint256', 'uint256']
        # config_decoded = self.web3.codec.decode_abi(config_types, token_data)
        config_decoded = raw_data
        liquidation_bonus = config_decoded[4] / 10000  # 转换为百分比
        
        # 获取价格
        collateral_price = self.data_provider.functions.getAssetPrice(collateral_token).call()
        
        debt_price = self.data_provider.functions.getAssetPrice(debt_token).call()
        
        # 计算可获得的抵押品数量
        collateral_amount = (debt_amount * debt_price * (1 + liquidation_bonus)) / collateral_price
        
        # 计算利润 (以 USD 为单位)
        profit = (collateral_amount * collateral_price - debt_amount * debt_price) / 1e8
        
        # 判断是否有利可图
        is_profitable = profit > 0
        
        return profit, is_profitable