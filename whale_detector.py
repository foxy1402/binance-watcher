"""
Whale Detection & Smart Money Tracking
Detects large transactions, unusual volumes, and smart money movements
"""

import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import config
import indicators as ind


# Whale thresholds (USD values)
WHALE_THRESHOLDS = {
    'small_whale': 500_000,      # $500K
    'medium_whale': 1_000_000,   # $1M
    'large_whale': 5_000_000,    # $5M
    'mega_whale': 10_000_000     # $10M
}

# Volume anomaly threshold (Z-score)
VOLUME_ANOMALY_THRESHOLD = 2.5  # ~99% confidence


def classify_whale_size(usd_value: float) -> str:
    """
    Classify transaction size
    
    Args:
        usd_value: Transaction value in USD
    
    Returns:
        Whale classification
    """
    if usd_value >= WHALE_THRESHOLDS['mega_whale']:
        return 'mega_whale'
    elif usd_value >= WHALE_THRESHOLDS['large_whale']:
        return 'large_whale'
    elif usd_value >= WHALE_THRESHOLDS['medium_whale']:
        return 'medium_whale'
    elif usd_value >= WHALE_THRESHOLDS['small_whale']:
        return 'small_whale'
    return None


def detect_whale_trades(candle_data: Dict, historical_data: List[Dict]) -> List[Dict]:
    """
    Detect whale trades from aggregated daily candle data
    
    Args:
        candle_data: Single day's candle data
        historical_data: Historical candles for comparison (last 30 days)
    
    Returns:
        List of whale trade alerts
    """
    alerts = []
    
    # Check for large absolute volumes
    buy_usd = candle_data.get('buy_volume_usd', 0)
    sell_usd = candle_data.get('sell_volume_usd', 0)
    net_usd = candle_data.get('net_volume_usd', 0)
    
    # Detect large buy pressure
    buy_class = classify_whale_size(buy_usd)
    if buy_class:
        alerts.append({
            'type': 'whale_buy',
            'coin': candle_data['coin'],
            'date': candle_data['date'],
            'size_class': buy_class,
            'value_usd': buy_usd,
            'volume': candle_data['buy_volume'],
            'price': candle_data['close_price'],
            'description': f"Large buy pressure detected: ${buy_usd:,.0f}"
        })
    
    # Detect large sell pressure
    sell_class = classify_whale_size(sell_usd)
    if sell_class:
        alerts.append({
            'type': 'whale_sell',
            'coin': candle_data['coin'],
            'date': candle_data['date'],
            'size_class': sell_class,
            'value_usd': sell_usd,
            'volume': candle_data['sell_volume'],
            'price': candle_data['close_price'],
            'description': f"Large sell pressure detected: ${sell_usd:,.0f}"
        })
    
    # Detect extreme net accumulation/distribution
    net_abs = abs(net_usd)
    net_class = classify_whale_size(net_abs)
    if net_class:
        direction = 'accumulation' if net_usd > 0 else 'distribution'
        alerts.append({
            'type': f'whale_{direction}',
            'coin': candle_data['coin'],
            'date': candle_data['date'],
            'size_class': net_class,
            'value_usd': net_abs,
            'volume': abs(candle_data['net_volume']),
            'price': candle_data['close_price'],
            'description': f"Strong {direction}: ${net_abs:,.0f} net {direction}"
        })
    
    return alerts


