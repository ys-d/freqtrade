# 导入核心库
from freqtrade.strategy import IStrategy, merge_informative_pair
from pandas import DataFrame
import talib.abstract as ta
import numpy as np

class BTCBinanceStrategy(IStrategy):
    # 1. 策略基本配置（适配币安）
    timeframe = '1h'          # 币安1H K线
    minimal_roi = {           # 止盈规则（BTC盈利1%止盈）
        "0": 0.01
    }
    stoploss = -0.015         # 止损1.5%
    trailing_stop = True
    trailing_stop_positive = 0.005
    trailing_stop_positive_offset = 0.01
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = True

    # 2. 币安BTC关键支撑/阻力位（可动态更新）
    BTC_SUPPORT = 40000
    BTC_RESISTANCE = 43000

    # 3. 指标计算（均线+RSI，适配币安K线）
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 60日均线（BTC中期趋势）
        dataframe['ma60'] = ta.MA(dataframe, timeperiod=60)
        # 20日均线（BTC短期趋势）
        dataframe['ma20'] = ta.MA(dataframe, timeperiod=20)
        # RSI（超买超卖）
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    # 4. 入场信号（支撑+均线共振）
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 做多信号：价格>支撑位 + ma20上穿ma60 + RSI<30（超卖）
        dataframe.loc[
            (
                (dataframe['close'] > self.BTC_SUPPORT) &
                (dataframe['ma20'] > dataframe['ma60']) &
                (dataframe['rsi'] < 30)
            ),
            'enter_long'] = 1
        return dataframe

    # 5. 出场信号（阻力+均线死叉）
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 平仓信号：价格>阻力位 + ma20下穿ma60 + RSI>70（超买）
        dataframe.loc[
            (
                (dataframe['close'] > self.BTC_RESISTANCE) &
                (dataframe['ma20'] < dataframe['ma60']) &
                (dataframe['rsi'] > 70)
            ),
            'exit_long'] = 1
        return dataframe