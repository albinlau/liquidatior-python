# 标准库
import os
import json
from typing import List, Dict, Tuple, Optional

# 第三方库
from web3 import Web3

class AaveDataProvider:
    def __init__(self, web3: Web3, pool_address: str, data_provider_address: str, factory_address: str):
        self.web3 = web3
        self.pool = self._load_contract(pool_address, 'AavePool.json')
        self.data_provider = self._load_contract(data_provider_address, 'AaveDataProvider.json')
        self.factory = self._load_contract(factory_address, 'UniswapV3Factory.json')
        
    def _load_contract(self, address: str, abi_file: str) -> object:
        """加载合约
        
        Args:
            address: 合约地址
            abi_file: ABI文件名
            
        Returns:
            Contract对象
            
        Raises:
            ValueError: 如果ABI格式无效
            FileNotFoundError: 如果ABI文件不存在
        """
        try:
            # 构建ABI文件路径
            abi_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 
                'abi', 
                abi_file
            )
            
            # 读取ABI文件
            with open(abi_path) as f:
                contract_json = json.load(f)
                
                # 处理不同的ABI格式
                if isinstance(contract_json, dict):
                    abi = contract_json.get('abi')
                else:
                    abi = contract_json
                    
                # 确保ABI是列表
                if not isinstance(abi, list):
                    raise ValueError(f"Invalid ABI format in {abi_file}. Expected list, got {type(abi)}")
                    
                # 处理嵌套的ABI格式
                if (isinstance(abi, list) and 
                    len(abi) == 1 and 
                    isinstance(abi[0], dict) and 
                    'abi' in abi[0]):
                    abi = abi[0]['abi']
                
                # 创建合约实例
                return self.web3.eth.contract(address=address, abi=abi)
                
        except FileNotFoundError:
            raise FileNotFoundError(f"ABI file not found: {abi_file}")
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in ABI file: {abi_file}")
        except Exception as e:
            raise Exception(f"Failed to load contract: {str(e)}")
        
    async def get_user_data(self, user_address: str) -> Dict:
        """获取用户数据"""
        try:
            # 调用合约方法
            values = self.pool.functions.getUserAccountData(user_address).call()
            
            if not values or len(values) < 6:  # 6 * 32 bytes
                print(f"获取用户 {user_address} 数据返回值长度不足: {len(values) if values else 0} bytes")
                return None
            
            try:
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
            reserves_list = raw_data
            
            for token in reserves_list:
                try:
                    # 获取用户在该代币上的数据
                    raw_data = self.data_provider.functions.getUserReserveData(token, user_address).call()
                    
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
    
    async def calculate_liquidation_profit(
        self,
        collateral_token: str,
        debt_token: str,
        debt_amount: int
    ) -> Tuple[float, bool]:
        """计算清算利润"""
        # 获取清算奖励
        raw_data = self.data_provider.functions.getReserveConfigurationData(collateral_token).call()
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
    
    async def get_asset_price(self, asset_address: str) -> float:
        """获取资产价格（以USD计价）"""
        try:
            # 从 Oracle 获取价格
            price = await self.data_provider.functions.getAssetPrice(asset_address).call()
            return float(price) / 1e8  # 价格有8位小数
        except Exception as e:
            print(f"获取资产 {asset_address} 价格失败: {str(e)}")
            return None 
    
    async def find_best_pool(self, token0: str, token1: str) -> Optional[str]:
        """查找两个代币之间TVL最深的Uniswap V3池子
        
        Args:
            token0: 代币0地址
            token1: 代币1地址
            
        Returns:
            池子地址或None
        """
        try:
            # 标准费率列表
            fee_tiers = [100, 500, 3000, 10000]  # 0.01%, 0.05%, 0.3%, 1%
            
            best_pool = None
            max_tvl = 0
            
            for fee in fee_tiers:
                # 获取池子地址
                pool_address = self.factory.functions.getPool(token0, token1, fee).call()
                
                if pool_address != "0x0000000000000000000000000000000000000000":
                    # 加载池子合约
                    pool = self._load_contract(pool_address, 'UniswapV3Pool.json')
                    
                    # 获取池子流动性
                    liquidity = pool.functions.liquidity().call()
                    
                    # 如果流动性更大，更新最佳池子
                    if liquidity > max_tvl:
                        max_tvl = liquidity
                        best_pool = pool_address
            
            return best_pool
            
        except Exception as e:
            print(f"查找最佳池子时出错: {str(e)}")
            return None 