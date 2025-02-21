const { ethers } = require("hardhat");

// Arbitrum 网络配置
const ARBITRUM_CONFIG = {
    // Aave V3
    AAVE_ADDRESSES_PROVIDER: "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb",
    
    // Uniswap V3
    UNISWAP_SWAP_ROUTER: "0xE592427A0AEce92De3Edee1F18E0157C05861564",
    UNISWAP_V3_FACTORY: "0x1F98431c8aD98523631AE4a59f267346ea31F984",
    
    // Tokens
    WETH: "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
    
    // 常用代币地址
    TOKENS: {
        USDC: "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8",
        USDT: "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
        WBTC: "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f",
        DAI: "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1"
    }
};

module.exports = {
    ARBITRUM_CONFIG
}; 