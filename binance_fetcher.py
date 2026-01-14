"""
Binance API client for fetching market volume data
Supports fetching all historical data with pagination
Includes proxy support and multi-pair aggregation
"""

import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import config

# Binance API base URL
BASE_URL = "https://api.binance.com/api/v3"

# Rate limiting - Binance allows 1200 requests per minute
REQUEST_DELAY = 0.1  # 100ms between requests

# Maximum candles per request
MAX_CANDLES = 1000


def get_session() -> requests.Session:
    """Create a requests session with proxy if configured"""
    session = requests.Session()
    
    proxy_url = config.get_proxy_url()
    if proxy_url:
        # Support both HTTP and SOCKS5 proxies
        if proxy_url.startswith('socks'):
            # For SOCKS5, we need PySocks
            session.proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
        else:
            session.proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
        print(f"Using proxy: {proxy_url.split('@')[-1] if '@' in proxy_url else proxy_url}")
    
    return session


def fetch_klines(symbol: str = "BTCUSDT", interval: str = "1d", 
                 start_time: Optional[int] = None, end_time: Optional[int] = None,
                 limit: int = MAX_CANDLES, session: Optional[requests.Session] = None) -> List:
    """
    Fetch kline/candlestick data from Binance
    
    Args:
        symbol: Trading pair (e.g., BTCUSDT)
        interval: Candlestick interval (1d, 1w, 1M, etc.)
        start_time: Start time in milliseconds
        end_time: End time in milliseconds
        limit: Number of candles (max 1000)
        session: Optional requests session with proxy
    
    Returns:
        List of kline data
    """
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": min(limit, MAX_CANDLES)
    }
    
    if start_time:
        params["startTime"] = start_time
    if end_time:
        params["endTime"] = end_time
    
    if session is None:
        session = get_session()
    
    try:
        response = session.get(f"{BASE_URL}/klines", params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching klines for {symbol}: {e}")
        return []


def parse_kline(candle: List, coin: str, symbol: str) -> Dict:
    """
    Parse a single kline candle into a structured dictionary
    
    Binance Kline format:
    [0] Open time (ms)
    [1] Open price
    [2] High price
    [3] Low price
    [4] Close price
    [5] Volume (base asset)
    [6] Close time (ms)
    [7] Quote asset volume
    [8] Number of trades
    [9] Taker buy base asset volume
    [10] Taker buy quote asset volume
    [11] Ignore
    """
    timestamp = candle[0]
    open_price = float(candle[1])
    high_price = float(candle[2])
    low_price = float(candle[3])
    close_price = float(candle[4])
    total_volume = float(candle[5])
    taker_buy_volume = float(candle[9])
    
    # Calculate sell volume
    taker_sell_volume = total_volume - taker_buy_volume
    
    # Net volume (positive = more buying, negative = more selling)
    net_volume = taker_buy_volume - taker_sell_volume
    
    # USD calculations using average price
    avg_price = (open_price + close_price) / 2
    buy_volume_usd = taker_buy_volume * avg_price
    sell_volume_usd = taker_sell_volume * avg_price
    net_volume_usd = net_volume * avg_price
    
    # Price change percentage
    price_change_pct = ((close_price - open_price) / open_price) * 100 if open_price > 0 else 0
    
    # Convert timestamp to date string
    date_str = datetime.utcfromtimestamp(timestamp / 1000).strftime('%Y-%m-%d')
    
    return {
        'coin': coin,  # Base coin (BTC, ETH, etc.)
        'symbol': symbol,  # Original trading pair
        'date': date_str,
        'open_price': open_price,
        'close_price': close_price,
        'high_price': high_price,
        'low_price': low_price,
        'total_volume': total_volume,
        'buy_volume': taker_buy_volume,
        'sell_volume': taker_sell_volume,
        'net_volume': net_volume,
        'buy_volume_usd': buy_volume_usd,
        'sell_volume_usd': sell_volume_usd,
        'net_volume_usd': net_volume_usd,
        'price_change_pct': price_change_pct
    }


def fetch_all_historical_data(symbol: str = "BTCUSDT", coin: str = "BTC",
                               interval: str = "1d",
                               start_date: Optional[str] = None,
                               progress_callback=None) -> List[Dict]:
    """
    Fetch ALL available historical data from Binance using pagination
    
    Args:
        symbol: Trading pair
        coin: Base coin name (for aggregation)
        interval: Candlestick interval
        start_date: Optional start date (YYYY-MM-DD format), defaults to earliest available
        progress_callback: Optional callback function(fetched_count, message)
    
    Returns:
        List of parsed volume data dictionaries
    """
    all_data = []
    session = get_session()
    
    # Start from the beginning of time if not specified
    # Binance BTC/USDT data starts from 2017-08-17
    if start_date:
        start_time = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
    else:
        # Default to start of Binance trading (Aug 17, 2017)
        # This ensures we paginate forward through all history
        start_time = int(datetime(2017, 8, 17).timestamp() * 1000)
    
    end_time = int(datetime.now().timestamp() * 1000)
    
    current_start = start_time
    batch_count = 0
    
    while True:
        if progress_callback:
            progress_callback(len(all_data), f"Fetching {symbol} batch {batch_count + 1}...")
        
        klines = fetch_klines(
            symbol=symbol,
            interval=interval,
            start_time=current_start,
            end_time=end_time,
            limit=MAX_CANDLES,
            session=session
        )
        
        if not klines:
            break
        
        # Parse all candles
        for candle in klines:
            parsed = parse_kline(candle, coin, symbol)
            all_data.append(parsed)
        
        batch_count += 1
        
        # Check if we got less than max, meaning we've reached the end
        if len(klines) < MAX_CANDLES:
            break
        
        # Move start time to after the last candle
        last_timestamp = klines[-1][0]
        current_start = last_timestamp + 1
        
        # Rate limiting
        time.sleep(REQUEST_DELAY)
        
        # Safety check - prevent infinite loops
        if batch_count > 100:  # ~100k candles max
            print("Warning: Reached maximum batch limit")
            break
    
    if progress_callback:
        progress_callback(len(all_data), f"Completed {symbol}! Fetched {len(all_data)} records.")
    
    return all_data


def fetch_recent_data(symbol: str = "BTCUSDT", coin: str = "BTC", days: int = 30) -> List[Dict]:
    """
    Fetch recent data for quick updates
    
    Args:
        symbol: Trading pair
        coin: Base coin name
        days: Number of days to fetch
    
    Returns:
        List of parsed volume data
    """
    session = get_session()
    klines = fetch_klines(symbol=symbol, interval="1d", limit=min(days, MAX_CANDLES), session=session)
    return [parse_kline(candle, coin, symbol) for candle in klines]


def fetch_coin_data(coin: str, days: Optional[int] = None, 
                    start_date: Optional[str] = None,
                    progress_callback=None) -> List[Dict]:
    """
    Fetch data for a coin from both USDT and USDC pairs
    
    Args:
        coin: Base coin (BTC, ETH, etc.)
        days: Number of days for recent data (None = all history)
        start_date: Start date for historical fetch
        progress_callback: Progress callback
    
    Returns:
        List of combined volume data
    """
    all_data = []
    pairs = config.get_trading_pairs(coin)
    
    for symbol in pairs:
        try:
            if days is not None:
                data = fetch_recent_data(symbol=symbol, coin=coin, days=days)
            else:
                data = fetch_all_historical_data(
                    symbol=symbol, 
                    coin=coin,
                    start_date=start_date,
                    progress_callback=progress_callback
                )
            all_data.extend(data)
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            continue
    
    return all_data


def check_symbol_exists(symbol: str) -> bool:
    """Check if a trading pair exists on Binance"""
    session = get_session()
    try:
        response = session.get(f"{BASE_URL}/exchangeInfo", params={"symbol": symbol}, timeout=10)
        return response.status_code == 200
    except:
        return False


def get_available_pairs_for_coin(coin: str) -> List[str]:
    """Get which pairs (USDT/USDC) are available for a coin"""
    available = []
    for symbol in config.get_trading_pairs(coin):
        if check_symbol_exists(symbol):
            available.append(symbol)
    return available


if __name__ == "__main__":
    # Test fetching
    print("Testing Binance fetcher with config...")
    print(f"Configured coins: {config.get_coins()}")
    print(f"Proxy: {config.get_proxy_url() or 'None'}")
    
    # Test recent data fetch
    data = fetch_recent_data("BTCUSDT", "BTC", days=3)
    for d in data:
        print(f"{d['date']}: Net = {d['net_volume']:.2f} {d['coin']} (${d['net_volume_usd']:,.0f})")
