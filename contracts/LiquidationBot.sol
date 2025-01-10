// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "./interfaces/IUniswapV3Pool.sol";
import "./interfaces/IUniswapV3FlashCallback.sol";
import "./interfaces/ISwapRouter.sol";
import "./interfaces/IPool.sol";
import "./interfaces/IPoolAddressesProvider.sol";

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

contract Liquidator is IUniswapV3FlashCallback, Ownable, Pausable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    struct FlashCallbackData {
        address user;
        address debtToken;
        address collToken;
        uint256 debtAmount;
    }

    // 常量
    IPoolAddressesProvider public immutable ADDRESSES_PROVIDER;
    ISwapRouter public immutable SWAP_ROUTER;
    address public immutable WETH;
    uint24 public constant POOL_FEE = 500;
    IUniswapV3Factory public immutable UNISWAP_FACTORY;

    // 错误定义
    error InsufficientProfit(uint256 profit, uint256 required);

    constructor(
        address _addressesProvider,
        address _swapRouter,
        address _weth,
        address _factory
    ) Ownable(msg.sender) {
        ADDRESSES_PROVIDER = IPoolAddressesProvider(_addressesProvider);
        SWAP_ROUTER = ISwapRouter(_swapRouter);
        WETH = _weth;
        UNISWAP_FACTORY = IUniswapV3Factory(_factory);
    }

    // 主要功能
    function liquidate(
        address user,
        address debtToken,
        address collToken,
        uint256 debtAmount
    ) external nonReentrant whenNotPaused {
        (address uniswapPool, address token0, ) = getTokenETHPool(debtToken);

        bytes memory data = abi.encode(
            FlashCallbackData({
                user: user,
                debtToken: debtToken,
                collToken: collToken,
                debtAmount: debtAmount
            })
        );

        // 执行闪电贷
        if (token0 == debtToken) {
            IUniswapV3Pool(uniswapPool).flash(
                address(this),
                debtAmount,
                0,
                data
            );
        } else {
            IUniswapV3Pool(uniswapPool).flash(
                address(this),
                0,
                debtAmount,
                data
            );
        }
    }

    function uniswapV3FlashCallback(
        uint256 fee0,
        uint256 fee1,
        bytes calldata data
    ) external override nonReentrant {
        FlashCallbackData memory decoded = abi.decode(data, (FlashCallbackData));
        
        // 1. 执行清算
        IPool pool = IPool(ADDRESSES_PROVIDER.getPool());
        IERC20(decoded.debtToken).approve(address(pool), decoded.debtAmount);
        require(IERC20(decoded.debtToken).balanceOf(address(this)) == decoded.debtAmount, "Insufficient debtAmount balance");
        pool.liquidationCall(
            decoded.collToken,
            decoded.debtToken,
            decoded.user,
            decoded.debtAmount,
            false
        );

        // 2. 将获得的抵押品通过Uniswap兑换成债务资产
        uint256 collateralReceived = IERC20(decoded.collToken).balanceOf(address(this));
        IERC20(decoded.collToken).approve(address(SWAP_ROUTER), collateralReceived);
        _swapExactInputSingle(
            decoded.collToken,
            decoded.debtToken,
            collateralReceived,
            0
        );
        uint256 amountOut = IERC20(decoded.debtToken).balanceOf(address(this));

        // 3. 归还闪电贷
        //计算需要归还的金额
        uint256 amountToRepay = decoded.debtAmount + fee0;
        if (fee0 == 0) {
            amountToRepay += fee1;
        }
        if (amountOut < amountToRepay)
            revert InsufficientProfit(amountOut, amountToRepay);
        IERC20(decoded.debtToken).safeTransfer(msg.sender, amountToRepay);

        // 6. 将剩余利润兑换成ETH
        uint256 remainingProfit = IERC20(decoded.debtToken).balanceOf(address(this));
        IERC20(decoded.debtToken).approve(address(SWAP_ROUTER), remainingProfit);
        _swapExactInputSingle(
            decoded.debtToken,
            WETH,
            remainingProfit,
            0
        );

        // 7. 将ETH发送给调用者
        uint256 wethProfit = IERC20(WETH).balanceOf(address(this));
        // 将 WETH 转换为 ETH
        IWETH(WETH).withdraw(wethProfit);
        // 发送 ETH 给调用者
        (bool success, ) = tx.origin.call{value: wethProfit}("");
        require(success, "ETH transfer failed");
    }

    // 内部函数
    function _swapExactInputSingle(
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 amountOutMinimum
    ) internal {
        ISwapRouter.ExactInputSingleParams memory params = ISwapRouter
            .ExactInputSingleParams({
                tokenIn: tokenIn,
                tokenOut: tokenOut,
                fee: POOL_FEE,
                recipient: address(this),
                deadline: block.timestamp + 1 days,
                amountIn: amountIn,
                amountOutMinimum: amountOutMinimum,
                sqrtPriceLimitX96: 0
            });

        SWAP_ROUTER.exactInputSingle(params);
    }

    function pause() external onlyOwner {
        _pause();
    }

    function unpause() external onlyOwner {
        _unpause();
    }

    // 紧急功能
    function emergencyWithdraw(address token) external onlyOwner {
        uint256 balance = IERC20(token).balanceOf(address(this));
        IERC20(token).safeTransfer(msg.sender, balance);
    }

    function emergencyWithdrawETH() external onlyOwner {
        uint256 wethBal = IERC20(WETH).balanceOf(address(this));
        // 将 WETH 转换为 ETH
        IWETH(WETH).withdraw(wethBal);

        uint256 balance = address(this).balance;
        (bool success, ) = tx.origin.call{value: balance}("");
        require(success, "ETH transfer failed");
    }

    receive() external payable {}

    function getUniswapPool(
        address tokenA,
        address tokenB
    ) public view returns (address pool, address token0, address token1) {
        // 对代币地址进行排序，确保顺序一致
        (token0, token1) = tokenA < tokenB 
            ? (tokenA, tokenB) 
            : (tokenB, tokenA);
            
        // 使用设定的手续费率获取交易对地址
        pool = UNISWAP_FACTORY.getPool(token0, token1, POOL_FEE);
        
        if (pool == address(0)) revert("Pool does not exist");
    }

    function getTokenETHPool(
        address token
    ) public view returns (address pool, address token0, address token1) {
        return getUniswapPool(token, WETH);
    }
}