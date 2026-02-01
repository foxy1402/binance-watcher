"""
BTC Market Volume Tracker - Main Flask Application
Tracks daily Bitcoin buy/sell volumes on Binance
Supports multiple coins with USDT+USDC aggregation
"""

import os
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template, send_from_directory, Response
from apscheduler.schedulers.background import BackgroundScheduler
import database as db
import binance_fetcher as bf
import etf_fetcher as ef
import indicators as ind
import whale_detector as wd
import futures_tracker as ft
import config

app = Flask(__name__, static_folder='static', template_folder='templates')

# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.route('/')
def index():
    """Serve the main dashboard"""
    return render_template('index.html')


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    # Convert ETF mappings from Dict[str, List[str]] to Dict[str, str]
    # Frontend expects coin -> "IBIT|FBTC|GBTC" format
    raw_mappings = config.get_etf_mappings()
    etf_mappings = {coin: '|'.join(tickers) for coin, tickers in raw_mappings.items()}
    
    return jsonify({
        'success': True,
        'coins': config.get_coins(),
        'sync_hour': config.get_sync_hour(),
        'etf_mappings': etf_mappings
    })


@app.route('/api/volumes', methods=['GET'])
def get_volumes():
    """
    Get volume data with optional filters and technical indicators
    
    Query params:
        coin: Base coin (default: BTC) - NOT the trading pair!
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        limit: Max records to return
        include_indicators: Include technical indicators (default: false)
    """
    coin = request.args.get('coin', 'BTC').upper()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = request.args.get('limit', type=int)
    include_indicators = request.args.get('include_indicators', 'false').lower() == 'true'
    
    data = db.get_volume_data(
        coin=coin,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )
    
    # Add technical indicators if requested
    if include_indicators and data:
        # Sort by date ascending for indicator calculation
        data_asc = sorted(data, key=lambda x: x['date'])
        data_asc = ind.enhance_volume_data_with_indicators(data_asc)
        # Sort back to descending
        data = sorted(data_asc, key=lambda x: x['date'], reverse=True)
    
    return jsonify({
        'success': True,
        'coin': coin,
        'count': len(data),
        'data': data
    })


@app.route('/api/volumes/summary', methods=['GET'])
def get_summary():
    """
    Get aggregated volume statistics
    
    Query params:
        coin: Base coin (default: BTC)
        days: Number of days to aggregate (default: all)
    """
    coin = request.args.get('coin', 'BTC').upper()
    days = request.args.get('days', type=int)
    
    summary = db.get_volume_summary(coin=coin, days=days)
    date_range = db.get_date_range(coin=coin)
    
    return jsonify({
        'success': True,
        'coin': coin,
        'days': days,
        'summary': summary,
        'date_range': date_range
    })


@app.route('/api/volumes/cumulative', methods=['GET'])
def get_cumulative():
    """
    Get cumulative net volume over time
    
    Query params:
        coin: Base coin (default: BTC)
        start_date: Start date (YYYY-MM-DD)
    """
    coin = request.args.get('coin', 'BTC').upper()
    start_date = request.args.get('start_date')
    
    data = db.get_cumulative_volume(coin=coin, start_date=start_date)
    
    return jsonify({
        'success': True,
        'coin': coin,
        'count': len(data),
        'data': data
    })


