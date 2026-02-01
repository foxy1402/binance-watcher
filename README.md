# Crypto Volume Tracker - Smart Money Edition

A professional investment tracking tool that detects whale trades, unusual volumes, and smart money movements on cryptocurrency markets. Track Binance spot volumes, ETF flows, futures premium, and get real-time alerts on significant market events.

## 🚀 New Smart Money Features

### 1. **Whale Detection System**
- Automatically detects large orders (>$500K, >$1M, >$5M, >$10M)
- Tracks massive accumulation and distribution events
- Real-time severity classification (Critical, High, Medium, Low)

### 2. **Volume Anomaly Detection**
- Statistical Z-score analysis for unusual volume spikes
- Detects buying/selling pressure anomalies
- Identifies market manipulation patterns

### 3. **Technical Indicators**
- **VWAP** (Volume Weighted Average Price)
- **RSI** (Relative Strength Index) with overbought/oversold signals
- **MACD** (Moving Average Convergence Divergence)
- **Bollinger Bands** for volatility analysis
- **OBV** (On-Balance Volume) for trend confirmation

### 4. **Price-Volume Divergence**
- Detects bullish divergence (price down but accumulation)
- Detects bearish divergence (price up but distribution)
- Early warning signals for trend reversals

### 5. **Futures Market Analysis**
- Futures vs. Spot premium/discount tracking
- Funding rate monitoring (8-hour and annualized)
- Open interest tracking
- Liquidation zone estimates
- Contango/backwardation detection

### 6. **Smart Alerts Dashboard**
- Real-time alert feed with severity filtering
- Alert summary cards (Critical, High, Medium, Low)
- Detailed metadata for each alert
- Time-based filtering

### 7. **Enhanced ETF Algorithm**
- Improved buy/sell volume estimation using close position in daily range
- Momentum-adjusted calculations
- Better accuracy for accumulation/distribution detection

## Features

- **Daily Volume Tracking**: Track taker buy/sell volumes from Binance (USDT + USDC pairs combined)
- **Net Volume Analysis**: See if there's more buying or selling pressure
- **Accumulation/Distribution Zones**: Visual chart overlay showing where buying (green) vs selling (red) occurred
- **ETF Flow Tracking**: Track Bitcoin and Ethereum ETF volumes (IBIT, FBTC, GBTC, etc.) via Yahoo Finance
- **Multi-Coin Support**: Track BTC, ETH, SOL, NEAR, LINK, AAVE and more
- **Historical Data**: Fetch all available historical data (back to 2017 for BTC)
- **Interactive Charts**: Price with zone overlay, net volume bars, cumulative trends
- **USD Valuation**: All metrics shown in both coin units and USD
- **Auto-Sync**: Daily automatic updates via background scheduler
- **Export**: Download data as CSV for external analysis

## Quick Start

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/foxy1402/binance-watcher.git
   cd binance-watcher
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # or
   source venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Open in browser**
   ```
   http://localhost:5000
   ```

On first run, click "Full Sync" to fetch all historical data from Binance.

## Configuration

Edit `config.ini` to customize:

```ini
# Coins to track (comma-separated)
COINS = BTC,ETH,SOL,NEAR,LINK,AAVE

# ETF mappings (coin=ETF_TICKER, use | for multiple ETFs per coin)
ETF_VOLUME = BTC=IBIT|FBTC|ARKB|BITB|BTCO|EZBC|BRRR|HODL|BTCW|GBTC,ETH=ETHA|FETH|ETHW|CETH|ETHV|EZET|QETH|ETHE

# Optional HTTP/SOCKS5 proxy for Binance API
PROXY_URL = 

# Auto-sync settings
SYNC_HOUR = 1
SYNC_DAYS = 7
```

### Environment Variables

You can also configure the app using environment variables (takes priority over `config.ini`):

| Variable | Description | Example |
|----------|-------------|---------|
| `PROXY_URL` | HTTP/SOCKS5 proxy for Binance API | `http://user:pass@host:port` or `socks5://host:port` |
| `DATABASE_PATH` | SQLite database path | `volume_data.db` |
| `PORT` | Server port | `5000` |

**Example (Windows PowerShell):**
```powershell
$env:PROXY_URL = "socks5://127.0.0.1:1080"
python app.py
```

**Example (Linux/Mac):**
```bash
export PROXY_URL="socks5://127.0.0.1:1080"
python app.py
```

## Deploy to Render.com

### Blueprint (Recommended)

