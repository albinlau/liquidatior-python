from web3 import Web3
from typing import List, Dict
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 网络配置
ARBITRUM_RPC = "https://arb1.arbitrum.io/rpc"
WEB3 = Web3(Web3.HTTPProvider(ARBITRUM_RPC))
AAVE_V3_DEPLOY_BLOCK = 28542429
BLOCK_CHUNK = 20000


# 合约地址
CONTRACTS = {
    'AAVE_POOL': '0x794a61358D6845594F94dc1DB02A252b5b4814aD',
    'AAVE_POOL_DATA_PROVIDER': '0x69FA688f1Dc47d4B5d8029D5a35FB7a548310654',
    'LIQUIDATOR': '0x332c9dFa5B630c967BC3B36eA7087aBb53AE0170', # 部署后填入
    'WETH': '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1',
    'UNISWAP_V3_FACTORY': '0x1F98431c8aD98523631AE4a59f267346ea31F984'  # Arbitrum上的Uniswap V3工厂合约
}


# 代币配置
TOKENS = {
    'WETH': '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1',
    'USDC': '0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8',
    'USDT': '0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9',
    'WBTC': '0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f',
    'DAI': '0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1'
}

# Token 精度
DECIMALS = {
    'WETH': 18,
    'USDC': 6,
    'USDT': 6,
    'WBTC': 8,
    'DAI': 18
}

# 数据库配置
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'aave_liquidation')
}

# 监控配置
MONITOR_CONFIG = {
    'interval': 1,  # 扫描间隔(秒)
    'min_health_factor': 1.0,  # 最小健康因子
    'min_liquidation_value': 10,  # 最小清算价值(USD)
    'max_gas_price': 150,  # 最大 gas 价格(Gwei)
    'min_profit': 0.00001  # 最小利润(USD)
} 