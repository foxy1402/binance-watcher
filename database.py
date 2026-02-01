"""
Database module for BTC Market Volume Tracker
SQLite-based persistent storage for volume data
Supports coin aggregation (combining USDT + USDC pairs)
"""

import sqlite3
import os
from datetime import datetime, date
from contextlib import contextmanager
import config

DATABASE_PATH = config.get_database_path()


@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_database():
    """Initialize database schema"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Raw volume data table (per trading pair)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS volume_data_raw (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coin TEXT NOT NULL,
                symbol TEXT NOT NULL,
                date DATE NOT NULL,
                open_price REAL,
                close_price REAL,
                high_price REAL,
                low_price REAL,
                total_volume REAL,
                buy_volume REAL,
                sell_volume REAL,
                net_volume REAL,
                buy_volume_usd REAL,
                sell_volume_usd REAL,
                net_volume_usd REAL,
                price_change_pct REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, date)
            )
        ''')
        
        # Index for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_raw_coin_date 
            ON volume_data_raw(coin, date DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_raw_symbol_date 
            ON volume_data_raw(symbol, date DESC)
        ''')
        
        # Sync status table to track last sync
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_status (
                id INTEGER PRIMARY KEY,
                coin TEXT UNIQUE NOT NULL,
                last_sync_date DATE,
                last_sync_timestamp TIMESTAMP,
                total_records INTEGER DEFAULT 0,
                earliest_date DATE,
                latest_date DATE
            )
        ''')
        
        # ETF volume data table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS etf_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coin TEXT NOT NULL,
                ticker TEXT NOT NULL,
                date DATE NOT NULL,
                open_price REAL,
                close_price REAL,
                high_price REAL,
                low_price REAL,
                total_volume REAL,
                buy_volume REAL,
                sell_volume REAL,
                net_volume REAL,
                buy_volume_usd REAL,
                sell_volume_usd REAL,
                net_volume_usd REAL,
                price_change_pct REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ticker, date)
            )
        ''')
        
        # Index for ETF queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_etf_coin_date 
            ON etf_data(coin, date DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_etf_ticker_date 
            ON etf_data(ticker, date DESC)
        ''')
        
        # Smart alerts table for whale detection and unusual activity
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS smart_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coin TEXT NOT NULL,
                date DATE NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                description TEXT,
                value_usd REAL,
                volume REAL,
                price REAL,
                zscore REAL,
                size_class TEXT,
                rsi REAL,
                metadata TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                acknowledged INTEGER DEFAULT 0,
                UNIQUE(coin, date, alert_type)
            )
        ''')
        
        # Index for alert queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_alerts_coin_date 
            ON smart_alerts(coin, date DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_alerts_severity 
            ON smart_alerts(severity, timestamp DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_alerts_type 
            ON smart_alerts(alert_type, timestamp DESC)
        ''')
        
        # Futures metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS futures_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coin TEXT NOT NULL,
                symbol TEXT NOT NULL,
                date DATE NOT NULL,
                spot_price REAL,
                futures_price REAL,
                premium_pct REAL,
                funding_rate REAL,
                funding_rate_annualized REAL,
                open_interest REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, date)
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_futures_coin_date 
            ON futures_metrics(coin, date DESC)
        ''')
        
        conn.commit()


def upsert_volume_data(data_list):
    """
    Insert or update raw volume data
    
    Args:
        data_list: List of dictionaries with volume data
    
    Returns:
        Number of records inserted/updated
    """
    if not data_list:
        return 0
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.executemany('''
            INSERT INTO volume_data_raw (
                coin, symbol, date, open_price, close_price, high_price, low_price,
                total_volume, buy_volume, sell_volume, net_volume,
                buy_volume_usd, sell_volume_usd, net_volume_usd, price_change_pct
            ) VALUES (
                :coin, :symbol, :date, :open_price, :close_price, :high_price, :low_price,
                :total_volume, :buy_volume, :sell_volume, :net_volume,
                :buy_volume_usd, :sell_volume_usd, :net_volume_usd, :price_change_pct
            )
            ON CONFLICT(symbol, date) DO UPDATE SET
                open_price = excluded.open_price,
                close_price = excluded.close_price,
                high_price = excluded.high_price,
                low_price = excluded.low_price,
                total_volume = excluded.total_volume,
                buy_volume = excluded.buy_volume,
                sell_volume = excluded.sell_volume,
                net_volume = excluded.net_volume,
                buy_volume_usd = excluded.buy_volume_usd,
                sell_volume_usd = excluded.sell_volume_usd,
                net_volume_usd = excluded.net_volume_usd,
                price_change_pct = excluded.price_change_pct
        ''', data_list)
        
        conn.commit()
        return cursor.rowcount


def get_volume_data(coin='BTC', start_date=None, end_date=None, limit=None):
    """
    Retrieve AGGREGATED volume data for a coin (combining all pairs)
    
    Args:
        coin: Base coin (BTC, ETH, etc.)
        start_date: Start date filter (inclusive)
        end_date: End date filter (inclusive)
        limit: Maximum number of records
    
    Returns:
        List of aggregated volume data dictionaries
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        query = '''
            SELECT 
                coin,
                date,
                AVG(open_price) as open_price,
                AVG(close_price) as close_price,
                MAX(high_price) as high_price,
                MIN(low_price) as low_price,
                SUM(total_volume) as total_volume,
                SUM(buy_volume) as buy_volume,
                SUM(sell_volume) as sell_volume,
                SUM(net_volume) as net_volume,
                SUM(buy_volume_usd) as buy_volume_usd,
                SUM(sell_volume_usd) as sell_volume_usd,
                SUM(net_volume_usd) as net_volume_usd,
                AVG(price_change_pct) as price_change_pct
            FROM volume_data_raw 
            WHERE coin = ?
        '''
        params = [coin]
        
        if start_date:
            query += ' AND date >= ?'
            params.append(start_date)
        
        if end_date:
            query += ' AND date <= ?'
            params.append(end_date)
        
        query += ' GROUP BY coin, date ORDER BY date DESC'
        
        if limit:
            query += ' LIMIT ?'
            params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]


