const { ethers } = require("hardhat");
const { ARBITRUM_CONFIG } = require("./config");

async function main() {
    console.log("开始部署清算机器人合约...");

    // 获取部署账户
    const [deployer] = await ethers.getSigners();
    console.log("部署账户:", deployer.address);
    console.log("账户余额:", ethers.formatEther(await ethers.provider.getBalance(deployer.address)), "ETH");
    return;
    // get the contract factory
    const liquidator = await ethers.getContractAt("Liquidator", "0x332c9dFa5B630c967BC3B36eA7087aBb53AE0170");
    
    // // 部署清算机器人合约
    // console.log("\n部署清算机器人合约...");
    // const Liquidator = await ethers.getContractFactory("Liquidator");
    // const liquidator = await Liquidator.deploy(
    //     ARBITRUM_CONFIG.AAVE_ADDRESSES_PROVIDER,
    //     // ARBITRUM_CONFIG.UNISWAP_SWAP_ROUTER,
    //     ARBITRUM_CONFIG.WETH,
    //     ARBITRUM_CONFIG.UNISWAP_V3_FACTORY,
    // );
    
    // // 等待合约部署完成
    // await liquidator.waitForDeployment();
    // console.log("清算机器人合约已部署到:", await liquidator.getAddress());
    
    //print liquidator address
    console.log("liquidator address: ", liquidator.target);
    console.log("liquidator aave provider: ", await liquidator.ADDRESSES_PROVIDER());
    console.log("liquidator factory address: ", await liquidator.UNISWAP_FACTORY());
    // console.log("liquidator router address: ", await liquidator.SWAP_ROUTER());
    console.log("liquidator weth address: ", await liquidator.WETH());

    // 定义错误签名
    // const errorSignature = 'InsufficientProfit(uint256 profit, uint256 required)';
    // const errorSelector = ethers.utils.keccak256(ethers.utils.toUtf8Bytes(errorSignature)).substring(0, 10);

    // console.log("错误选择器:", errorSelector); // 输出: 0x3ee5aeb5
    
    //执行清算
    let user = "0xbc6a26FD56c9188238B2829ad0dE7b50128793B4"
    let debt_token = "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1"
    let collateral_token = "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8"
    let max_liquidatable_debt = 2579973586128936
    // opp.estimated_profit_eth: 64459500  28496   25799735861289369
    try {
        let tx = await liquidator.liquidate(
            user,
            debt_token,
            collateral_token,
            max_liquidatable_debt
        );
        await tx.wait();
        console.log("liquidate tx: ", tx.hash);
    } catch (error) {
        console.error("调用合约 liquidate 方法时出错:", error);

        if (error.data) {
            // 解析错误数据
            const errorData = error.data;
            if (errorData.startsWith(errorSelector)) {
                const decoded = ethers.utils.defaultAbiCoder.decode(
                    ['uint256', 'uint256'],
                    '0x' + errorData.slice(10)
                );
                console.error(`错误详情: InsufficientProfit(profit: ${decoded[0].toString()}, required: ${decoded[1].toString()})`);
            } else {
                console.error("未知错误:", errorData);
            }
        } else if (error.message) {
            console.error("错误信息:", error.message);
        }
    }

    // opp.debt_token: 0x82aF49447D8a07e3bd95BD0d56f35241523fBab1
    // opp.collateral_token: 0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8
    // opp.max_liquidatable_debt: 242136.0
    // opp.estimated_profit_eth: 406841000.0
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    }); 