"""
Futures Market Analysis Module
Tracks futures premium, funding rates, and open interest
Detects arbitrage opportunities and market sentiment
"""

import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import config


# Binance Futures API
FUTURES_BASE_URL = "https://fapi.binance.com/fapi/v1"

# Rate limiting
REQUEST_DELAY = 0.1


def get_session() -> requests.Session:
    """Create a requests session with proxy if configured"""
    session = requests.Session()
    
    proxy_url = config.get_proxy_url()
    if proxy_url:
        session.proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
    
    return session


def get_futures_price(symbol: str = "BTCUSDT", session: Optional[requests.Session] = None) -> Optional[float]:
    """
    Get current futures mark price
    
    Args:
        symbol: Futures symbol (e.g., BTCUSDT)
        session: Optional requests session
    
    Returns:
        Current mark price or None
    """
    if session is None:
        session = get_session()
    
    try:
        response = session.get(f"{FUTURES_BASE_URL}/premiumIndex", params={"symbol": symbol}, timeout=10)
        response.raise_for_status()
        data = response.json()
        return float(data['markPrice'])
    except Exception as e:
        print(f"Error fetching futures price for {symbol}: {e}")
        return None


def get_funding_rate(symbol: str = "BTCUSDT", session: Optional[requests.Session] = None) -> Optional[Dict]:
    """
    Get current funding rate
    
    Args:
        symbol: Futures symbol
        session: Optional requests session
    
    Returns:
        Dictionary with funding rate info
    """
    if session is None:
        session = get_session()
    
    try:
        response = session.get(f"{FUTURES_BASE_URL}/premiumIndex", params={"symbol": symbol}, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        return {
            'symbol': symbol,
            'funding_rate': float(data['lastFundingRate']),
            'next_funding_time': data['nextFundingTime'],
            'mark_price': float(data['markPrice']),
            'index_price': float(data['indexPrice']),
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Error fetching funding rate for {symbol}: {e}")
        return None


def get_open_interest(symbol: str = "BTCUSDT", session: Optional[requests.Session] = None) -> Optional[Dict]:
    """
    Get open interest statistics
    
    Args:
        symbol: Futures symbol
        session: Optional requests session
    
    Returns:
        Open interest data
    """
    if session is None:
        session = get_session()
    
    try:
        response = session.get(f"{FUTURES_BASE_URL}/openInterest", params={"symbol": symbol}, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        return {
            'symbol': symbol,
            'open_interest': float(data['openInterest']),
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Error fetching open interest for {symbol}: {e}")
        return None


def calculate_futures_premium(spot_price: float, futures_price: float) -> float:
    """
    Calculate futures premium/discount percentage
    
    Args:
        spot_price: Spot market price
        futures_price: Futures mark price
    
    Returns:
        Premium percentage (positive = premium, negative = discount)
    """
    if spot_price == 0:
        return 0
    
    return ((futures_price - spot_price) / spot_price) * 100


def get_futures_metrics(coin: str = "BTC", spot_price: Optional[float] = None) -> Dict:
    """
    Get comprehensive futures market metrics
    
    Args:
        coin: Base coin (BTC, ETH, etc.)
        spot_price: Current spot price (fetched if not provided)
    
    Returns:
        Dictionary with all futures metrics
    """
    symbol = f"{coin}USDT"
    session = get_session()
    
    # Get futures data
    funding_data = get_funding_rate(symbol, session)
    oi_data = get_open_interest(symbol, session)
    
    if not funding_data:
        return None
    
    futures_price = funding_data['mark_price']
    
    # Use provided spot price or futures index price as proxy
    if spot_price is None:
        spot_price = funding_data.get('index_price', futures_price)
    
    premium = calculate_futures_premium(spot_price, futures_price)
    
    metrics = {
        'coin': coin,
        'symbol': symbol,
        'spot_price': spot_price,
        'futures_price': futures_price,
        'premium_pct': round(premium, 4),
        'funding_rate': funding_data['funding_rate'],
        'funding_rate_annualized': round(funding_data['funding_rate'] * 3 * 365 * 100, 2),  # 8h periods
        'next_funding_time': funding_data['next_funding_time'],
        'open_interest': oi_data['open_interest'] if oi_data else None,
        'timestamp': datetime.now().isoformat()
    }
    
    return metrics


def detect_futures_anomalies(metrics: Dict) -> List[Dict]:
    """
    Detect unusual futures market conditions
    
    Args:
        metrics: Futures metrics dictionary
    
    Returns:
        List of anomaly alerts
    """
    alerts = []
    
    premium = metrics.get('premium_pct', 0)
    funding_rate = metrics.get('funding_rate', 0)
    funding_annualized = metrics.get('funding_rate_annualized', 0)
    
    # Extreme premium (potential overheating)
    if premium > 0.5:  # >0.5% premium
        alerts.append({
            'type': 'high_futures_premium',
            'coin': metrics['coin'],
            'severity': 'high' if premium > 1.0 else 'medium',
            'premium_pct': premium,
            'description': f"High futures premium: {premium:.2f}% - Market overheating"
        })
    
    # Extreme discount (potential fear)
    elif premium < -0.5:  # <-0.5% discount
        alerts.append({
            'type': 'futures_discount',
            'coin': metrics['coin'],
            'severity': 'high' if premium < -1.0 else 'medium',
            'premium_pct': premium,
            'description': f"Futures trading at discount: {premium:.2f}% - Market fear"
        })
    
    # Extreme funding rate (positive)
    if funding_annualized > 50:  # >50% annualized
        alerts.append({
            'type': 'extreme_funding_rate',
            'coin': metrics['coin'],
            'severity': 'critical' if funding_annualized > 100 else 'high',
            'funding_rate': funding_rate,
            'funding_annualized': funding_annualized,
            'description': f"Extreme positive funding: {funding_annualized:.1f}% annualized - Longs paying shorts heavily"
        })
    
    # Extreme funding rate (negative)
    elif funding_annualized < -50:  # <-50% annualized
        alerts.append({
            'type': 'extreme_negative_funding',
            'coin': metrics['coin'],
            'severity': 'critical' if funding_annualized < -100 else 'high',
            'funding_rate': funding_rate,
            'funding_annualized': funding_annualized,
            'description': f"Extreme negative funding: {funding_annualized:.1f}% annualized - Shorts paying longs heavily"
        })
    
    # Backwardation (futures < spot) with high negative funding = bullish
    if premium < -0.3 and funding_rate < -0.01:
        alerts.append({
            'type': 'backwardation_signal',
            'coin': metrics['coin'],
            'severity': 'medium',
            'premium_pct': premium,
            'funding_rate': funding_rate,
            'description': f"Backwardation + negative funding - Potential bullish setup"
        })
    
    # Contango (futures > spot) with high positive funding = bearish
    elif premium > 0.3 and funding_rate > 0.01:
        alerts.append({
            'type': 'contango_warning',
            'coin': metrics['coin'],
            'severity': 'medium',
            'premium_pct': premium,
            'funding_rate': funding_rate,
            'description': f"High contango + positive funding - Potential bearish setup"
        })
    
    # Add timestamp to all alerts
    for alert in alerts:
        alert['timestamp'] = metrics['timestamp']
        alert['spot_price'] = metrics['spot_price']
        alert['futures_price'] = metrics['futures_price']
    
    return alerts


def get_liquidation_estimates(symbol: str = "BTCUSDT", 
                               session: Optional[requests.Session] = None) -> Optional[Dict]:
    """
    Estimate liquidation zones using leverage and OI data
    Note: This is estimated data, not actual liquidations
    
    Args:
        symbol: Futures symbol
        session: Optional requests session
    
    Returns:
        Liquidation estimates
    """
    if session is None:
        session = get_session()
    
    try:
        # Get current price and OI
        funding_data = get_funding_rate(symbol, session)
        if not funding_data:
            return None
        
        mark_price = funding_data['mark_price']
        
        # Estimate liquidation zones (simplified)
        # Assume average leverage of 10x
        avg_leverage = 10
        liquidation_threshold = 1 / avg_leverage  # 10% move
        
        # Long liquidation (price drops)
        long_liq_price = mark_price * (1 - liquidation_threshold)
        
        # Short liquidation (price rises)
        short_liq_price = mark_price * (1 + liquidation_threshold)
        
        return {
            'symbol': symbol,
            'current_price': mark_price,
            'long_liquidation_zone': round(long_liq_price, 2),
            'short_liquidation_zone': round(short_liq_price, 2),
            'avg_leverage_assumed': avg_leverage,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Error estimating liquidations for {symbol}: {e}")
        return None


if __name__ == "__main__":
    # Test futures tracking
    print("Testing Futures Market Analysis...")
    print(f"Proxy: {config.get_proxy_url() or 'None'}")
    
    # Test BTC metrics
    print("\nBTC Futures Metrics:")
    metrics = get_futures_metrics("BTC")
    if metrics:
        print(f"  Spot: ${metrics['spot_price']:,.2f}")
        print(f"  Futures: ${metrics['futures_price']:,.2f}")
        print(f"  Premium: {metrics['premium_pct']:.4f}%")
        print(f"  Funding Rate: {metrics['funding_rate']:.6f} ({metrics['funding_rate_annualized']:.2f}% annualized)")
        print(f"  Open Interest: {metrics['open_interest']:,.0f}")
        
        # Check for anomalies
        alerts = detect_futures_anomalies(metrics)
        if alerts:
            print(f"\n  Anomalies detected:")
            for alert in alerts:
                print(f"    [{alert['severity'].upper()}] {alert['type']}: {alert['description']}")
        else:
            print(f"\n  No anomalies detected")
    
    # Test liquidation estimates
    print("\nLiquidation Estimates:")
    liq_data = get_liquidation_estimates("BTCUSDT")
    if liq_data:
        print(f"  Current: ${liq_data['current_price']:,.2f}")
        print(f"  Long Liq Zone: ${liq_data['long_liquidation_zone']:,.2f}")
        print(f"  Short Liq Zone: ${liq_data['short_liquidation_zone']:,.2f}")
