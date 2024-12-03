// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@uniswap/v3-core/contracts/interfaces/IUniswapV3Pool.sol";
import "@uniswap/v3-core/contracts/interfaces/callback/IUniswapV3FlashCallback.sol";
import "@uniswap/v3-periphery/contracts/interfaces/ISwapRouter.sol";
import "@aave/core-v3/contracts/interfaces/IPool.sol";
import "@aave/core-v3/contracts/interfaces/IPoolAddressesProvider.sol";
import "@aave/core-v3/contracts/interfaces/IPoolDataProvider.sol";

contract Liquidator is IUniswapV3FlashCallback, Ownable, Pausable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    struct FlashCallbackData {
        address user;
        address debtToken;
        address collToken;
        uint256 debtAmount;
        address pool;
    }

    // 常量
    IPoolAddressesProvider public immutable ADDRESSES_PROVIDER;
    ISwapRouter public immutable SWAP_ROUTER;
    address public immutable WETH;
    uint24 public constant POOL_FEE = 3000;

    // 状态变量
    mapping(address => bool) public whitelistedCallers;

    // 错误定义
    error InsufficientProfit(uint256 profit, uint256 required);
    error UnauthorizedCaller(address caller);
    error InvalidToken(address token);
    error SwapFailed();
    error LiquidationFailed();

    constructor(
        address _addressesProvider,
        address _swapRouter,
        address _weth
    ) Ownable(msg.sender) {
        ADDRESSES_PROVIDER = IPoolAddressesProvider(_addressesProvider);
        SWAP_ROUTER = ISwapRouter(_swapRouter);
        WETH = _weth;
        _addWhitelistedCaller(msg.sender);
    }

    // 修饰器
    modifier onlyWhitelisted() {
        if (!whitelistedCallers[msg.sender]) revert UnauthorizedCaller(msg.sender);
        _;
    }

    // 主要功能
    function liquidate(
        address user,
        address debtToken,
        address collToken,
        uint256 debtAmount,
        address uniswapPool
    ) external nonReentrant whenNotPaused onlyWhitelisted {
        // 验证输入
        if (debtToken == address(0) || collToken == address(0)) 
            revert InvalidToken(address(0));

        bytes memory data = abi.encode(
            FlashCallbackData({
                user: user,
                debtToken: debtToken,
                collToken: collToken,
                debtAmount: debtAmount,
                pool: uniswapPool
            })
        );

        // 执行闪电贷
        IUniswapV3Pool(uniswapPool).flash(
            address(this),
            debtAmount,
            0,
            data
        );
    }

    function uniswapV3FlashCallback(
        uint256 fee0,
        uint256 fee1,
        bytes calldata data
    ) external override nonReentrant {
        FlashCallbackData memory decoded = abi.decode(data, (FlashCallbackData));
        require(msg.sender == decoded.pool, "Invalid callback");

        // 1. 设置代币授权
        IPool pool = IPool(ADDRESSES_PROVIDER.getPool());
        _approveToken(decoded.debtToken, address(pool), decoded.debtAmount);
        
        // 2. 执行清算
        pool.liquidationCall(
            decoded.collToken,
            decoded.debtToken,
            decoded.user,
            decoded.debtAmount,
            false
        );

        // 3. 计算需要归还的金额
        uint256 amountToRepay = decoded.debtAmount + fee0;

        // 4. 将获得的抵押品通过Uniswap兑换成债务资产
        uint256 collateralReceived = IERC20(decoded.collToken).balanceOf(address(this));
        _approveToken(decoded.collToken, address(SWAP_ROUTER), collateralReceived);

        uint256 amountOut = _swapExactInputSingle(
            decoded.collToken,
            decoded.debtToken,
            collateralReceived,
            amountToRepay
        );

        if (amountOut < amountToRepay) revert SwapFailed();

        // 5. 归还闪电贷
        IERC20(decoded.debtToken).safeTransfer(decoded.pool, amountToRepay);

        // 6. 将剩余利润兑换成ETH
        uint256 remainingProfit = IERC20(decoded.debtToken).balanceOf(address(this));
        if (remainingProfit > 0) {
            _approveToken(decoded.debtToken, address(SWAP_ROUTER), remainingProfit);
            uint256 wethProfit = _swapExactInputSingle(
                decoded.debtToken,
                WETH,
                remainingProfit,
                0
            );
            
            // 将 WETH 转换为 ETH
            IWETH(WETH).withdraw(wethProfit);
            
            // 发送 ETH 给调用者
            (bool success, ) = tx.origin.call{value: wethProfit}("");
            require(success, "ETH transfer failed");
        }
    }

    // 内部函数
    function _swapExactInputSingle(
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 amountOutMinimum
    ) internal returns (uint256 amountOut) {
        ISwapRouter.ExactInputSingleParams memory params = ISwapRouter
            .ExactInputSingleParams({
                tokenIn: tokenIn,
                tokenOut: tokenOut,
                fee: POOL_FEE,
                recipient: address(this),
                deadline: block.timestamp,
                amountIn: amountIn,
                amountOutMinimum: amountOutMinimum,
                sqrtPriceLimitX96: 0
            });

        amountOut = SWAP_ROUTER.exactInputSingle(params);
    }

    function _approveToken(address token, address spender, uint256 amount) internal {
        uint256 currentAllowance = IERC20(token).allowance(address(this), spender);
        if (currentAllowance < amount) {
            IERC20(token).safeIncreaseAllowance(spender, amount - currentAllowance);
        }
    }

    function setWhitelistedCaller(address caller, bool status) external onlyOwner {
        if (status) {
            _addWhitelistedCaller(caller);
        } else {
            _removeWhitelistedCaller(caller);
        }
    }

    function _removeWhitelistedCaller(address caller) internal {
        whitelistedCallers[caller] = false;
    }

    function _addWhitelistedCaller(address caller) internal {
        whitelistedCallers[caller] = true;
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
        IERC20(token).safeTransfer(owner(), balance);
    }

    function emergencyWithdrawETH() external onlyOwner {
        uint256 balance = address(this).balance;
        (bool success, ) = tx.origin.call{value: balance}("");
        require(success, "ETH transfer failed");
    }

    receive() external payable {}

    function getLiquidationBonus(
        address collToken
    ) external view returns (uint256 liquidationBonus) {
        // 获取 AAVE 数据提供者
        IPoolDataProvider dataProvider = IPoolDataProvider(ADDRESSES_PROVIDER.getPoolDataProvider());
        
        // 获取清算配置
        (
            ,
            ,
            ,
            liquidationBonus,
            ,
            ,
            ,
            ,
            ,
            
        ) = dataProvider.getReserveConfigurationData(collToken);
    }
}

interface IWETH {
    function withdraw(uint256) external;
}