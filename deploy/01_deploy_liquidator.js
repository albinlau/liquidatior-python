const { ethers } = require("hardhat");
const { ARBITRUM_CONFIG } = require("./config");

async function main() {
    console.log("开始部署清算机器人合约...");

    // 获取部署账户
    const [deployer] = await ethers.getSigners();
    console.log("部署账户:", deployer.address);
    console.log("账户余额:", ethers.utils.formatEther(await deployer.getBalance()), "ETH");
    
    // 部署清算机器人合约
    console.log("\n部署清算机器人合约...");
    const Liquidator = await ethers.getContractFactory("Liquidator");
    const liquidator = await Liquidator.deploy(
        ARBITRUM_CONFIG.AAVE_ADDRESSES_PROVIDER,
        ARBITRUM_CONFIG.UNISWAP_SWAP_ROUTER,
        ARBITRUM_CONFIG.WETH
    );
    
    await liquidator.deployed();
    console.log("清算机器人合约已部署到:", liquidator.address);
    
    // // 验证合约
    // if (network.name !== "hardhat" && network.name !== "localhost") {
    //     console.log("\n等待区块确认...");
    //     await liquidator.deployTransaction.wait(5);
        
    //     console.log("验证合约...");
    //     await run("verify:verify", {
    //         address: liquidator.address,
    //         constructorArguments: [
    //             ARBITRUM_CONFIG.AAVE_ADDRESSES_PROVIDER,
    //             ARBITRUM_CONFIG.UNISWAP_SWAP_ROUTER,
    //             ARBITRUM_CONFIG.WETH
    //         ],
    //     });
    // }
    
    // // 设置初始配置
    // if (network.name !== "hardhat") {
    //     console.log("\n设置初始配置...");
        
    //     // 将部署者添加为白名单调用者
    //     const tx = await liquidator.setWhitelistedCaller(deployer.address, true);
    //     await tx.wait();
    //     console.log("已将部署者添加到白名单:", deployer.address);
    // }
    
    console.log("\n部署完成!");
    console.log("清算机器人合约:", liquidator.address);
    console.log("\n下一步操作:");
    console.log("1. 添加更多白名单地址");
    console.log("2. 确保合约有足够的 ETH 余额用于接收清算利润");
    console.log("3. 设置监控脚本以监控清算机会");
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    }); 