def detect_volume_anomalies(candle_data: Dict, historical_data: List[Dict]) -> List[Dict]:
    """
    Detect unusual volume spikes using statistical analysis
    
    Args:
        candle_data: Current day's data
        historical_data: Historical data for baseline (20-30 days)
    
    Returns:
        List of volume anomaly alerts
    """
    alerts = []
    
    if len(historical_data) < 10:
        return alerts
    
    # Get historical volumes
    hist_total_volumes = [d['total_volume'] for d in historical_data]
    hist_buy_volumes = [d['buy_volume'] for d in historical_data]
    hist_sell_volumes = [d['sell_volume'] for d in historical_data]
    
    # Check total volume anomaly
    is_anomaly, zscore = ind.detect_volume_anomaly(
        candle_data['total_volume'],
        hist_total_volumes,
        VOLUME_ANOMALY_THRESHOLD
    )
    
    if is_anomaly:
        alerts.append({
            'type': 'volume_spike',
            'coin': candle_data['coin'],
            'date': candle_data['date'],
            'zscore': round(zscore, 2),
            'volume': candle_data['total_volume'],
            'avg_volume': sum(hist_total_volumes) / len(hist_total_volumes),
            'price': candle_data['close_price'],
            'description': f"Unusual volume spike detected (Z-score: {zscore:.2f})"
        })
    
    # Check buy volume spike
    is_buy_anomaly, buy_zscore = ind.detect_volume_anomaly(
        candle_data['buy_volume'],
        hist_buy_volumes,
        VOLUME_ANOMALY_THRESHOLD
    )
    
    if is_buy_anomaly and buy_zscore > 0:
        alerts.append({
            'type': 'buy_volume_spike',
            'coin': candle_data['coin'],
            'date': candle_data['date'],
            'zscore': round(buy_zscore, 2),
            'volume': candle_data['buy_volume'],
            'value_usd': candle_data['buy_volume_usd'],
            'price': candle_data['close_price'],
            'description': f"Unusual buying activity (Z-score: {buy_zscore:.2f})"
        })
    
    # Check sell volume spike
    is_sell_anomaly, sell_zscore = ind.detect_volume_anomaly(
        candle_data['sell_volume'],
        hist_sell_volumes,
        VOLUME_ANOMALY_THRESHOLD
    )
    
    if is_sell_anomaly and sell_zscore > 0:
        alerts.append({
            'type': 'sell_volume_spike',
            'coin': candle_data['coin'],
            'date': candle_data['date'],
            'zscore': round(sell_zscore, 2),
            'volume': candle_data['sell_volume'],
            'value_usd': candle_data['sell_volume_usd'],
            'price': candle_data['close_price'],
            'description': f"Unusual selling activity (Z-score: {sell_zscore:.2f})"
        })
    
    return alerts


def detect_divergence_signals(data_series: List[Dict]) -> List[Dict]:
    """
    Detect price-volume divergence patterns
    
    Args:
        data_series: List of recent candles (at least 5-10 days)
    
    Returns:
        List of divergence alerts
    """
    alerts = []
    
    if len(data_series) < 5:
        return alerts
    
    prices = [d['close_price'] for d in data_series]
    net_volumes = [d['net_volume'] for d in data_series]
    
    # Get last divergence signal
    signals = ind.calculate_net_volume_divergence(prices, net_volumes)
    
    if signals[-1] == 'bullish':
        alerts.append({
            'type': 'bullish_divergence',
            'coin': data_series[-1]['coin'],
            'date': data_series[-1]['date'],
            'price': data_series[-1]['close_price'],
            'net_volume': data_series[-1]['net_volume'],
            'description': 'Bullish divergence: Price declining but accumulation detected'
        })
    elif signals[-1] == 'bearish':
        alerts.append({
            'type': 'bearish_divergence',
            'coin': data_series[-1]['coin'],
            'date': data_series[-1]['date'],
            'price': data_series[-1]['close_price'],
            'net_volume': data_series[-1]['net_volume'],
            'description': 'Bearish divergence: Price rising but distribution detected'
        })
    
    return alerts


def detect_rsi_extremes(data_series: List[Dict]) -> List[Dict]:
    """
    Detect RSI overbought/oversold conditions
    
    Args:
        data_series: List of candles with RSI calculated
    
    Returns:
        List of RSI alerts
    """
    alerts = []
    
    if len(data_series) < 2:
        return alerts
    
    current = data_series[-1]
    rsi = current.get('rsi')
    
    if rsi is None:
        return alerts
    
    # Oversold (potential buy signal)
    if rsi < 30:
        alerts.append({
            'type': 'rsi_oversold',
            'coin': current['coin'],
            'date': current['date'],
            'rsi': round(rsi, 2),
            'price': current['close_price'],
            'description': f'RSI oversold at {rsi:.1f} - potential buy zone'
        })
    
    # Overbought (potential sell signal)
    elif rsi > 70:
        alerts.append({
            'type': 'rsi_overbought',
            'coin': current['coin'],
            'date': current['date'],
            'rsi': round(rsi, 2),
            'price': current['close_price'],
            'description': f'RSI overbought at {rsi:.1f} - potential sell zone'
        })
    
    return alerts