def get_volume_summary(coin='BTC', days=None):
    """
    Get aggregated volume statistics for a coin
    
    Args:
        coin: Base coin
        days: Number of days to aggregate (None = all data)
    
    Returns:
        Dictionary with summary statistics
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Build query for aggregated data
        if days:
            query = '''
                SELECT
                    COUNT(DISTINCT date) as total_days,
                    SUM(buy_volume) as total_buy_volume,
                    SUM(sell_volume) as total_sell_volume,
                    SUM(net_volume) as total_net_volume,
                    SUM(buy_volume_usd) as total_buy_usd,
                    SUM(sell_volume_usd) as total_sell_usd,
                    SUM(net_volume_usd) as total_net_usd,
                    AVG(close_price) as avg_price
                FROM (
                    SELECT 
                        date,
                        SUM(buy_volume) as buy_volume,
                        SUM(sell_volume) as sell_volume,
                        SUM(net_volume) as net_volume,
                        SUM(buy_volume_usd) as buy_volume_usd,
                        SUM(sell_volume_usd) as sell_volume_usd,
                        SUM(net_volume_usd) as net_volume_usd,
                        AVG(close_price) as close_price
                    FROM volume_data_raw
                    WHERE coin = ?
                    GROUP BY date
                    ORDER BY date DESC
                    LIMIT ?
                )
            '''
            cursor.execute(query, (coin, days))
        else:
            query = '''
                SELECT
                    COUNT(DISTINCT date) as total_days,
                    SUM(buy_volume) as total_buy_volume,
                    SUM(sell_volume) as total_sell_volume,
                    SUM(net_volume) as total_net_volume,
                    SUM(buy_volume_usd) as total_buy_usd,
                    SUM(sell_volume_usd) as total_sell_usd,
                    SUM(net_volume_usd) as total_net_usd,
                    AVG(close_price) as avg_price
                FROM volume_data_raw
                WHERE coin = ?
            '''
            cursor.execute(query, (coin,))
        
        row = cursor.fetchone()
        
        if row:
            summary = dict(row)
            # Calculate averages
            if summary['total_days'] and summary['total_days'] > 0:
                summary['avg_daily_net_volume'] = summary['total_net_volume'] / summary['total_days']
                summary['avg_daily_net_usd'] = summary['total_net_usd'] / summary['total_days']
            return summary
        return None


def get_cumulative_volume(coin='BTC', start_date=None):
    """
    Calculate cumulative net volume over time for a coin
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        query = '''
            SELECT 
                date,
                net_volume,
                net_volume_usd,
                SUM(net_volume) OVER (ORDER BY date) as cumulative_volume,
                SUM(net_volume_usd) OVER (ORDER BY date) as cumulative_usd
            FROM (
                SELECT 
                    date,
                    SUM(net_volume) as net_volume,
                    SUM(net_volume_usd) as net_volume_usd
                FROM volume_data_raw
                WHERE coin = ?
        '''
        params = [coin]
        
        if start_date:
            query += ' AND date >= ?'
            params.append(start_date)
        
        query += '''
                GROUP BY date
            )
            ORDER BY date
        '''
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]


