"""
Yahoo Finance ETF Data Fetcher
Fetches ETF price and volume data for accumulation/distribution analysis
"""

import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import config

# Yahoo Finance API endpoints
YF_BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"

# Rate limiting
REQUEST_DELAY = 0.2  # 200ms between requests


def get_session() -> requests.Session:
    """Create a requests session with proxy if configured"""
    session = requests.Session()
    
    proxy_url = config.get_proxy_url()
    if proxy_url:
        session.proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
    
    # Set user agent to avoid blocking
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    return session


def fetch_etf_data(ticker: str, period: str = "max", interval: str = "1d",
                   session: Optional[requests.Session] = None) -> List[Dict]:
    """
    Fetch ETF historical data from Yahoo Finance
    
    Args:
        ticker: ETF ticker symbol (e.g., IBIT, ETHA)
        period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
        interval: Data interval (1d, 1wk, 1mo)
        session: Optional requests session with proxy
    
    Returns:
        List of parsed ETF data dictionaries
    """
    if session is None:
        session = get_session()
    
    params = {
        "period1": 0,  # Start from beginning
        "period2": int(datetime.now().timestamp()),
        "interval": interval,
        "events": "history",
        "includeAdjustedClose": "true"
    }
    
    try:
        url = f"{YF_BASE_URL}/{ticker}"
        response = session.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        result = data.get('chart', {}).get('result', [])
        if not result:
            print(f"No data found for ETF {ticker}")
            return []
        
        chart_data = result[0]
        timestamps = chart_data.get('timestamp', [])
        indicators = chart_data.get('indicators', {})
        quote = indicators.get('quote', [{}])[0]
        
        opens = quote.get('open', [])
        highs = quote.get('high', [])
        lows = quote.get('low', [])
        closes = quote.get('close', [])
        volumes = quote.get('volume', [])
        
        parsed_data = []
        
        for i, ts in enumerate(timestamps):
            if ts is None:
                continue
                
            date_str = datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d')
            
            open_price = opens[i] if i < len(opens) and opens[i] is not None else 0
            high_price = highs[i] if i < len(highs) and highs[i] is not None else 0
            low_price = lows[i] if i < len(lows) and lows[i] is not None else 0
            close_price = closes[i] if i < len(closes) and closes[i] is not None else 0
            volume = volumes[i] if i < len(volumes) and volumes[i] is not None else 0
            
            # Skip invalid data points
            if close_price == 0:
                continue
            
            # For ETFs, we estimate buy/sell based on price movement and volume
            # Positive price change with high volume = accumulation
            # Negative price change with volume = distribution
            price_change = close_price - open_price if open_price > 0 else 0
            price_change_pct = (price_change / open_price * 100) if open_price > 0 else 0
            
            # Estimate buy/sell volumes based on price direction
            # This is an approximation since ETFs don't have taker buy volume
            if price_change >= 0:
                # Price went up - assume more buying
                buy_ratio = 0.5 + (min(abs(price_change_pct), 5) / 10)  # 50-100% buy
            else:
                # Price went down - assume more selling
                buy_ratio = 0.5 - (min(abs(price_change_pct), 5) / 10)  # 0-50% buy
            
            buy_volume = volume * buy_ratio
            sell_volume = volume * (1 - buy_ratio)
            net_volume = buy_volume - sell_volume
            
            # USD calculations
            avg_price = (open_price + close_price) / 2
            buy_volume_usd = buy_volume * avg_price
            sell_volume_usd = sell_volume * avg_price
            net_volume_usd = net_volume * avg_price
            
            parsed_data.append({
                'ticker': ticker,
                'date': date_str,
                'open_price': round(open_price, 4),
                'close_price': round(close_price, 4),
                'high_price': round(high_price, 4),
                'low_price': round(low_price, 4),
                'total_volume': volume,
                'buy_volume': round(buy_volume, 2),
                'sell_volume': round(sell_volume, 2),
                'net_volume': round(net_volume, 2),
                'buy_volume_usd': round(buy_volume_usd, 2),
                'sell_volume_usd': round(sell_volume_usd, 2),
                'net_volume_usd': round(net_volume_usd, 2),
                'price_change_pct': round(price_change_pct, 4)
            })
        
        return parsed_data
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching ETF data for {ticker}: {e}")
        return []
    except (KeyError, IndexError, TypeError) as e:
        print(f"Error parsing ETF data for {ticker}: {e}")
        return []


