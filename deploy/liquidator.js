const { ethers } = require("hardhat");
const { ARBITRUM_CONFIG } = require("./config");

async function main() {
    console.log("开始部署清算机器人合约...");

    // 获取部署账户
    const [deployer] = await ethers.getSigners();
    console.log("部署账户:", deployer.address);
    console.log("账户余额:", ethers.formatEther(await ethers.provider.getBalance(deployer.address)), "ETH");

    // get the contract factory
    const liquidator = await ethers.getContractAt("Liquidator", "0x526E8a66E357FFeaEeEc6d7Be1E5eA44a788dd1d");
    
    //print liquidator address
    console.log("liquidator address: ", liquidator.target);
    console.log("liquidator aave provider: ", await liquidator.ADDRESSES_PROVIDER());
    console.log("liquidator factory address: ", await liquidator.UNISWAP_FACTORY());
    console.log("liquidator router address: ", await liquidator.SWAP_ROUTER());
    console.log("liquidator weth address: ", await liquidator.WETH());

    //执行清算
    // opp.debt_token: 0x82aF49447D8a07e3bd95BD0d56f35241523fBab1
    // opp.collateral_token: 0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8
    // opp.max_liquidatable_debt: 420083.0
    // opp.estimated_profit_eth: 705314000.0
    let tx = await liquidator.liquidate(

    );
    await tx.wait();
    console.log("liquidate tx: ", tx.hash);

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