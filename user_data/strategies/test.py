from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np

class FuturesRsiMacdStrategy(IStrategy):
    """
    优化版金叉策略 - 添加更多过滤条件
    """
    timeframe = '5m'
    startup_candle_count = 300

    # 收紧止损
    stoploss = -0.008  # -0.8%

    # 优化ROI
    minimal_roi = {
        "0": 0.015,     # 1.5%
        "60": 0.01,     # 60分钟后1%
        "120": 0.005,   # 120分钟后0.5%
        "240": 0.002,   # 240分钟后0.2%
        "480": 0        # 480分钟后保本
    }

    # 启用追踪止损
    trailing_stop = True
    trailing_stop_positive = 0.005
    trailing_stop_positive_offset = 0.01
    trailing_only_offset_is_reached = True

    max_open_trades = 1
    use_exit_signal = True
    use_custom_stoploss = True

    def leverage(self, pair: str, current_time, current_rate: float,
                 proposed_leverage: float, max_leverage: float, side: str, **kwargs) -> float:
        return 2

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 均线系统
        dataframe['sma_20'] = ta.SMA(dataframe, timeperiod=20)
        dataframe['sma_50'] = ta.SMA(dataframe, timeperiod=50)
        dataframe['sma_200'] = ta.SMA(dataframe, timeperiod=200)

        # 计算短期趋势
        dataframe['trend_short'] = dataframe['sma_20'] > dataframe['sma_50']
        dataframe['trend_long'] = dataframe['sma_50'] > dataframe['sma_200']

        # 金叉/死叉
        dataframe['golden_cross'] = (dataframe['sma_20'] > dataframe['sma_50']) & (dataframe['sma_20'].shift(1) <= dataframe['sma_50'].shift(1))
        dataframe['death_cross'] = (dataframe['sma_20'] < dataframe['sma_50']) & (dataframe['sma_20'].shift(1) >= dataframe['sma_50'].shift(1))

        # 动量指标
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # 波动率
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['atr_percent'] = dataframe['atr'] / dataframe['close']

        # 成交量
        dataframe['volume_sma'] = ta.SMA(dataframe['volume'], timeperiod=20)
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']

        # 价格位置
        dataframe['price_position'] = (dataframe['close'] - dataframe['low'].rolling(50).min()) / (dataframe['high'].rolling(50).max() - dataframe['low'].rolling(50).min())

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        更严格的入场条件
        """
        # 条件1：短期金叉
        condition1 = dataframe['golden_cross']

        # 条件2：长期趋势向上
        condition2 = dataframe['trend_long']

        # 条件3：价格在合理位置（不追高）
        condition3 = dataframe['price_position'] < 0.7

        # 条件4：RSI健康
        condition4 = (dataframe['rsi'] > 35) & (dataframe['rsi'] < 65)

        # 条件5：成交量确认
        condition5 = dataframe['volume_ratio'] > 1.2

        # 条件6：波动率适中
        condition6 = (dataframe['atr_percent'] > 0.002) & (dataframe['atr_percent'] < 0.01)

        # 综合条件
        dataframe.loc[
            condition1 & condition2 & condition3 & condition4 & condition5 & condition6,
            'enter_long'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        多条件退出
        """
        # 死叉退出
        exit1 = dataframe['death_cross']

        # 价格跌破20日均线
        exit2 = dataframe['close'] < dataframe['sma_20'] * 0.995

        # RSI超买
        exit3 = dataframe['rsi'] > 75

        # 长期趋势反转
        exit4 = dataframe['sma_50'] < dataframe['sma_200']

        dataframe.loc[
            exit1 | exit2 | exit3 | exit4,
            'exit_long'
        ] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade, current_time, current_rate: float,
                        current_profit: float, **kwargs) -> float:
        """
        动态止损策略
        """
        # 盈利后收紧止损
        if current_profit > 0.01:  # 盈利1%以上
            return -0.003
        elif current_profit > 0.005:  # 盈利0.5%以上
            return -0.005
        elif current_profit > 0:  # 微利
            return -0.006

        # 亏损状态下，根据持仓时间调整
        time_held = (current_time - trade.open_date_utc).total_seconds() / 3600  # 小时

        if time_held > 4:  # 持仓4小时以上仍亏损
            return -0.012  # 放宽止损
        elif time_held > 2:  # 持仓2小时以上from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np