def get_sync_status(coin='BTC'):
    """Get last sync status for a coin"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM sync_status WHERE coin = ?',
            (coin,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def update_sync_status(coin):
    """Update sync status after data fetch"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Get date range and count
        cursor.execute('''
            SELECT MIN(date) as earliest, MAX(date) as latest, COUNT(DISTINCT date) as count
            FROM volume_data_raw WHERE coin = ?
        ''', (coin,))
        stats = cursor.fetchone()
        
        cursor.execute('''
            INSERT INTO sync_status (coin, last_sync_date, last_sync_timestamp, total_records, earliest_date, latest_date)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(coin) DO UPDATE SET
                last_sync_date = excluded.last_sync_date,
                last_sync_timestamp = excluded.last_sync_timestamp,
                total_records = excluded.total_records,
                earliest_date = excluded.earliest_date,
                latest_date = excluded.latest_date
        ''', (
            coin, 
            stats['latest'], 
            datetime.now().isoformat(), 
            stats['count'],
            stats['earliest'],
            stats['latest']
        ))
        conn.commit()


def get_all_coins():
    """Get list of all tracked coins"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT coin FROM volume_data_raw ORDER BY coin')
        return [row[0] for row in cursor.fetchall()]


def get_date_range(coin='BTC'):
    """Get the date range of available data for a coin"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT MIN(date) as earliest, MAX(date) as latest, COUNT(DISTINCT date) as count
            FROM volume_data_raw WHERE coin = ?
        ''', (coin,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_latest_date(coin='BTC') -> str:
    """Get the most recent date we have data for"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT MAX(date) as latest FROM volume_data_raw WHERE coin = ?
        ''', (coin,))
        row = cursor.fetchone()
        return row['latest'] if row and row['latest'] else None