1. Fork this repository
2. Go to [Render Dashboard](https://dashboard.render.com/)
3. Click "New" → "Blueprint"
4. Connect your forked repository
5. Render will automatically detect `render.yaml` and configure everything

### Manual Setup

1. Create a new "Web Service" on Render
2. Connect your repository
3. Configure:
   - **Region**: Singapore (for Binance access)
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`

## API Endpoints

### Volume Data
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard |
| `/api/volumes` | GET | Get volume data with filters (add `include_indicators=true` for RSI, MACD, etc.) |
| `/api/volumes/summary` | GET | Get aggregated statistics |
| `/api/volumes/cumulative` | GET | Get cumulative net volume |
| `/api/sync` | POST | Trigger Binance data sync |
| `/api/export` | GET | Export data as CSV |

### ETF Data
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/etf` | GET | Get ETF volume data |
| `/api/etf/sync` | POST | Trigger ETF data sync |

### Smart Alerts
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/alerts` | GET | Get smart alerts (filter by severity, type, date) |
| `/api/alerts/summary` | GET | Get alert summary statistics |
| `/api/alerts/scan` | POST | Trigger manual alert scan |
| `/api/alerts/<id>/acknowledge` | POST | Acknowledge/dismiss an alert |

### Futures Market
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/futures` | GET | Get historical futures metrics |
| `/api/futures/current` | GET | Get real-time futures data (premium, funding rate, OI) |
| `/api/futures/liquidations` | GET | Get estimated liquidation zones |

### Configuration
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/config` | GET | Get app configuration |
| `/api/coins` | GET | Get list of tracked coins |

## Understanding the Data

### Volume Types

- **Taker Buy Volume**: Volume driven by buyers (market buy orders hitting the ask)
- **Taker Sell Volume**: Volume driven by sellers (market sell orders hitting the bid)
- **Net Volume**: Buy Volume - Sell Volume

### Zone Interpretation

| Zone | Color | Meaning |
|------|-------|---------|
| Accumulation | 🟢 Green | Net buying pressure (smart money buying) |
| Distribution | 🔴 Red | Net selling pressure (smart money selling) |

### Trend Indicators

- **7-Day Trend**: Short-term accumulation/distribution
- **30-Day Trend**: Medium-term market sentiment
- **90-Day Trend**: Longer-term positioning
- **Cumulative Net Volume**: Overall historical buying/selling balance

### Smart Alert Types

| Alert Type | Severity | Description |
|------------|----------|-------------|
| **Mega Whale** | 🔴 Critical | Transactions >$10M |
| **Large Whale** | 🟠 High | Transactions $5M-$10M |
| **Medium Whale** | 🟡 Medium | Transactions $1M-$5M |
| **Volume Spike** | 🟠 High | Z-score > 2.5 (99% confidence) |
| **Bullish Divergence** | 🟡 Medium | Price ↓ but accumulation |
| **Bearish Divergence** | 🟡 Medium | Price ↑ but distribution |
| **RSI Oversold** | 🟢 Low | RSI < 30 (potential buy zone) |
| **RSI Overbought** | 🔴 High | RSI > 70 (potential sell zone) |
| **Extreme Funding** | 🔴 Critical | Funding rate >100% annualized |
| **Futures Premium** | 🟠 High | Futures > Spot by >0.5% |

### Futures Metrics

- **Premium/Discount**: Difference between futures and spot price
- **Funding Rate**: Fee paid by longs (positive) or shorts (negative) every 8 hours
- **Annualized Funding**: Funding rate projected over a year (×3×365)
- **Open Interest**: Total value of outstanding futures contracts
- **Liquidation Zones**: Estimated price levels where leveraged positions get liquidated

**Interpretation:**
- **Positive Funding + Premium**: Market overheated, potential correction
- **Negative Funding + Discount**: Market fear, potential bounce
- **High OI + Rising Price**: Strong trend confirmation
- **High OI + Falling Price**: Liquidation cascade risk

## Technical Indicators Guide

### VWAP (Volume Weighted Average Price)
- Price weighted by volume - shows "fair value"
- Price above VWAP = bullish, below = bearish
- Institutions often use VWAP for entry/exit decisions

### RSI (Relative Strength Index)
- Measures momentum on 0-100 scale
- < 30: Oversold (potential buy)
- \> 70: Overbought (potential sell)
- 50: Neutral

### MACD (Moving Average Convergence Divergence)
- Shows trend direction and momentum
- MACD > Signal: Bullish
- MACD < Signal: Bearish
- Histogram crossing zero: Trend reversal

### Bollinger Bands
- Shows volatility and potential reversal zones
- Price at upper band: Overbought
- Price at lower band: Oversold
- Squeeze (narrow bands): Low volatility, potential breakout

### Z-Score (Volume Anomaly)
- Measures how unusual current volume is
- Z > 2.5: Highly unusual (99% confidence)
- Z > 3.0: Extremely unusual
- Higher Z-score = more significant event

## Project Structure

```
binance-watcher/
├── app.py                  # Flask application & API routes
├── database.py             # SQLite database operations
├── binance_fetcher.py      # Binance API client (spot data)
├── etf_fetcher.py          # Yahoo Finance ETF data fetcher (improved algorithm)
├── futures_tracker.py      # Binance Futures API client (premium, funding, OI)
├── whale_detector.py       # Whale detection & smart money tracking
├── indicators.py           # Technical indicators (VWAP, RSI, MACD, etc.)
├── config.py               # Configuration loader
├── config.ini              # User configuration file
├── requirements.txt        # Python dependencies
├── render.yaml             # Render.com deployment config
├── Procfile                # Process configuration
├── templates/
│   └── index.html          # Dashboard template (with smart alerts)
└── static/
    ├── css/
    │   └── style.css       # Styles (with alert components)
    └── js/
        └── app.js          # Frontend JavaScript (with alerts logic)
```

## Usage Examples

### Get Volume Data with Technical Indicators
```bash
curl "http://localhost:5000/api/volumes?coin=BTC&include_indicators=true&limit=30"
```

### Scan for Smart Actions
```bash
curl -X POST "http://localhost:5000/api/alerts/scan" \
  -H "Content-Type: application/json" \
  -d '{"coin":"BTC","days":7}'
```

### Get Smart Alerts (Critical Only)
```bash
curl "http://localhost:5000/api/alerts?coin=BTC&severity=critical"
```

### Get Current Futures Metrics
```bash
curl "http://localhost:5000/api/futures/current?coin=BTC"
```

### Get Alert Summary
```bash
curl "http://localhost:5000/api/alerts/summary?coin=BTC&days=7"
```

## Advanced Configuration

### Whale Detection Thresholds
Edit `whale_detector.py` to customize thresholds:
```python
WHALE_THRESHOLDS = {
    'small_whale': 500_000,      # $500K
    'medium_whale': 1_000_000,   # $1M
    'large_whale': 5_000_000,    # $5M
    'mega_whale': 10_000_000     # $10M
}
```

### Volume Anomaly Sensitivity
```python
VOLUME_ANOMALY_THRESHOLD = 2.5  # Z-score (2.5 = 99% confidence)
```

### Technical Indicator Periods
```python
# RSI Period
rsi_values = calculate_rsi(prices, period=14)

# MACD Settings
macd_data = calculate_macd(prices, fast=12, slow=26, signal=9)

# Bollinger Bands
bb_data = calculate_bollinger_bands(prices, period=20, std_dev=2.0)
```

## Database Schema

### Smart Alerts Table
```sql
CREATE TABLE smart_alerts (
    id INTEGER PRIMARY KEY,
    coin TEXT NOT NULL,
    date DATE NOT NULL,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,  -- critical, high, medium, low
    description TEXT,
    value_usd REAL,
    volume REAL,
    price REAL,
    zscore REAL,
    size_class TEXT,        -- mega_whale, large_whale, etc.
    rsi REAL,
    metadata TEXT,          -- JSON for additional data
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acknowledged INTEGER DEFAULT 0
);
```

### Futures Metrics Table
```sql
CREATE TABLE futures_metrics (
    id INTEGER PRIMARY KEY,
    coin TEXT NOT NULL,
    symbol TEXT NOT NULL,
    date DATE NOT NULL,
    spot_price REAL,
    futures_price REAL,
    premium_pct REAL,
    funding_rate REAL,
    funding_rate_annualized REAL,
    open_interest REAL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Performance & Scaling

### Rate Limiting
- Binance Spot: 1200 requests/minute (100ms delay between requests)
- Binance Futures: 2400 requests/minute (50ms delay)
- Yahoo Finance: 2000 requests/hour (200ms delay)

### Database Optimization
- Indexes on (coin, date) for fast queries
- Aggregated data reduces redundant calculations
- Cleanup old alerts (>90 days) automatically

### Memory Usage
- ~50MB base
- +10MB per 10,000 records
- Charts rendered client-side (offloads server)

## Troubleshooting

### No Alerts Appearing
1. Click "Scan Now" button to trigger detection
2. Check if you have enough historical data (need 30+ days)
3. Verify coins have recent sync data

### Futures Data Not Loading
- Ensure you have internet access to Binance Futures API
- Check if proxy is configured correctly
- Verify coin symbol exists on Binance Futures (BTCUSDT, ETHUSDT, etc.)

### High Memory Usage
- Reduce `limit` parameter in API calls
- Clear old alerts: `DELETE FROM smart_alerts WHERE date < date('now', '-90 days')`
- Reduce number of tracked coins in config

## Project Structure

## License

MIT License - Free for personal and commercial use.

## Disclaimer

This tool is for educational and informational purposes only. Not financial advice. Always do your own research before making investment decisions.