@app.route('/api/sync', methods=['POST'])
def sync_data():
    """
    Trigger manual data sync
    
    JSON body:
        coin: Base coin (default: all configured coins)
        full_sync: If true, fetch all historical data (default: false)
    """
    data = request.get_json() or {}
    requested_coin = data.get('coin')
    full_sync = data.get('full_sync', False)
    
    # Determine which coins to sync
    if requested_coin:
        coins_to_sync = [requested_coin.upper()]
    else:
        coins_to_sync = config.get_coins()
    
    total_records = 0
    results = {}
    
    for coin in coins_to_sync:
        try:
            if full_sync:
                # Fetch all historical data for both USDT and USDC pairs
                volume_data = bf.fetch_coin_data(coin=coin, days=None)
            else:
                # Incremental sync: fetch recent data
                latest_date = db.get_latest_date(coin)
                if latest_date:
                    # Fetch from last date + a few days overlap
                    start_date = (datetime.strptime(latest_date, '%Y-%m-%d') - timedelta(days=3)).strftime('%Y-%m-%d')
                    volume_data = bf.fetch_coin_data(coin=coin, days=config.get_sync_days())
                else:
                    # No data yet, do full sync
                    volume_data = bf.fetch_coin_data(coin=coin, days=None)
            
            if volume_data:
                count = db.upsert_volume_data(volume_data)
                db.update_sync_status(coin)
                results[coin] = len(volume_data)
                total_records += len(volume_data)
        except Exception as e:
            results[coin] = f"Error: {str(e)}"
    
    return jsonify({
        'success': True,
        'message': f'Synced {total_records} records across {len(coins_to_sync)} coins',
        'results': results
    })


@app.route('/api/sync/status', methods=['GET'])
def get_sync_status():
    """Get sync status for a coin or all coins"""
    coin = request.args.get('coin')
    
    if coin:
        status = db.get_sync_status(coin=coin.upper())
        return jsonify({
            'success': True,
            'coin': coin.upper(),
            'status': status
        })
    else:
        # Get status for all configured coins
        statuses = {}
        for c in config.get_coins():
            statuses[c] = db.get_sync_status(coin=c)
        return jsonify({
            'success': True,
            'statuses': statuses
        })


@app.route('/api/coins', methods=['GET'])
def get_coins():
    """Get list of configured and tracked coins"""
    configured = config.get_coins()
    tracked = db.get_all_coins()
    
    return jsonify({
        'success': True,
        'configured': configured,
        'tracked': tracked
    })


# =============================================================================
# ETF API ENDPOINTS
# =============================================================================

@app.route('/api/etf', methods=['GET'])
def get_etf_volumes():
    """
    Get ETF volume data for a coin
    
    Query params:
        coin: Base coin (default: BTC)
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    """
    coin = request.args.get('coin', 'BTC').upper()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Check if coin has ETF mapping
    etf_tickers = config.get_etfs_for_coin(coin)
    if not etf_tickers:
        return jsonify({
            'success': False,
            'message': f'No ETF configured for {coin}'
        }), 404
    
    data = db.get_etf_data(
        coin=coin,
        start_date=start_date,
        end_date=end_date
    )
    
    return jsonify({
        'success': True,
        'coin': coin,
        'etf_tickers': etf_tickers,  # List of all ETF tickers
        'etf_ticker': '|'.join(etf_tickers),  # Combined string for display
        'count': len(data),
        'data': data
    })


@app.route('/api/etf/sync', methods=['POST'])
def sync_etf_data():
    """
    Trigger ETF data sync
    
    JSON body:
        coin: Base coin (default: all coins with ETF)
    """
    data = request.get_json() or {}
    requested_coin = data.get('coin')
    
    # Determine which coins to sync
    if requested_coin:
        coins_to_sync = [requested_coin.upper()]
    else:
        coins_to_sync = config.get_coins_with_etf()
    
    total_records = 0
    results = {}
    
    for coin in coins_to_sync:
        etf_ticker = config.get_etf_for_coin(coin)
        if not etf_ticker:
            results[coin] = "No ETF configured"
            continue
        
        try:
            etf_data = ef.fetch_etf_for_coin(coin)
            if etf_data:
                db.upsert_etf_data(etf_data)
                results[coin] = f"{len(etf_data)} records ({etf_ticker})"
                total_records += len(etf_data)
            else:
                results[coin] = "No data found"
        except Exception as e:
            results[coin] = f"Error: {str(e)}"
    
    return jsonify({
        'success': True,
        'message': f'Synced {total_records} ETF records',
        'results': results
    })


