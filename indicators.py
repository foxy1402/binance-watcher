"""
Technical Indicators & Statistical Analysis Module
Provides VWAP, RSI, MACD, Bollinger Bands, Z-Score analysis
"""

import math
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta


def calculate_vwap(data: List[Dict]) -> List[Dict]:
    """
    Calculate Volume Weighted Average Price
    
    Args:
        data: List of candles with 'high', 'low', 'close', 'total_volume'
    
    Returns:
        List with added 'vwap' field
    """
    for candle in data:
        typical_price = (candle['high_price'] + candle['low_price'] + candle['close_price']) / 3
        candle['typical_price'] = typical_price
        candle['price_volume'] = typical_price * candle['total_volume']
    
    cumulative_pv = 0
    cumulative_volume = 0
    
    for candle in data:
        cumulative_pv += candle['price_volume']
        cumulative_volume += candle['total_volume']
        candle['vwap'] = cumulative_pv / cumulative_volume if cumulative_volume > 0 else candle['close_price']
    
    return data


def calculate_rsi(prices: List[float], period: int = 14) -> List[Optional[float]]:
    """
    Calculate Relative Strength Index
    
    Args:
        prices: List of closing prices
        period: RSI period (default 14)
    
    Returns:
        List of RSI values (None for initial values)
    """
    if len(prices) < period + 1:
        return [None] * len(prices)
    
    rsi_values = [None] * period
    
    # Calculate initial average gain and loss
    gains = []
    losses = []
    
    for i in range(1, period + 1):
        change = prices[i] - prices[i - 1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    
    # Calculate first RSI
    if avg_loss == 0:
        rsi_values.append(100)
    else:
        rs = avg_gain / avg_loss
        rsi_values.append(100 - (100 / (1 + rs)))
    
    # Calculate subsequent RSI values using smoothed averages
    for i in range(period + 1, len(prices)):
        change = prices[i] - prices[i - 1]
        
        if change > 0:
            gain = change
            loss = 0
        else:
            gain = 0
            loss = abs(change)
        
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        
        if avg_loss == 0:
            rsi_values.append(100)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - (100 / (1 + rs)))
    
    return rsi_values


def calculate_macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, List[Optional[float]]]:
    """
    Calculate MACD (Moving Average Convergence Divergence)
    
    Args:
        prices: List of closing prices
        fast: Fast EMA period (default 12)
        slow: Slow EMA period (default 26)
        signal: Signal line period (default 9)
    
    Returns:
        Dictionary with 'macd', 'signal', 'histogram' lists
    """
    def ema(values: List[float], period: int) -> List[Optional[float]]:
        """Calculate Exponential Moving Average"""
        ema_values = [None] * (period - 1)
        multiplier = 2 / (period + 1)
        
        # Initial SMA
        ema_values.append(sum(values[:period]) / period)
        
        # Calculate EMA
        for i in range(period, len(values)):
            ema_val = (values[i] - ema_values[-1]) * multiplier + ema_values[-1]
            ema_values.append(ema_val)
        
        return ema_values
    
    fast_ema = ema(prices, fast)
    slow_ema = ema(prices, slow)
    
    # Calculate MACD line
    macd_line = []
    for i in range(len(prices)):
        if fast_ema[i] is not None and slow_ema[i] is not None:
            macd_line.append(fast_ema[i] - slow_ema[i])
        else:
            macd_line.append(None)
    
    # Calculate signal line (EMA of MACD)
    macd_valid = [x for x in macd_line if x is not None]
    if len(macd_valid) >= signal:
        signal_ema = ema(macd_valid, signal)
        # Pad with None to match length
        signal_line = [None] * (len(macd_line) - len(signal_ema)) + signal_ema
    else:
        signal_line = [None] * len(macd_line)
    
    # Calculate histogram
    histogram = []
    for i in range(len(macd_line)):
        if macd_line[i] is not None and signal_line[i] is not None:
            histogram.append(macd_line[i] - signal_line[i])
        else:
            histogram.append(None)
    
    return {
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    }


def calculate_bollinger_bands(prices: List[float], period: int = 20, std_dev: float = 2.0) -> Dict[str, List[Optional[float]]]:
    """
    Calculate Bollinger Bands
    
    Args:
        prices: List of closing prices
        period: Moving average period (default 20)
        std_dev: Number of standard deviations (default 2.0)
    
    Returns:
        Dictionary with 'upper', 'middle', 'lower' bands
    """
    upper = [None] * (period - 1)
    middle = [None] * (period - 1)
    lower = [None] * (period - 1)
    
    for i in range(period - 1, len(prices)):
        window = prices[i - period + 1:i + 1]
        sma = sum(window) / period
        variance = sum((x - sma) ** 2 for x in window) / period
        std = math.sqrt(variance)
        
        middle.append(sma)
        upper.append(sma + (std_dev * std))
        lower.append(sma - (std_dev * std))
    
    return {
        'upper': upper,
        'middle': middle,
        'lower': lower
    }


