# Aave V3 清算机器人

基于 Arbitrum 网络的 Aave V3 清算机器人，使用 Uniswap V3 闪电贷进行清算操作。

## 功能特点

- 实时监控 Aave V3 上的借贷头寸
- 自动发现可清算用户
- 使用 Uniswap V3 闪电贷获取清算所需资金
- 多任务异步执行
- MySQL 数据库存储用户数据和清算机会
- 自动计算清算收益并执行有利可图的清算

## 环境要求

- Python 3.8+
- MySQL 5.7+
- Node.js 14+
- Web3.py
- SQLAlchemy
- Hardhat

## 安装步骤

1. 克隆项目并安装 Python 依赖：
```bash
pip install -r requirements.txt
```

2. 安装 Node.js 依赖：
```bash
npm install
```

3. 配置环境变量：
```bash
cp .env.example .env
```
编辑 `.env` 文件，填入以下信息：
- `ARBITRUM_RPC_URL`: Arbitrum RPC 节点地址
- `PRIVATE_KEY`: 部署和执行清算的账户私钥
- `ETHERSCAN_API_KEY`: Arbiscan API Key（用于合约验证）
- 数据库配置
- 监控参数配置

4. 创建 MySQL 数据库：
```sql
CREATE DATABASE aave_liquidation CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

## 部署合约

1. 编译合约：
```bash
npx hardhat compile
```

2. 部署到 Arbitrum：
```bash
npx hardhat run deploy/01_deploy_liquidator.js --network arbitrum
```

3. 将部署的合约地址更新到 `monitor/config/config.py` 中的 `CONTRACTS['LIQUIDATOR']`

## 运行监控程序

1. 启动监控程序：
```bash
python monitor/main.py
```

监控程序包含四个异步任务：
- 用户发现（60分钟/次）
- 用户数据更新（30分钟/次）
- 清算机会发现（5分钟/次）
- 清算执行（1分钟/次）

## 配置说明

### 合约配置（config/config.py）
- `CONTRACTS`: 合约地址配置
- `TOKENS`: 支持的代币配置
- `DECIMALS`: 代币精度配置

### 监控配置（.env）
- `MONITOR_INTERVAL`: 监控间隔
- `MIN_HEALTH_FACTOR`: 最小健康因子
- `MIN_LIQUIDATION_VALUE`: 最小清算价值
- `MAX_GAS_PRICE`: 最大 Gas 价格
- `MIN_PROFIT_THRESHOLD`: 最小利润阈值

## 数据库结构

- `users`: 用户信息表
- `positions`: 用户头寸表
- `liquidation_opportunities`: 清算机会表
- `token_prices`: 代币价格表

## 安全建议

1. 使用独立的执行账户
2. 设置合适的利润阈值
3. 监控 Gas 价格
4. 定期备份数据库
5. 使用安全的 RPC 节点

## 监控和维护

1. 检查日志：
```bash
tail -f liquidator.log
```

2. 查看清算统计：
```sql
SELECT COUNT(*) as count, SUM(estimated_profit_eth) as total_profit 
FROM liquidation_opportunities 
WHERE executed = true;
```

3. 停止程序：
使用 Ctrl+C 或发送 SIGTERM 信号，程序会优雅关闭。

## 故障排除

1. Gas 价格过高
- 检查 `MAX_GAS_PRICE` 设置
- 考虑提高利润阈值

2. 清算失败
- 检查合约余额
- 验证 Uniswap 池流动性
- 检查健康因子是否已改变

3. 数据库连接问题
- 验证数据库配置
- 检查连接权限
- 确保数据库服务运行

## 贡献指南

1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证

MIT 