class FuturesRsiMacdStrategy(IStrategy):
    """
    优化版金叉策略 - 添加更多过滤条件
    """
    timeframe = '5m'
    startup_candle_count = 300

    # 收紧止损
    stoploss = -0.008  # -0.8%

    # 优化ROI
    minimal_roi = {
        "0": 0.015,     # 1.5%
        "60": 0.01,     # 60分钟后1%
        "120": 0.005,   # 120分钟后0.5%
        "240": 0.002,   # 240分钟后0.2%
        "480": 0        # 480分钟后保本
    }

    # 启用追踪止损
    trailing_stop = True
    trailing_stop_positive = 0.005
    trailing_stop_positive_offset = 0.01
    trailing_only_offset_is_reached = True

    max_open_trades = 1
    use_exit_signal = True
    use_custom_stoploss = True

    def leverage(self, pair: str, current_time, current_rate: float,
                 proposed_leverage: float, max_leverage: float, side: str, **kwargs) -> float:
        return 2

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 均线系统
        dataframe['sma_20'] = ta.SMA(dataframe, timeperiod=20)
        dataframe['sma_50'] = ta.SMA(dataframe, timeperiod=50)
        dataframe['sma_200'] = ta.SMA(dataframe, timeperiod=200)

        # 计算短期趋势
        dataframe['trend_short'] = dataframe['sma_20'] > dataframe['sma_50']
        dataframe['trend_long'] = dataframe['sma_50'] > dataframe['sma_200']

        # 金叉/死叉
        dataframe['golden_cross'] = (dataframe['sma_20'] > dataframe['sma_50']) & (dataframe['sma_20'].shift(1) <= dataframe['sma_50'].shift(1))
        dataframe['death_cross'] = (dataframe['sma_20'] < dataframe['sma_50']) & (dataframe['sma_20'].shift(1) >= dataframe['sma_50'].shift(1))

        # 动量指标
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # 波动率
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['atr_percent'] = dataframe['atr'] / dataframe['close']

        # 成交量
        dataframe['volume_sma'] = ta.SMA(dataframe['volume'], timeperiod=20)
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']

        # 价格位置
        dataframe['price_position'] = (dataframe['close'] - dataframe['low'].rolling(50).min()) / (dataframe['high'].rolling(50).max() - dataframe['low'].rolling(50).min())

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        更严格的入场条件
        """
        # 条件1：短期金叉
        condition1 = dataframe['golden_cross']

        # 条件2：长期趋势向上
        condition2 = dataframe['trend_long']

        # 条件3：价格在合理位置（不追高）
        condition3 = dataframe['price_position'] < 0.7

        # 条件4：RSI健康
        condition4 = (dataframe['rsi'] > 35) & (dataframe['rsi'] < 65)

        # 条件5：成交量确认
        condition5 = dataframe['volume_ratio'] > 1.2

        # 条件6：波动率适中
        condition6 = (dataframe['atr_percent'] > 0.002) & (dataframe['atr_percent'] < 0.01)

        # 综合条件
        dataframe.loc[
            condition1 & condition2 & condition3 & condition4 & condition5 & condition6,
            'enter_long'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        多条件退出
        """
        # 死叉退出
        exit1 = dataframe['death_cross']

        # 价格跌破20日均线
        exit2 = dataframe['close'] < dataframe['sma_20'] * 0.995

        # RSI超买
        exit3 = dataframe['rsi'] > 75

        # 长期趋势反转
        exit4 = dataframe['sma_50'] < dataframe['sma_200']

        dataframe.loc[
            exit1 | exit2 | exit3 | exit4,
            'exit_long'
        ] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade, current_time, current_rate: float,
                        current_profit: float, **kwargs) -> float:
        """
        动态止损策略
        """
        # 盈利后收紧止损
        if current_profit > 0.01:  # 盈利1%以上
            return -0.003
        elif current_profit > 0.005:  # 盈利0.5%以上
            return -0.005
        elif current_profit > 0:  # 微利
            return -0.006

        # 亏损状态下，根据持仓时间调整
        time_held = (current_time - trade.open_date_utc).total_seconds() / 3600  # 小时

        if time_held > 4:  # 持仓4小时以上仍亏损
            return -0.012  # 放宽止损
        elif time_held > 2:  # 持仓2小时以上
            return -0.01

        return -0.008  # 初始止损

    def custom_stake_amount(self, pair: str, current_time, current_rate: float,
                            proposed_stake: float, min_stake: float, max_stake: float,
                            leverage: float, entry_tag: str, side: str, **kwargs) -> float:
        return 200
            return -0.01

        return -0.008  # 初始止损

    def custom_stake_amount(self, pair: str, current_time, current_rate: float,
                            proposed_stake: float, min_stake: float, max_stake: float,
                            leverage: float, entry_tag: str, side: str, **kwargs) -> float:
        return 200