@app.route('/api/export', methods=['GET'])
def export_data():
    """
    Export volume data as CSV
    
    Query params:
        coin: Base coin (default: BTC)
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    """
    coin = request.args.get('coin', 'BTC').upper()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    data = db.get_volume_data(
        coin=coin,
        start_date=start_date,
        end_date=end_date
    )
    
    if not data:
        return jsonify({'success': False, 'message': 'No data found'}), 404
    
    # Generate CSV
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        'date', 'coin', 'open_price', 'close_price', 'high_price', 'low_price',
        'total_volume', 'buy_volume', 'sell_volume', 'net_volume',
        'buy_volume_usd', 'sell_volume_usd', 'net_volume_usd', 'price_change_pct'
    ])
    writer.writeheader()
    
    for row in data:
        writer.writerow(row)
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={coin}_volume_data.csv'}
    )


# =============================================================================
# SMART ALERTS API ENDPOINTS
# =============================================================================

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """
    Get smart alerts with optional filters
    
    Query params:
        coin: Filter by coin
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        severity: Filter by severity (critical, high, medium, low)
        alert_type: Filter by alert type
        limit: Max records (default: 100)
    """
    coin = request.args.get('coin')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    severity = request.args.get('severity')
    alert_type = request.args.get('alert_type')
    limit = request.args.get('limit', 100, type=int)
    
    alerts = db.get_smart_alerts(
        coin=coin,
        start_date=start_date,
        end_date=end_date,
        severity=severity,
        alert_type=alert_type,
        limit=limit
    )
    
    return jsonify({
        'success': True,
        'count': len(alerts),
        'alerts': alerts
    })


@app.route('/api/alerts/summary', methods=['GET'])
def get_alerts_summary():
    """
    Get summary of recent alerts
    
    Query params:
        coin: Filter by coin (optional)
        days: Number of days to look back (default: 7)
    """
    coin = request.args.get('coin')
    days = request.args.get('days', 7, type=int)
    
    summary = db.get_alert_summary(coin=coin, days=days)
    
    return jsonify({
        'success': True,
        'days': days,
        'coin': coin,
        'summary': summary
    })


