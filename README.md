# Crypto Volume Tracker

A web application to track cryptocurrency buy/sell volumes from Binance and ETF flows, with visual accumulation/distribution zone analysis for long-term investment decisions.

## Features

- **Daily Volume Tracking**: Track taker buy/sell volumes from Binance (USDT + USDC pairs combined)
- **Net Volume Analysis**: See if there's more buying or selling pressure
- **Accumulation/Distribution Zones**: Visual chart overlay showing where buying (green) vs selling (red) occurred
- **ETF Flow Tracking**: Track Bitcoin and Ethereum ETF volumes (IBIT, ETHA, etc.) via Yahoo Finance
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

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard |
| `/api/volumes` | GET | Get volume data with filters |
| `/api/volumes/summary` | GET | Get aggregated statistics |
| `/api/volumes/cumulative` | GET | Get cumulative net volume |
| `/api/etf` | GET | Get ETF volume data |
| `/api/sync` | POST | Trigger Binance data sync |
| `/api/etf/sync` | POST | Trigger ETF data sync |
| `/api/config` | GET | Get app configuration |
| `/api/export` | GET | Export data as CSV |

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

## Project Structure

```
binance-watcher/
├── app.py                 # Flask application & API routes
├── database.py            # SQLite database operations
├── binance_fetcher.py     # Binance API client (spot data)
├── etf_fetcher.py         # Yahoo Finance ETF data fetcher
├── config.py              # Configuration loader
├── config.ini             # User configuration file
├── requirements.txt       # Python dependencies
├── render.yaml            # Render.com deployment config
├── Procfile               # Process configuration
├── templates/
│   └── index.html         # Dashboard template
└── static/
    ├── css/
    │   └── style.css      # Styles
    └── js/
        └── app.js         # Frontend JavaScript
```

## License

MIT License - Free for personal and commercial use.

## Disclaimer

This tool is for educational and informational purposes only. Not financial advice. Always do your own research before making investment decisions.
