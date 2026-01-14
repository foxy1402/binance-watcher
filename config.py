"""
Configuration loader for BTC Market Volume Tracker
Reads settings from config.ini file
"""

import os
import configparser
from typing import List, Optional, Dict

CONFIG_PATH = os.environ.get('CONFIG_PATH', 'config.ini')

# Default configuration values
DEFAULTS = {
    'COINS': 'BTC,ETH,SOL,NEAR,LINK,AAVE',
    'ETF_VOLUME': 'BTC=IBIT,ETH=ETHA',
    'PROXY_URL': '',
    'SYNC_HOUR': '1',
    'SYNC_DAYS': '7',
    'DATABASE_PATH': 'volume_data.db',
    'PORT': '5000',
    'DEBUG': 'false'
}


def load_config() -> dict:
    """Load configuration from config.ini file"""
    config = configparser.ConfigParser()
    
    # Create default config if not exists
    if not os.path.exists(CONFIG_PATH):
        create_default_config()
    
    # Read config file (treating it as a simple key=value file)
    config_dict = DEFAULTS.copy()
    
    try:
        with open(CONFIG_PATH, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#') or line.startswith('['):
                    continue
                # Parse key=value pairs
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    if key in DEFAULTS:
                        config_dict[key] = value
    except Exception as e:
        print(f"Warning: Could not read config file: {e}")
    
    return config_dict


def create_default_config():
    """Create default config.ini file"""
    default_content = '''# =============================================================================
# BTC Market Volume Tracker - Configuration
# =============================================================================

# Supported coins (base assets to track)
# Add or remove coins as needed - both USDT and USDC pairs will be fetched
# and combined into a single total per coin
COINS = BTC,ETH,SOL,NEAR,LINK,AAVE

# =============================================================================
# Proxy Configuration (Optional)
# =============================================================================
# Leave empty to disable proxy
# HTTP Proxy example: http://user:pass@host:port
# SOCKS5 Proxy example: socks5://user:pass@host:port

PROXY_URL = 

# =============================================================================
# Data Sync Settings
# =============================================================================

# Hour (UTC) to run daily sync (0-23)
SYNC_HOUR = 1

# Number of days to fetch on each sync (for incremental updates)
# The app stores all historical data and only fetches new days
SYNC_DAYS = 7

# =============================================================================
# Database
# =============================================================================

# Path to SQLite database file
DATABASE_PATH = volume_data.db

# =============================================================================
# Server
# =============================================================================

# Port to run the server on
PORT = 5000

# Debug mode (set to false in production)
DEBUG = false
'''
    try:
        with open(CONFIG_PATH, 'w') as f:
            f.write(default_content)
        print(f"Created default config file: {CONFIG_PATH}")
    except Exception as e:
        print(f"Warning: Could not create config file: {e}")


def get_coins() -> List[str]:
    """Get list of coins to track"""
    config = load_config()
    coins_str = config.get('COINS', DEFAULTS['COINS'])
    return [c.strip().upper() for c in coins_str.split(',') if c.strip()]


def get_proxy_url() -> Optional[str]:
    """Get proxy URL - prioritizes environment variable for security"""
    # Priority: Environment variable > config file
    proxy = os.environ.get('PROXY_URL', '').strip()
    if not proxy:
        config = load_config()
        proxy = config.get('PROXY_URL', '').strip()
    return proxy if proxy else None


def get_sync_hour() -> int:
    """Get sync hour (UTC)"""
    config = load_config()
    try:
        return int(config.get('SYNC_HOUR', DEFAULTS['SYNC_HOUR']))
    except ValueError:
        return int(DEFAULTS['SYNC_HOUR'])


def get_sync_days() -> int:
    """Get number of days to sync"""
    config = load_config()
    try:
        return int(config.get('SYNC_DAYS', DEFAULTS['SYNC_DAYS']))
    except ValueError:
        return int(DEFAULTS['SYNC_DAYS'])


def get_database_path() -> str:
    """Get database path"""
    config = load_config()
    return os.environ.get('DATABASE_PATH', config.get('DATABASE_PATH', DEFAULTS['DATABASE_PATH']))


def get_port() -> int:
    """Get server port"""
    config = load_config()
    try:
        return int(os.environ.get('PORT', config.get('PORT', DEFAULTS['PORT'])))
    except ValueError:
        return int(DEFAULTS['PORT'])


def is_debug() -> bool:
    """Check if debug mode is enabled"""
    config = load_config()
    return config.get('DEBUG', DEFAULTS['DEBUG']).lower() == 'true'


# Convenience function to get all trading pairs for a coin
def get_trading_pairs(coin: str) -> List[str]:
    """Get all trading pairs (USDT + USDC) for a coin"""
    return [f"{coin}USDT", f"{coin}USDC"]


def get_all_trading_pairs() -> List[str]:
    """Get all trading pairs for all configured coins"""
    pairs = []
    for coin in get_coins():
        pairs.extend(get_trading_pairs(coin))
    return pairs


def get_etf_mappings() -> Dict[str, List[str]]:
    """Get ETF mappings from config (coin -> list of ETF tickers)"""
    config = load_config()
    etf_str = config.get('ETF_VOLUME', DEFAULTS.get('ETF_VOLUME', ''))
    mappings = {}
    for item in etf_str.split(','):
        item = item.strip()
        if '=' in item:
            coin, etfs = item.split('=', 1)
            # Support multiple ETFs separated by pipe
            etf_list = [e.strip() for e in etfs.split('|') if e.strip()]
            if etf_list:
                mappings[coin.strip().upper()] = etf_list
    return mappings


def get_etfs_for_coin(coin: str) -> List[str]:
    """Get list of ETF tickers for a coin, or empty list if not configured"""
    mappings = get_etf_mappings()
    return mappings.get(coin.upper(), [])


def get_etf_for_coin(coin: str) -> Optional[str]:
    """Get primary ETF ticker for a coin (first in list), or None if not configured"""
    etfs = get_etfs_for_coin(coin)
    return etfs[0] if etfs else None


def get_coins_with_etf() -> List[str]:
    """Get list of coins that have ETF mappings"""
    return list(get_etf_mappings().keys())


if __name__ == "__main__":
    # Test configuration loading
    print("Configuration Test:")
    print(f"  Coins: {get_coins()}")
    print(f"  Proxy: {get_proxy_url()}")
    print(f"  Sync Hour: {get_sync_hour()}")
    print(f"  Database: {get_database_path()}")
    print(f"  All Pairs: {get_all_trading_pairs()}")
    print(f"  ETF Mappings: {get_etf_mappings()}")
    print(f"  BTC ETFs: {get_etfs_for_coin('BTC')}")