def fetch_etf_for_coin(coin: str, days: Optional[int] = None,
                       progress_callback=None) -> List[Dict]:
    """
    Fetch ETF data for a coin from ALL configured ETFs and aggregate
    
    Args:
        coin: Base coin (BTC, ETH, etc.)
        days: Number of days to fetch (None = all history)
        progress_callback: Progress callback
    
    Returns:
        List of aggregated ETF volume data, or empty list if no ETF mapping
    """
    etf_tickers = config.get_etfs_for_coin(coin)
    
    if not etf_tickers:
        return []
    
    session = get_session()
    all_etf_data = {}  # date -> aggregated data
    
    # Fetch data from each ETF
    for ticker in etf_tickers:
        if progress_callback:
            progress_callback(0, f"Fetching ETF {ticker} data...")
        
        try:
            data = fetch_etf_data(ticker, session=session)
            time.sleep(REQUEST_DELAY)  # Rate limiting between ETFs
            
            if not data:
                print(f"No data for {ticker}, skipping...")
                continue
            
            print(f"Fetched {len(data)} records from {ticker}")
            
            # Aggregate by date
            for record in data:
                date = record['date']
                
                if date not in all_etf_data:
                    # First ETF for this date - use as base
                    all_etf_data[date] = {
                        'coin': coin,
                        'ticker': ticker,  # Primary ticker
                        'tickers': [ticker],
                        'date': date,
                        'open_price': record['open_price'],
                        'close_price': record['close_price'],
                        'high_price': record['high_price'],
                        'low_price': record['low_price'],
                        'total_volume': record['total_volume'],
                        'buy_volume': record['buy_volume'],
                        'sell_volume': record['sell_volume'],
                        'net_volume': record['net_volume'],
                        'buy_volume_usd': record['buy_volume_usd'],
                        'sell_volume_usd': record['sell_volume_usd'],
                        'net_volume_usd': record['net_volume_usd'],
                        'price_change_pct': record['price_change_pct'],
                        '_price_sum': record['close_price'],
                        '_price_count': 1
                    }
                else:
                    # Aggregate with existing data
                    existing = all_etf_data[date]
                    existing['tickers'].append(ticker)
                    
                    # Sum volumes (these represent total market flow)
                    existing['total_volume'] += record['total_volume']
                    existing['buy_volume'] += record['buy_volume']
                    existing['sell_volume'] += record['sell_volume']
                    existing['net_volume'] += record['net_volume']
                    existing['buy_volume_usd'] += record['buy_volume_usd']
                    existing['sell_volume_usd'] += record['sell_volume_usd']
                    existing['net_volume_usd'] += record['net_volume_usd']
                    
                    # Average price across ETFs
                    existing['_price_sum'] += record['close_price']
                    existing['_price_count'] += 1
                    existing['close_price'] = existing['_price_sum'] / existing['_price_count']
                    
                    # Take extremes for high/low
                    existing['high_price'] = max(existing['high_price'], record['high_price'])
                    existing['low_price'] = min(existing['low_price'], record['low_price'])
                    
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            continue
    
    # Convert to list and clean up
    result = []
    for date, data in all_etf_data.items():
        # Remove internal tracking fields
        data.pop('_price_sum', None)
        data.pop('_price_count', None)
        data['ticker'] = '|'.join(data['tickers'])  # Combined ticker names
        data.pop('tickers', None)
        result.append(data)
    
    # Filter by days if specified
    if days is not None and result:
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        result = [d for d in result if d['date'] >= cutoff_date]
    
    if progress_callback:
        progress_callback(len(result), f"Fetched {len(result)} aggregated ETF records for {coin}")
    
    print(f"Total aggregated ETF records for {coin}: {len(result)}")
    return result


def fetch_recent_etf_data(ticker: str, days: int = 30) -> List[Dict]:
    """Fetch recent ETF data from a single ticker"""
    session = get_session()
    data = fetch_etf_data(ticker, session=session)
    
    if not data:
        return []
    
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    return [d for d in data if d['date'] >= cutoff_date]


if __name__ == "__main__":
    # Test ETF fetching
    print("Testing Yahoo Finance ETF fetcher...")
    print(f"ETF Mappings: {config.get_etf_mappings()}")
    print(f"BTC ETFs: {config.get_etfs_for_coin('BTC')}")
    
    # Test aggregated fetch for BTC
    print("\nFetching aggregated BTC ETF data (last 5 days)...")
    data = fetch_etf_for_coin("BTC", days=5)
    print(f"\nBTC Aggregated ETF (last 5 days):")
    for d in sorted(data, key=lambda x: x['date']):
        print(f"  {d['date']}: ${d['close_price']:.2f}, Net Vol: {d['net_volume']:,.0f} ({d['ticker']})")

