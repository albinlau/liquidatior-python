// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "./interfaces/IUniswapV3Pool.sol";
import "./interfaces/IUniswapV3SwapCallback.sol";
import "./interfaces/IPool.sol";
import "./interfaces/IPoolAddressesProvider.sol";

contract Liquidator is IUniswapV3SwapCallback, Ownable, Pausable {
    using SafeERC20 for IERC20;

    struct SwapCallbackData {
        address user;           // 被清算用户
        address debtToken;      // 债务代币
        address collToken;      // 抵押品代币
        uint256 debtAmount;     // 清算金额
        bool isFlashLoan;       // 是否是闪电贷
    }

    // 常量
    IPoolAddressesProvider public immutable ADDRESSES_PROVIDER;
    address public immutable WETH;
    uint24 public constant POOL_FEE = 500;
    IUniswapV3Factory public immutable UNISWAP_FACTORY;

    constructor(
        address _addressesProvider,
        address _weth,
        address _factory
    ) Ownable(msg.sender) {
        ADDRESSES_PROVIDER = IPoolAddressesProvider(_addressesProvider);
        WETH = _weth;
        UNISWAP_FACTORY = IUniswapV3Factory(_factory);
    }

    function liquidate(
        address user,
        address debtToken,
        address collToken,
        uint256 debtAmount
    ) external whenNotPaused {
        // 1. 获取debt token和weth的uniswap交易对地址
        (address pool, address token0, ) = getTokenETHPool(debtToken);
        require(pool != address(0), "Pool not found");

        // 准备回调数据
        bytes memory data = abi.encode(
            SwapCallbackData({
                user: user,
                debtToken: debtToken,
                collToken: collToken,
                debtAmount: debtAmount,
                isFlashLoan: true
            })
        );

        // 2. 通过swap操作获取debtAmount的debt token
        bool zeroForOne = token0 == WETH;
        IUniswapV3Pool(pool).swap(
            address(this),
            zeroForOne,
            -int256(debtAmount),  // 负值表示精确输出
            zeroForOne ? 
                TickMath.MIN_SQRT_RATIO + 1 : 
                TickMath.MAX_SQRT_RATIO - 1,
            data
        );
    }

    function uniswapV3SwapCallback(
        int256 amount0Delta,
        int256 amount1Delta,
        bytes calldata data
    ) external override {
        // 1. 检查回调数据
        SwapCallbackData memory decoded = abi.decode(data, (SwapCallbackData));

        // 2. 检查是否是闪电贷
        if (!decoded.isFlashLoan) {
            IERC20(decoded.collToken).transfer(msg.sender, amount0Delta > 0 ? uint256(amount0Delta) : uint256(amount1Delta));
            return;
        }
        
        // 3. 进入回调函数，计算需要支付的WETH数量
        uint256 payAmount = uint256(amount0Delta > 0 ? amount0Delta : amount1Delta);

        // 4. 检查debt Token余额
        uint256 debtTokenBalance = IERC20(decoded.debtToken).balanceOf(address(this));
        require(debtTokenBalance >= decoded.debtAmount, "Insufficient debt token");

        // 5. 执行清算
        IPool pool = IPool(ADDRESSES_PROVIDER.getPool());
        IERC20(decoded.debtToken).approve(address(pool), decoded.debtAmount);
        
        pool.liquidationCall(
            decoded.collToken,
            decoded.debtToken,
            decoded.user,
            decoded.debtAmount,
            false
        );

        // 6. 检查获得的抵押品余额
        uint256 collBalance = IERC20(decoded.collToken).balanceOf(address(this));
        require(collBalance > 0, "No collateral received");

        // 7. 将抵押品兑换为WETH
        (address collPool, address token0, ) = getTokenETHPool(decoded.collToken);
        require(collPool != address(0), "Pool not found");

        bool ZeroForOne = token0 == decoded.collToken;
        
        // 准备回调数据
        bytes memory swapData = abi.encode(
            SwapCallbackData({
                user: decoded.user,
                debtToken: decoded.debtToken,
                collToken: decoded.collToken,
                debtAmount: decoded.debtAmount,
                isFlashLoan: false
            })
        );
        IUniswapV3Pool(collPool).swap(
            address(this),
            ZeroForOne,
            int256(collBalance),
            ZeroForOne ? 
                TickMath.MIN_SQRT_RATIO + 1 : 
                TickMath.MAX_SQRT_RATIO - 1,
            swapData
        );

        // 8. 归还WETH
        uint256 wethBalance = IERC20(WETH).balanceOf(address(this));
        require(wethBalance >= payAmount, "Insufficient WETH for payback");
        IERC20(WETH).transfer(msg.sender, payAmount);

        // 9. 提取剩余WETH利润
        uint256 profit = wethBalance - payAmount;
        if (profit > 0) {
            IWETH(WETH).withdraw(profit);
            (bool success, ) = tx.origin.call{value: profit}("");
            require(success, "ETH transfer failed");
        }
    }

    // 辅助函数
    function getTokenETHPool(
        address token
    ) public view returns (address pool, address token0, address token1) {
        (token0, token1) = token < WETH ? (token, WETH) : (WETH, token);
        pool = UNISWAP_FACTORY.getPool(token0, token1, POOL_FEE);
    }

    // 紧急功能
    function emergencyWithdraw(address token) external onlyOwner {
        uint256 balance = IERC20(token).balanceOf(address(this));
        IERC20(token).safeTransfer(msg.sender, balance);
    }

    function emergencyWithdrawETH() external onlyOwner {
        uint256 balance = address(this).balance;
        (bool success, ) = msg.sender.call{value: balance}("");
        require(success, "ETH transfer failed");
    }

    receive() external payable {}
}

interface IUniswapV3Factory {
    function getPool(
        address tokenA,
        address tokenB,
        uint24 fee
    ) external view returns (address pool);
}

interface IWETH {
    function withdraw(uint256) external;
}

library TickMath {
    int24 internal constant MIN_TICK = -887272;
    int24 internal constant MAX_TICK = -MIN_TICK;
    uint160 internal constant MIN_SQRT_RATIO = 4295128739;
    uint160 internal constant MAX_SQRT_RATIO = 1461446703485210103287273052203988822378723970342;
}