def detect_all_smart_actions(current_data: Dict, historical_data: List[Dict]) -> List[Dict]:
    """
    Run all detection algorithms and return combined alerts
    
    Args:
        current_data: Latest candle data
        historical_data: Historical data for context (30+ days recommended)
    
    Returns:
        List of all detected smart action alerts
    """
    all_alerts = []
    
    # Whale trade detection
    whale_alerts = detect_whale_trades(current_data, historical_data)
    all_alerts.extend(whale_alerts)
    
    # Volume anomaly detection
    volume_alerts = detect_volume_anomalies(current_data, historical_data)
    all_alerts.extend(volume_alerts)
    
    # Divergence detection (needs multiple days)
    if len(historical_data) >= 5:
        recent_data = historical_data[-5:] + [current_data]
        divergence_alerts = detect_divergence_signals(recent_data)
        all_alerts.extend(divergence_alerts)
    
    # RSI extreme detection (needs data with RSI)
    if current_data.get('rsi') is not None:
        rsi_alerts = detect_rsi_extremes([current_data])
        all_alerts.extend(rsi_alerts)
    
    # Add metadata to all alerts
    for alert in all_alerts:
        if 'timestamp' not in alert:
            alert['timestamp'] = datetime.now().isoformat()
        if 'severity' not in alert:
            # Determine severity based on type and values
            alert['severity'] = calculate_alert_severity(alert)
    
    return all_alerts


def calculate_alert_severity(alert: Dict) -> str:
    """
    Calculate severity level for an alert
    
    Args:
        alert: Alert dictionary
    
    Returns:
        Severity level: 'critical', 'high', 'medium', 'low'
    """
    alert_type = alert.get('type', '')
    
    # Mega whale = critical
    if alert.get('size_class') == 'mega_whale':
        return 'critical'
    
    # Large whale or very high Z-score = high
    if alert.get('size_class') == 'large_whale':
        return 'high'
    
    zscore = abs(alert.get('zscore', 0))
    if zscore > 3.5:
        return 'critical'
    elif zscore > 3.0:
        return 'high'
    
    # Divergence signals = medium
    if 'divergence' in alert_type:
        return 'medium'
    
    # Medium whale or high Z-score = medium
    if alert.get('size_class') == 'medium_whale':
        return 'medium'
    elif zscore > 2.5:
        return 'medium'
    
    # Everything else = low
    return 'low'


if __name__ == "__main__":
    # Test whale detection
    test_current = {
        'coin': 'BTC',
        'date': '2024-01-15',
        'close_price': 45000,
        'total_volume': 50000,
        'buy_volume': 30000,
        'sell_volume': 20000,
        'net_volume': 10000,
        'buy_volume_usd': 1_350_000_000,
        'sell_volume_usd': 900_000_000,
        'net_volume_usd': 450_000_000
    }
    
    test_historical = [
        {
            'coin': 'BTC',
            'date': f'2024-01-{i:02d}',
            'close_price': 44000 + i * 100,
            'total_volume': 25000 + i * 100,
            'buy_volume': 13000,
            'sell_volume': 12000,
            'net_volume': 1000,
            'buy_volume_usd': 572_000_000,
            'sell_volume_usd': 528_000_000,
            'net_volume_usd': 44_000_000
        }
        for i in range(1, 15)
    ]
    
    alerts = detect_all_smart_actions(test_current, test_historical)
    
    print(f"Detected {len(alerts)} smart action alerts:")
    for alert in alerts:
        print(f"  [{alert['severity'].upper()}] {alert['type']}: {alert['description']}")