def get_missing_dates(coin='BTC', start_date='2017-08-17') -> list:
    """Get list of dates missing from our data"""
    # This is useful for incremental sync
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT date FROM volume_data_raw 
            WHERE coin = ? AND date >= ?
            ORDER BY date
        ''', (coin, start_date))
        existing = set(row[0] for row in cursor.fetchall())
    
    # Generate all dates
    from datetime import datetime, timedelta
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.now()
    all_dates = set()
    current = start
    while current <= end:
        all_dates.add(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)
    
    return sorted(all_dates - existing)


# =============================================================================
# ETF Data Functions
# =============================================================================

def upsert_etf_data(data_list):
    """
    Insert or update ETF volume data
    
    Args:
        data_list: List of dictionaries with ETF data
    
    Returns:
        Number of records inserted/updated
    """
    if not data_list:
        return 0
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.executemany('''
            INSERT INTO etf_data (
                coin, ticker, date, open_price, close_price, high_price, low_price,
                total_volume, buy_volume, sell_volume, net_volume,
                buy_volume_usd, sell_volume_usd, net_volume_usd, price_change_pct
            ) VALUES (
                :coin, :ticker, :date, :open_price, :close_price, :high_price, :low_price,
                :total_volume, :buy_volume, :sell_volume, :net_volume,
                :buy_volume_usd, :sell_volume_usd, :net_volume_usd, :price_change_pct
            )
            ON CONFLICT(ticker, date) DO UPDATE SET
                open_price = excluded.open_price,
                close_price = excluded.close_price,
                high_price = excluded.high_price,
                low_price = excluded.low_price,
                total_volume = excluded.total_volume,
                buy_volume = excluded.buy_volume,
                sell_volume = excluded.sell_volume,
                net_volume = excluded.net_volume,
                buy_volume_usd = excluded.buy_volume_usd,
                sell_volume_usd = excluded.sell_volume_usd,
                net_volume_usd = excluded.net_volume_usd,
                price_change_pct = excluded.price_change_pct
        ''', data_list)
        
        conn.commit()
        return cursor.rowcount


def get_etf_data(coin='BTC', start_date=None, end_date=None, limit=None):
    """
    Retrieve ETF volume data for a coin
    
    Args:
        coin: Base coin (BTC, ETH, etc.)
        start_date: Start date filter (inclusive)
        end_date: End date filter (inclusive)
        limit: Maximum number of records
    
    Returns:
        List of ETF volume data dictionaries
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        query = '''
            SELECT * FROM etf_data 
            WHERE coin = ?
        '''
        params = [coin]
        
        if start_date:
            query += ' AND date >= ?'
            params.append(start_date)
        
        if end_date:
            query += ' AND date <= ?'
            params.append(end_date)
        
        query += ' ORDER BY date DESC'
        
        if limit:
            query += ' LIMIT ?'
            params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]


def get_etf_date_range(coin='BTC'):
    """Get the date range of available ETF data for a coin"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT MIN(date) as earliest, MAX(date) as latest, COUNT(*) as count
            FROM etf_data WHERE coin = ?
        ''', (coin,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_etf_latest_date(coin='BTC') -> str:
    """Get the most recent date we have ETF data for"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT MAX(date) as latest FROM etf_data WHERE coin = ?
        ''', (coin,))
        row = cursor.fetchone()
        return row['latest'] if row and row['latest'] else None


def upsert_smart_alert(alert: dict):
    """
    Insert or update a smart alert
    
    Args:
        alert: Alert dictionary
    
    Returns:
        Alert ID
    """
    import json
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Prepare metadata JSON
        metadata = {
            k: v for k, v in alert.items()
            if k not in ['coin', 'date', 'type', 'severity', 'description', 
                        'value_usd', 'volume', 'price', 'zscore', 'size_class', 'rsi']
        }
        
        cursor.execute('''
            INSERT INTO smart_alerts (
                coin, date, alert_type, severity, description,
                value_usd, volume, price, zscore, size_class, rsi, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(coin, date, alert_type) DO UPDATE SET
                severity = excluded.severity,
                description = excluded.description,
                value_usd = excluded.value_usd,
                volume = excluded.volume,
                price = excluded.price,
                zscore = excluded.zscore,
                size_class = excluded.size_class,
                rsi = excluded.rsi,
                metadata = excluded.metadata,
                timestamp = CURRENT_TIMESTAMP
        ''', (
            alert.get('coin'),
            alert.get('date'),
            alert.get('type'),
            alert.get('severity', 'low'),
            alert.get('description'),
            alert.get('value_usd'),
            alert.get('volume'),
            alert.get('price'),
            alert.get('zscore'),
            alert.get('size_class'),
            alert.get('rsi'),
            json.dumps(metadata)
        ))
        
        conn.commit()
        return cursor.lastrowid


def get_smart_alerts(coin=None, start_date=None, end_date=None, 
                     severity=None, alert_type=None, limit=100):
    """
    Retrieve smart alerts with filters
    
    Args:
        coin: Filter by coin
        start_date: Start date filter
        end_date: End date filter
        severity: Filter by severity (critical, high, medium, low)
        alert_type: Filter by alert type
        limit: Maximum records
    
    Returns:
        List of alert dictionaries
    """
    import json
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        query = 'SELECT * FROM smart_alerts WHERE 1=1'
        params = []
        
        if coin:
            query += ' AND coin = ?'
            params.append(coin)
        
        if start_date:
            query += ' AND date >= ?'
            params.append(start_date)
        
        if end_date:
            query += ' AND date <= ?'
            params.append(end_date)
        
        if severity:
            query += ' AND severity = ?'
            params.append(severity)
        
        if alert_type:
            query += ' AND alert_type = ?'
            params.append(alert_type)
        
        query += ' ORDER BY timestamp DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        alerts = []
        for row in rows:
            alert = dict(row)
            # Parse metadata JSON
            if alert.get('metadata'):
                try:
                    metadata = json.loads(alert['metadata'])
                    alert.update(metadata)
                except:
                    pass
            alerts.append(alert)
        
        return alerts


def get_alert_summary(coin=None, days=7):
    """
    Get summary of recent alerts
    
    Args:
        coin: Filter by coin
        days: Number of days to look back
    
    Returns:
        Summary dictionary
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        query = '''
            SELECT 
                COUNT(*) as total_alerts,
                SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) as critical,
                SUM(CASE WHEN severity = 'high' THEN 1 ELSE 0 END) as high,
                SUM(CASE WHEN severity = 'medium' THEN 1 ELSE 0 END) as medium,
                SUM(CASE WHEN severity = 'low' THEN 1 ELSE 0 END) as low,
                COUNT(DISTINCT alert_type) as unique_types,
                COUNT(DISTINCT coin) as coins_affected
            FROM smart_alerts
            WHERE date >= date('now', '-' || ? || ' days')
        '''
        params = [days]
        
        if coin:
            query += ' AND coin = ?'
            params.append(coin)
        
        cursor.execute(query, params)
        row = cursor.fetchone()
        
        return dict(row) if row else None


def acknowledge_alert(alert_id: int):
    """Mark an alert as acknowledged"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE smart_alerts SET acknowledged = 1 WHERE id = ?',
            (alert_id,)
        )
        conn.commit()


def delete_old_alerts(days=90):
    """Delete alerts older than specified days"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM smart_alerts WHERE date < date('now', '-' || ? || ' days')",
            (days,)
        )
        conn.commit()
        return cursor.rowcount


