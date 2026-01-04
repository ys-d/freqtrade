from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter, stoploss_from_open
import pandas as pd
import numpy as np
import talib.abstract as ta

class BearMarketShortStrategy(IStrategy):
    # 基础配置（4h熊市空单专属）
    timeframe = '4h'
    minimal_roi = {
        "0": 0.02  # 空单止盈2%
    }
    stoploss = -0.015  # 空单止损1.5%（反弹止损）
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.015
    trailing_only_offset_is_reached = True
    max_open_trades = 1
    stake_currency = "USDT"
    stake_amount = "unlimited"
    process_only_new_candles = True
    startup_candle_count: int = 30

    # 指标参数（可优化）
    rsi_high = IntParameter(70, 85, default=75, space="buy")
    sma_slope_threshold = DecimalParameter(-0.5, -0.1, default=-0.3, space="buy")

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # 核心指标：判断顶部/下跌趋势
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['sma20'] = ta.SMA(dataframe, timeperiod=20)
        dataframe['sma20_slope'] = dataframe['sma20'].diff(5) / dataframe['sma20'] * 100
        dataframe['sma20_slope'] = dataframe['sma20_slope'].fillna(0)

        # 价格新高（确认顶部）
        dataframe['high_8'] = dataframe['high'].rolling(8).max()
        dataframe['high_8'] = dataframe['high_8'].fillna(dataframe['high'])

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # 空单入场条件：顶部+下跌趋势
        entry_conditions = (
                (dataframe['rsi'] > self.rsi_high.value)  # RSI超买（顶部）
                & (dataframe['sma20_slope'] < self.sma_slope_threshold.value)  # 均线向下
                & (dataframe['high'] == dataframe['high_8'])  # 价格创8期新高
                & (dataframe['volume'] > dataframe['volume'].rolling(20).mean() * 1.5)  # 放量下跌
                & (dataframe['volume'] > 0)
        )

        # 空单入场（enter_short=1）
        dataframe['enter_short'] = 0
        dataframe.loc[entry_conditions, 'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # 空单出场条件：RSI超卖（止盈）+ 反弹止损
        exit_conditions = (
                (dataframe['rsi'] < 25)  # RSI超卖，止盈
                & (dataframe['volume'] > 0)
        )

        dataframe['exit_short'] = 0
        dataframe.loc[exit_conditions, 'exit_short'] = 1

        return dataframe