def calculate_volume_zscore(volumes: List[float], window: int = 20) -> List[Optional[float]]:
    """
    Calculate Z-Score for volume to detect anomalies
    
    Args:
        volumes: List of volume values
        window: Rolling window size (default 20)
    
    Returns:
        List of Z-scores
    """
    zscores = [None] * (window - 1)
    
    for i in range(window - 1, len(volumes)):
        window_data = volumes[i - window + 1:i + 1]
        mean = sum(window_data) / window
        variance = sum((x - mean) ** 2 for x in window_data) / window
        std = math.sqrt(variance)
        
        if std > 0:
            zscore = (volumes[i] - mean) / std
            zscores.append(zscore)
        else:
            zscores.append(0)
    
    return zscores


def detect_volume_anomaly(volume: float, historical_volumes: List[float], 
                          threshold: float = 2.5) -> Tuple[bool, float]:
    """
    Detect if current volume is anomalous
    
    Args:
        volume: Current volume
        historical_volumes: Historical volume data (last 20-30 days)
        threshold: Z-score threshold (default 2.5 = ~99% confidence)
    
    Returns:
        Tuple of (is_anomaly, z_score)
    """
    if len(historical_volumes) < 10:
        return False, 0.0
    
    mean = sum(historical_volumes) / len(historical_volumes)
    variance = sum((x - mean) ** 2 for x in historical_volumes) / len(historical_volumes)
    std = math.sqrt(variance)
    
    if std == 0:
        return False, 0.0
    
    zscore = (volume - mean) / std
    is_anomaly = abs(zscore) > threshold
    
    return is_anomaly, zscore


def calculate_net_volume_divergence(prices: List[float], net_volumes: List[float]) -> List[Optional[str]]:
    """
    Detect price-volume divergence (bullish/bearish signals)
    
    Args:
        prices: List of closing prices
        net_volumes: List of net volume values
    
    Returns:
        List of divergence signals ('bullish', 'bearish', or None)
    """
    if len(prices) < 5 or len(net_volumes) < 5:
        return [None] * len(prices)
    
    signals = [None] * 4  # Not enough data for first few points
    
    for i in range(4, len(prices)):
        # Look at last 5 periods
        price_trend = prices[i] - prices[i - 4]
        volume_trend = sum(net_volumes[i - 4:i + 1])
        
        # Bullish divergence: price down but accumulation (positive net volume)
        if price_trend < 0 and volume_trend > 0:
            signals.append('bullish')
        # Bearish divergence: price up but distribution (negative net volume)
        elif price_trend > 0 and volume_trend < 0:
            signals.append('bearish')
        else:
            signals.append(None)
    
    return signals


def calculate_obv(closes: List[float], volumes: List[float]) -> List[float]:
    """
    Calculate On-Balance Volume
    
    Args:
        closes: List of closing prices
        volumes: List of volumes
    
    Returns:
        List of OBV values
    """
    obv = [volumes[0]]
    
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            obv.append(obv[-1] + volumes[i])
        elif closes[i] < closes[i - 1]:
            obv.append(obv[-1] - volumes[i])
        else:
            obv.append(obv[-1])
    
    return obv


def enhance_volume_data_with_indicators(data: List[Dict]) -> List[Dict]:
    """
    Add all technical indicators to volume data
    
    Args:
        data: List of volume data dictionaries (sorted by date ascending)
    
    Returns:
        Enhanced data with indicators
    """
    if not data:
        return data
    
    # Extract price and volume series
    closes = [d['close_price'] for d in data]
    volumes = [d['total_volume'] for d in data]
    net_volumes = [d['net_volume'] for d in data]
    
    # Calculate indicators
    data = calculate_vwap(data)
    rsi_values = calculate_rsi(closes)
    macd_data = calculate_macd(closes)
    bb_data = calculate_bollinger_bands(closes)
    volume_zscores = calculate_volume_zscore(volumes)
    divergence_signals = calculate_net_volume_divergence(closes, net_volumes)
    obv_values = calculate_obv(closes, volumes)
    
    # Add to data
    for i, candle in enumerate(data):
        candle['rsi'] = rsi_values[i]
        candle['macd'] = macd_data['macd'][i]
        candle['macd_signal'] = macd_data['signal'][i]
        candle['macd_histogram'] = macd_data['histogram'][i]
        candle['bb_upper'] = bb_data['upper'][i]
        candle['bb_middle'] = bb_data['middle'][i]
        candle['bb_lower'] = bb_data['lower'][i]
        candle['volume_zscore'] = volume_zscores[i]
        candle['divergence_signal'] = divergence_signals[i]
        candle['obv'] = obv_values[i]
    
    return data


if __name__ == "__main__":
    # Test indicators
    test_data = [
        {'date': '2024-01-01', 'open_price': 42000, 'high_price': 43000, 'low_price': 41500, 'close_price': 42500, 'total_volume': 1000, 'net_volume': 100},
        {'date': '2024-01-02', 'open_price': 42500, 'high_price': 44000, 'low_price': 42000, 'close_price': 43500, 'total_volume': 1200, 'net_volume': 300},
        {'date': '2024-01-03', 'open_price': 43500, 'high_price': 45000, 'low_price': 43000, 'close_price': 44000, 'total_volume': 1500, 'net_volume': 500},
    ]
    
    enhanced = enhance_volume_data_with_indicators(test_data)
    for candle in enhanced:
        print(f"{candle['date']}: VWAP={candle.get('vwap', 0):.2f}, RSI={candle.get('rsi')}, Volume Z-Score={candle.get('volume_zscore')}")
