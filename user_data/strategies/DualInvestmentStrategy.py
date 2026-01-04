# DualInvestmentFuturesStable.py
import talib.abstract as ta
import pandas as pd
import numpy as np
from freqtrade.strategy import IStrategy
from pandas import DataFrame, Series
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DualInvestmentStrategy(IStrategy):
    """
    稳定的合约交易策略 - 修复MACD错误
    """

    # 使用15分钟时间框架
    timeframe = '15m'

    # 止损设置
    stoploss = -0.05

    # ROI设置
    minimal_roi = {
        "0": 0.15,
        "15": 0.08,
        "30": 0.04,
        "60": 0.02,
        "120": 0
    }

    # 跟踪止损
    trailing_stop = True
    trailing_stop_positive = 0.03
    trailing_stop_positive_offset = 0.05
    trailing_only_offset_is_reached = True

    # 基础参数
    process_only_new_candles = True
    startup_candle_count = 100

    # 禁用exit_signal
    use_exit_signal = False

    # 合约交易特有设置
    can_short = True
    use_custom_stoploss = True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算技术指标 - 修复MACD问题
        """
        logger.info(f"处理交易对: {metadata['pair']} - 数据形状: {dataframe.shape}")

        try:
            # 核心动量指标
            dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)
            dataframe['rsi_slow'] = ta.RSI(dataframe['close'], timeperiod=28)

            # 修复MACD计算 - 使用正确的方法
            # 方法1：使用talib.MACD函数并正确解包
            macd, macd_signal, macd_hist = ta.MACD(
                dataframe['close'],
                fastperiod=12,
                slowperiod=26,
                signalperiod=9
            )

            dataframe['macd'] = macd
            dataframe['macd_signal'] = macd_signal
            dataframe['macd_hist'] = macd_hist

            # 方法2：或者使用talib.MACDEXT获取扩展MACD
            # macd, macd_signal, macd_hist = ta.MACDEXT(
            #     dataframe['close'],
            #     fastperiod=12, fastmatype=0,
            #     slowperiod=26, slowmatype=0,
            #     signalperiod=9, signalmatype=0
            # )

            # 布林带
            bb_period = 20
            bb_std = 2.5
            dataframe['bb_upper'] = ta.BBANDS(
                dataframe['close'],
                timeperiod=bb_period,
                nbdevup=bb_std,
                nbdevdn=bb_std
            )[0]  # 第一个返回值是上轨

            dataframe['bb_lower'] = ta.BBANDS(
                dataframe['close'],
                timeperiod=bb_period,
                nbdevup=bb_std,
                nbdevdn=bb_std
            )[2]  # 第三个返回值是下轨

            dataframe['bb_middle'] = ta.SMA(dataframe['close'], timeperiod=bb_period)

            # 计算布林带宽度
            dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['bb_middle']

            # 移动平均线
            dataframe['ema_9'] = ta.EMA(dataframe['close'], timeperiod=9)
            dataframe['ema_21'] = ta.EMA(dataframe['close'], timeperiod=21)
            dataframe['ema_50'] = ta.EMA(dataframe['close'], timeperiod=50)
            dataframe['sma_50'] = ta.SMA(dataframe['close'], timeperiod=50)

            # ATR - 波动性指标
            dataframe['atr'] = ta.ATR(
                dataframe['high'],
                dataframe['low'],
                dataframe['close'],
                timeperiod=14
            )
            dataframe['atr_percent'] = dataframe['atr'] / dataframe['close'] * 100

            # 成交量指标
            dataframe['volume_sma'] = ta.SMA(dataframe['volume'], timeperiod=20)
            dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']

            # 价格位置指标
            dataframe['high_20'] = dataframe['high'].rolling(20).max()
            dataframe['low_20'] = dataframe['low'].rolling(20).min()

            # 避免除零错误
            price_range = dataframe['high_20'] - dataframe['low_20']
            price_range = price_range.replace(0, np.nan)  # 将0替换为NaN

            dataframe['price_position'] = (dataframe['close'] - dataframe['low_20']) / price_range

            # 填充NaN值
            dataframe['price_position'] = dataframe['price_position'].fillna(0.5)

            # 调试信息
            logger.info(f"{metadata['pair']} - 指标计算完成")
            logger.info(f"  RSI范围: {dataframe['rsi'].min():.1f} - {dataframe['rsi'].max():.1f}")
            logger.info(f"  MACD范围: {dataframe['macd'].min():.3f} - {dataframe['macd'].max():.3f}")

            return dataframe

        except Exception as e:
            logger.error(f"计算指标时出错: {e}")
            logger.error(f"数据列: {dataframe.columns.tolist()}")
            raise

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        入场逻辑 - 简化和稳定版
        """
        dataframe.loc[:, 'enter_long'] = 0
        dataframe.loc[:, 'enter_short'] = 0

        # ===== 多头信号 =====
        # 简化条件，避免过于复杂
        long_conditions = []

        # 条件1: RSI超卖
        long_conditions.append(dataframe['rsi'] < 35)

        # 条件2: 价格接近布林带下轨
        long_conditions.append(dataframe['close'] <= dataframe['bb_lower'] * 1.05)

        # 条件3: MACD可能金叉
        long_conditions.append(dataframe['macd'] > dataframe['macd_signal'] * 0.95)

        # 条件4: 成交量确认
        long_conditions.append(dataframe['volume_ratio'] > 0.7)

        # 至少满足3个条件
        if long_conditions:
            # 计算满足的条件数量
            condition_count = sum([1 for cond in long_conditions if cond is not None])

            if condition_count >= 3:
                # 使用reduce来组合条件
                from functools import reduce
                combined_condition = reduce(lambda x, y: x & y,
                                            [cond for cond in long_conditions if cond is not None])
                dataframe.loc[combined_condition, 'enter_long'] = 1

        # ===== 空头信号 =====
        short_conditions = []

        # 条件1: RSI超买
        short_conditions.append(dataframe['rsi'] > 65)

        # 条件2: 价格接近布林带上轨
        short_conditions.append(dataframe['close'] >= dataframe['bb_upper'] * 0.95)

        # 条件3: MACD可能死叉
        short_conditions.append(dataframe['macd'] < dataframe['macd_signal'] * 1.05)

        # 条件4: 成交量确认
        short_conditions.append(dataframe['volume_ratio'] > 0.7)

        # 至少满足3个条件
        if short_conditions:
            condition_count = sum([1 for cond in short_conditions if cond is not None])

            if condition_count >= 3:
                from functools import reduce
                combined_condition = reduce(lambda x, y: x & y,
                                            [cond for cond in short_conditions if cond is not None])
                dataframe.loc[combined_condition, 'enter_short'] = 1

        # 信号统计
        long_signals = dataframe['enter_long'].sum()
        short_signals = dataframe['enter_short'].sum()

        if long_signals > 0 or short_signals > 0:
            logger.info(f"{metadata['pair']} - 信号统计: 多头={long_signals}, 空头={short_signals}")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        退出逻辑
        """
        dataframe.loc[:, 'exit_long'] = 0
        dataframe.loc[:, 'exit_short'] = 0

        # 可以添加额外的退出条件，但主要依赖ROI和止损
        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """
        动态止损 - 基于ATR
        """
        try:
            # 获取最新的数据
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

            if len(dataframe) > 0:
                last_candle = dataframe.iloc[-1]

                # 计算ATR百分比
                if 'atr_percent' in last_candle and not pd.isna(last_candle['atr_percent']):
                    atr_percent = last_candle['atr_percent']

                    # 基础止损
                    base_sl = -0.05

                    # 根据ATR调整（高波动放宽止损）
                    atr_adjustment = atr_percent / 100 * 0.5  # ATR的50%

                    # 动态止损
                    dynamic_sl = base_sl - atr_adjustment

                    # 限制在合理范围
                    dynamic_sl = max(dynamic_sl, -0.15)  # 最大15%
                    dynamic_sl = min(dynamic_sl, -0.02)  # 最小2%

                    return dynamic_sl
        except Exception as e:
            logger.warning(f"计算动态止损时出错: {e}")

        return -0.05  # 默认止损