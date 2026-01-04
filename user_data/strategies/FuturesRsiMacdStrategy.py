from functools import reduce

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta



class FuturesRsiMacdStrategy(IStrategy):
    """
   优化版趋势策略 - 提高胜率和盈亏比
   """
    timeframe = '5m'
    startup_candle_count = 100

    # 风险管理参数
    stoploss = -0.008  # -0.8%止损（放宽止损，给趋势更多空间）


    minimal_roi = {
        "0": 0.025,     # 2.5% 快速止盈
        "20": 0.018,    # 20分钟后1.8%
        "40": 0.012,    # 40分钟后1.2%
        "80": 0.006,    # 80分钟后0.6%
        "120": 0.002    # 120分钟后0.2%
    }

    # 策略设置
    trailing_stop = False
    max_open_trades = 5
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # 可选：增加冷却期，减少过度交易
    process_only_new_candles = True
    use_custom_stoploss = False

    def leverage(self, pair: str, current_time, current_rate: float,
                 proposed_leverage: float, max_leverage: float, side: str, **kwargs) -> float:
        return 4

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算指标
        """
        # 1. 价格指标
        dataframe['ema_9'] = ta.EMA(dataframe, timeperiod=9)
        dataframe['ema_21'] = ta.EMA(dataframe, timeperiod=21)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_100'] = ta.EMA(dataframe, timeperiod=100)

        # 2. 动量指标
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['rsi_sma'] = ta.SMA(dataframe['rsi'], timeperiod=14)

        # 3. MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        # 4. 趋势强度
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)

        # 5. 波动率
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['atr_percent'] = dataframe['atr'] / dataframe['close']

        # 6. 支撑阻力
        dataframe['bb_upper'], dataframe['bb_middle'], dataframe['bb_lower'] = ta.BBANDS(
            dataframe['close'], timeperiod=20, nbdevup=2.0, nbdevdn=2.0, matype=0)

        # 7. 成交量
        dataframe['volume_sma'] = ta.SMA(dataframe['volume'], timeperiod=20)
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']

        # 8. 趋势方向
        dataframe['trend_up'] = (
                (dataframe['ema_9'] > dataframe['ema_21']) &
                (dataframe['ema_21'] > dataframe['ema_50']) &
                (dataframe['ema_50'] > dataframe['ema_100'])
        )
        # 在populate_indicators中添加
        dataframe['prev_trend'] = (
                (dataframe['ema_9'].shift(1) > dataframe['ema_21'].shift(1)) &
                (dataframe['ema_21'].shift(1) > dataframe['ema_50'].shift(1))
        )



        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        更严格的入场条件
        """
        conditions = []

        # === 核心条件：强趋势 ===
        conditions.append(dataframe['trend_up'])  # 均线多头排列

        # === 条件2：价格回调到支撑位 ===
        # 价格在EMA21附近（回调入场）
        price_near_ema21 = (
                (dataframe['close'] > dataframe['ema_21'] * 0.995) &
                (dataframe['close'] < dataframe['ema_21'] * 1.005)
        )
        conditions.append(price_near_ema21)

        # === 条件3：RSI健康回调 ===
        # RSI从超买区回调到合理区间
        rsi_condition = (
                (dataframe['rsi'] > 40) &
                (dataframe['rsi'] < 65) &
                (dataframe['rsi'] > dataframe['rsi'].shift(1))  # RSI开始上升
        )
        conditions.append(rsi_condition)

        # === 条件4：MACD金叉确认 ===
        macd_golden_cross = (
                (dataframe['macd'] > dataframe['macdsignal']) &
                (dataframe['macd'].shift(1) <= dataframe['macdsignal'].shift(1))
        )
        conditions.append(macd_golden_cross)

        # === 条件5：趋势强度足够 ===
        adx_condition = dataframe['adx'] > 25  # 强趋势
        conditions.append(adx_condition)

        # === 条件6：成交量确认 ===
        volume_condition = dataframe['volume_ratio'] > 0.8  # 成交量不低于平均水平
        conditions.append(volume_condition)

        # === 条件7：避免高波动 ===
        volatility_condition = dataframe['atr_percent'] < 0.012  # ATR小于1.2%
        conditions.append(volatility_condition)
        # 在入场条件中添加，确保趋势已经持续了一段时间
        conditions.append(dataframe['prev_trend'])
        # 综合所有条件
        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'enter_long'
            ] = 1

            dataframe.loc[dataframe['enter_long'] == 1, 'enter_tag'] = 'strong_trend_entry'

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        简化退出逻辑 - 主要依靠ROI和止损
        """
        # 只有在明显趋势反转时才退出
        conditions = []

        # 条件1: 短期均线明显跌破中期均线
        trend_broken = (
                (dataframe['ema_9'] < dataframe['ema_21']) &
                (dataframe['close'] < dataframe['ema_21'] * 0.98)  # 价格跌破EMA21 2%
        )
        conditions.append(trend_broken)

        # 条件2: RSI严重超买
        rsi_extreme = dataframe['rsi'] > 80
        conditions.append(rsi_extreme)

        # 条件3: 趋势强度明显减弱
        adx_weak = dataframe['adx'] < 15
        conditions.append(adx_weak)

        # 需要多个条件同时满足才退出
        dataframe.loc[
            (trend_broken & rsi_extreme) |  # 趋势破且RSI超买
            (trend_broken & adx_weak) |     # 趋势破且ADX弱
            (rsi_extreme & adx_weak),       # RSI超买且ADX弱
            'exit_long'
        ] = 1

        return dataframe

    def custom_stake_amount(self, pair: str, current_time, current_rate: float,
                            proposed_stake: float, min_stake: float, max_stake: float,
                            leverage: float, entry_tag: str, side: str, **kwargs) -> float:
        """
        动态仓位管理
        """
        # 根据波动率调整仓位
        return 500  # 固定100USDT