@app.route('/api/alerts/<int:alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id):
    """Acknowledge/dismiss an alert"""
    db.acknowledge_alert(alert_id)
    return jsonify({
        'success': True,
        'message': 'Alert acknowledged'
    })


@app.route('/api/alerts/scan', methods=['POST'])
def scan_for_alerts():
    """
    Manually trigger smart alert scanning for recent data
    
    JSON body:
        coin: Base coin (default: all configured coins)
        days: Number of days to scan (default: 7)
    """
    data = request.get_json() or {}
    requested_coin = data.get('coin')
    days = data.get('days', 7)
    
    # Determine which coins to scan
    if requested_coin:
        coins_to_scan = [requested_coin.upper()]
    else:
        coins_to_scan = config.get_coins()
    
    total_alerts = 0
    results = {}
    
    for coin in coins_to_scan:
        try:
            # Get recent data with indicators
            volume_data = db.get_volume_data(coin=coin, limit=days + 30)
            
            if not volume_data or len(volume_data) < 2:
                results[coin] = "Insufficient data"
                continue
            
            # Sort ascending for calculations
            volume_data = sorted(volume_data, key=lambda x: x['date'])
            
            # Add technical indicators
            volume_data = ind.enhance_volume_data_with_indicators(volume_data)
            
            # Detect smart actions on recent days
            alerts_for_coin = []
            for i in range(max(0, len(volume_data) - days), len(volume_data)):
                current_candle = volume_data[i]
                historical = volume_data[max(0, i - 30):i]
                
                alerts = wd.detect_all_smart_actions(current_candle, historical)
                alerts_for_coin.extend(alerts)
            
            # Save alerts to database
            for alert in alerts_for_coin:
                db.upsert_smart_alert(alert)
            
            results[coin] = f"{len(alerts_for_coin)} alerts"
            total_alerts += len(alerts_for_coin)
            
        except Exception as e:
            results[coin] = f"Error: {str(e)}"
    
    return jsonify({
        'success': True,
        'message': f'Scanned and found {total_alerts} alerts',
        'results': results
    })


# =============================================================================
# FUTURES MARKET API ENDPOINTS
# =============================================================================

@app.route('/api/futures', methods=['GET'])
def get_futures_data():
    """
    Get futures metrics (premium, funding rate, OI)
    
    Query params:
        coin: Base coin (default: BTC)
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        limit: Max records (default: 30)
    """
    coin = request.args.get('coin', 'BTC').upper()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    limit = request.args.get('limit', 30, type=int)
    
    metrics = db.get_futures_metrics(
        coin=coin,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )
    
    return jsonify({
        'success': True,
        'coin': coin,
        'count': len(metrics),
        'data': metrics
    })


@app.route('/api/futures/current', methods=['GET'])
def get_current_futures():
    """
    Get current real-time futures metrics
    
    Query params:
        coin: Base coin (default: BTC)
    """
    coin = request.args.get('coin', 'BTC').upper()
    
    try:
        # Get current spot price from recent data
        recent = db.get_volume_data(coin=coin, limit=1)
        spot_price = recent[0]['close_price'] if recent else None
        
        # Get futures metrics
        metrics = ft.get_futures_metrics(coin=coin, spot_price=spot_price)
        
        if not metrics:
            return jsonify({
                'success': False,
                'message': 'Could not fetch futures data'
            }), 404
        
        # Detect anomalies
        alerts = ft.detect_futures_anomalies(metrics)
        
        # Save to database
        db.upsert_futures_metrics(metrics)
        
        # Save alerts
        for alert in alerts:
            alert['date'] = datetime.now().strftime('%Y-%m-%d')
            db.upsert_smart_alert(alert)
        
        return jsonify({
            'success': True,
            'coin': coin,
            'metrics': metrics,
            'alerts': alerts
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/futures/liquidations', methods=['GET'])
def get_liquidation_zones():
    """
    Get estimated liquidation zones
    
    Query params:
        coin: Base coin (default: BTC)
    """
    coin = request.args.get('coin', 'BTC').upper()
    symbol = f"{coin}USDT"
    
    try:
        liq_data = ft.get_liquidation_estimates(symbol)
        
        if not liq_data:
            return jsonify({
                'success': False,
                'message': 'Could not fetch liquidation data'
            }), 404
        
        return jsonify({
            'success': True,
            'coin': coin,
            'data': liq_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# =============================================================================
# BACKGROUND SCHEDULER
# =============================================================================

def scheduled_sync():
    """Run scheduled daily full sync for all configured coins
    
    Attempts full sync first. If any error occurs (Binance or ETF),
    automatically falls back to incremental sync for that coin.
    Also runs smart alert detection on new data.
    """
    print(f"[{datetime.now()}] Running scheduled FULL sync...")
    
    coins = config.get_coins()
    
    for coin in coins:
        full_sync_success = False
        
        # Try full sync first
        try:
            print(f"  [{coin}] Attempting full sync...")
            volume_data = bf.fetch_coin_data(coin=coin, days=None)
            
            if volume_data:
                db.upsert_volume_data(volume_data)
                db.update_sync_status(coin)
                print(f"  [{coin}] Full sync complete: {len(volume_data)} records")
                full_sync_success = True
                
                # Run smart alert detection on recent data
                try:
                    print(f"  [{coin}] Running smart alert detection...")
                    recent_data = db.get_volume_data(coin=coin, limit=37)  # 30 for context + 7 for scanning
                    if recent_data and len(recent_data) >= 2:
                        recent_data = sorted(recent_data, key=lambda x: x['date'])
                        recent_data = ind.enhance_volume_data_with_indicators(recent_data)
                        
                        alerts_found = 0
                        for i in range(max(0, len(recent_data) - 7), len(recent_data)):
                            current = recent_data[i]
                            historical = recent_data[max(0, i - 30):i]
                            alerts = wd.detect_all_smart_actions(current, historical)
                            for alert in alerts:
                                db.upsert_smart_alert(alert)
                                alerts_found += 1
                        
                        print(f"  [{coin}] Smart alerts: {alerts_found} detected")
                except Exception as alert_err:
                    print(f"  [{coin}] Alert detection failed: {alert_err}")
            
            # Also sync ETF data if coin has ETF mapping
            etf_tickers = config.get_etfs_for_coin(coin)
            if etf_tickers:
                try:
                    etf_data = ef.fetch_etf_for_coin(coin)
                    if etf_data:
                        db.upsert_etf_data(etf_data)
                        print(f"  [{coin}] ETF sync complete: {len(etf_data)} records")
                except Exception as etf_err:
                    print(f"  [{coin}] ETF sync failed: {etf_err}")
                    # ETF failure doesn't trigger fallback, just log it
                    
        except Exception as e:
            print(f"  [{coin}] Full sync failed: {e}")
            print(f"  [{coin}] Falling back to incremental sync...")
            
            # Fallback to incremental sync
            try:
                latest_date = db.get_latest_date(coin)
                if latest_date:
                    volume_data = bf.fetch_coin_data(coin=coin, days=config.get_sync_days())
                else:
                    # Still no data and full sync failed - skip
                    print(f"  [{coin}] No existing data and full sync failed, skipping")
                    continue
                
                if volume_data:
                    db.upsert_volume_data(volume_data)
                    db.update_sync_status(coin)
                    print(f"  [{coin}] Incremental sync complete: {len(volume_data)} records")
            except Exception as fallback_err:
                print(f"  [{coin}] Incremental sync also failed: {fallback_err}")
    
    print(f"[{datetime.now()}] Scheduled sync complete")


def init_scheduler():
    """Initialize the background scheduler"""
    scheduler = BackgroundScheduler()
    
    sync_hour = config.get_sync_hour()
    
    # Run daily at specified hour UTC
    scheduler.add_job(
        scheduled_sync,
        'cron',
        hour=sync_hour,
        minute=5,
        id='daily_sync'
    )
    
    scheduler.start()
    print(f"Scheduler started. Daily sync at {sync_hour}:05 UTC")
    return scheduler


# =============================================================================
# STARTUP
# =============================================================================

def initial_sync():
    """Perform initial data sync if database is empty"""
    coins = config.get_coins()
    
    for coin in coins:
        date_range = db.get_date_range(coin)
        
        if not date_range or not date_range.get('count'):
            print(f"No data for {coin}. Performing initial sync...")
            
            def progress(count, msg):
                print(f"  {msg} ({count} records)")
            
            volume_data = bf.fetch_coin_data(
                coin=coin,
                days=None,
                progress_callback=progress
            )
            
            if volume_data:
                db.upsert_volume_data(volume_data)
                db.update_sync_status(coin)
                print(f"Initial sync complete for {coin}. Loaded {len(volume_data)} records.")
            else:
                print(f"Warning: Could not fetch data for {coin}.")
        else:
            print(f"{coin}: {date_range['count']} days from {date_range['earliest']} to {date_range['latest']}")


# Initialize database
db.init_database()

# Initialize scheduler (only in production, not during imports)
scheduler = None


if __name__ == '__main__':
    print("=" * 60)
    print("BTC Market Volume Tracker")
    print("=" * 60)
    print(f"Configured coins: {config.get_coins()}")
    print(f"Proxy: {config.get_proxy_url() or 'None'}")
    print()
    
    # Perform initial sync
    initial_sync()
    
    # Start scheduler
    scheduler = init_scheduler()
    
    # Run Flask app
    port = config.get_port()
    debug = config.is_debug()
    print(f"\nStarting server on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