def upsert_futures_metrics(metrics: dict):
    """
    Insert or update futures metrics
    
    Args:
        metrics: Futures metrics dictionary
    
    Returns:
        Record ID
    """
    from datetime import datetime
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Use current date
        date_str = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute('''
            INSERT INTO futures_metrics (
                coin, symbol, date, spot_price, futures_price,
                premium_pct, funding_rate, funding_rate_annualized, open_interest
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, date) DO UPDATE SET
                spot_price = excluded.spot_price,
                futures_price = excluded.futures_price,
                premium_pct = excluded.premium_pct,
                funding_rate = excluded.funding_rate,
                funding_rate_annualized = excluded.funding_rate_annualized,
                open_interest = excluded.open_interest,
                timestamp = CURRENT_TIMESTAMP
        ''', (
            metrics.get('coin'),
            metrics.get('symbol'),
            date_str,
            metrics.get('spot_price'),
            metrics.get('futures_price'),
            metrics.get('premium_pct'),
            metrics.get('funding_rate'),
            metrics.get('funding_rate_annualized'),
            metrics.get('open_interest')
        ))
        
        conn.commit()
        return cursor.lastrowid


def get_futures_metrics(coin=None, start_date=None, end_date=None, limit=30):
    """
    Retrieve futures metrics
    
    Args:
        coin: Filter by coin
        start_date: Start date filter
        end_date: End date filter
        limit: Maximum records
    
    Returns:
        List of futures metrics
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        query = 'SELECT * FROM futures_metrics WHERE 1=1'
        params = []
        
        if coin:
            query += ' AND coin = ?'
            params.append(coin)
        
        if start_date:
            query += ' AND date >= ?'
            params.append(start_date)
        
        if end_date:
            query += ' AND date <= ?'
            params.append(end_date)
        
        query += ' ORDER BY date DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]


# Initialize database on module import
init_database()

