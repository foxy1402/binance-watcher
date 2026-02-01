/**
 * Crypto Volume Tracker - Frontend JavaScript
 * Price chart with Accumulation/Distribution zones
 */

const API_BASE = '';
const ROWS_PER_PAGE = 25;

// State
let currentCoin = 'BTC';
let configuredCoins = ['BTC'];
let etfMappings = {};  // coin -> ETF ticker
let volumeData = [];
let cumulativeData = [];
let etfData = [];
let currentPage = 1;
let sortColumn = 'date';
let sortDirection = 'desc';

// Charts
let priceZoneChart = null;
let netVolumeChart = null;
let cumulativeChart = null;
let etfZoneChart = null;

// =============================================================================
// Utilities
// =============================================================================

function formatNumber(num, decimals = 2) {
    if (num === null || num === undefined) return '--';
    return new Intl.NumberFormat('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(num);
}

function formatCurrency(num, compact = false) {
    if (num === null || num === undefined) return '--';
    if (compact) {
        const abs = Math.abs(num);
        if (abs >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
        if (abs >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
        if (abs >= 1e3) return `$${(num / 1e3).toFixed(2)}K`;
    }
    return new Intl.NumberFormat('en-US', {
        style: 'currency', currency: 'USD',
        minimumFractionDigits: 0, maximumFractionDigits: 0
    }).format(num);
}

function formatCoin(num, coin) {
    if (num === null || num === undefined) return '--';
    const prefix = num >= 0 ? '+' : '';
    return `${prefix}${formatNumber(num)} ${coin}`;
}

function showLoading(msg = 'Loading...') {
    document.getElementById('loadingText').textContent = msg;
    document.getElementById('loadingOverlay').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.add('hidden');
}

function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    toast.className = `toast ${type}`;
    document.getElementById('toastMessage').textContent = message;
    toast.classList.remove('hidden');
    setTimeout(() => toast.classList.add('hidden'), 4000);
}

function getDateRange(days) {
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - days);
    return { start: start.toISOString().split('T')[0], end: end.toISOString().split('T')[0] };
}

// =============================================================================
// API
// =============================================================================

async function fetchConfig() {
    const res = await fetch(`${API_BASE}/api/config`);
    const data = await res.json();
    if (data.success) {
        configuredCoins = data.coins;
        etfMappings = data.etf_mappings || {};
    }
    return data;
}

async function fetchVolumes(coin, startDate, endDate) {
    let url = `${API_BASE}/api/volumes?coin=${coin}`;
    if (startDate) url += `&start_date=${startDate}`;
    if (endDate) url += `&end_date=${endDate}`;
    const res = await fetch(url);
    const data = await res.json();
    if (data.success) return data.data;
    throw new Error(data.message || 'Failed');
}

async function fetchCumulative(coin, startDate) {
    let url = `${API_BASE}/api/volumes/cumulative?coin=${coin}`;
    if (startDate) url += `&start_date=${startDate}`;
    const res = await fetch(url);
    const data = await res.json();
    if (data.success) return data.data;
    throw new Error(data.message || 'Failed');
}

async function fetchSummary(coin) {
    const res = await fetch(`${API_BASE}/api/volumes/summary?coin=${coin}`);
    const data = await res.json();
    if (data.success) return { summary: data.summary, dateRange: data.date_range };
    throw new Error(data.message || 'Failed');
}

async function fetchSyncStatus(coin) {
    const res = await fetch(`${API_BASE}/api/sync/status?coin=${coin}`);
    const data = await res.json();
    return data.status;
}

async function triggerSync(coin, fullSync) {
    const res = await fetch(`${API_BASE}/api/sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ coin, full_sync: fullSync })
    });
    return await res.json();
}

// ETF API functions
async function fetchEtfData(coin, startDate, endDate) {
    let url = `${API_BASE}/api/etf?coin=${coin}`;
    if (startDate) url += `&start_date=${startDate}`;
    if (endDate) url += `&end_date=${endDate}`;
    const res = await fetch(url);
    const data = await res.json();
    if (data.success) return { data: data.data, ticker: data.etf_ticker };
    return { data: [], ticker: null };
}

async function triggerEtfSync(coin) {
    const res = await fetch(`${API_BASE}/api/etf/sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ coin })
    });
    return await res.json();
}

// =============================================================================
// Charts
// =============================================================================

function initCharts() {
    const baseOpts = {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: 'rgba(22, 27, 34, 0.95)',
                titleColor: '#f0f6fc',
                bodyColor: '#8b949e',
                borderColor: 'rgba(255,255,255,0.1)',
                borderWidth: 1,
                padding: 12
            }
        },
        scales: {
            x: {
                type: 'time',
                time: { unit: 'month', displayFormats: { month: 'MMM yy' } },
                grid: { color: 'rgba(255,255,255,0.05)' },
                ticks: { color: '#8b949e' }
            },
            y: {
                grid: { color: 'rgba(255,255,255,0.05)' },
                ticks: { color: '#8b949e' }
            }
        }
    };

    // Main Price Zone Chart - Price line with colored backgrounds
    const priceCtx = document.getElementById('priceZoneChart').getContext('2d');
    priceZoneChart = new Chart(priceCtx, {
        type: 'line',
        data: {
            datasets: [
                {
                    label: 'Coin Price',
                    data: [],
                    borderColor: '#58a6ff',
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    tension: 0.1,
                    fill: false,
                    yAxisID: 'yPrice',
                    order: 1
                },
                {
                    label: 'Accumulation',
                    data: [],
                    backgroundColor: 'rgba(63, 185, 80, 0.3)',
                    borderColor: 'rgba(63, 185, 80, 0.6)',
                    borderWidth: 0,
                    pointRadius: 0,
                    fill: 'origin',
                    yAxisID: 'yPrice',
                    order: 2
                },
                {
                    label: 'Distribution',
                    data: [],
                    backgroundColor: 'rgba(248, 81, 73, 0.3)',
                    borderColor: 'rgba(248, 81, 73, 0.6)',
                    borderWidth: 0,
                    pointRadius: 0,
                    fill: 'origin',
                    yAxisID: 'yPrice',
                    order: 2
                }
            ]
        },
        options: {
            ...baseOpts,
            scales: {
                x: { ...baseOpts.scales.x },
                yPrice: {
                    type: 'linear',
                    position: 'left',
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: {
                        color: '#8b949e',
                        callback: (v) => '$' + formatNumber(v, 0)
                    },
                    title: { display: true, text: 'Price (USD)', color: '#8b949e' }
                }
            },
            plugins: {
                ...baseOpts.plugins,
                tooltip: {
                    ...baseOpts.plugins.tooltip,
                    callbacks: {
                        label: (ctx) => {
                            if (ctx.dataset.label === 'Coin Price') {
                                return `Price: $${formatNumber(ctx.parsed.y, 2)}`;
                            }
                            return null;
                        }
                    }
                }
            }
        }
    });

    // Net Volume Chart
    const netCtx = document.getElementById('netVolumeChart').getContext('2d');
    netVolumeChart = new Chart(netCtx, {
        type: 'bar',
        data: { datasets: [{ data: [], backgroundColor: [] }] },
        options: {
            ...baseOpts,
            plugins: {
                ...baseOpts.plugins,
                tooltip: {
                    ...baseOpts.plugins.tooltip,
                    callbacks: { label: (ctx) => `Net: ${formatCoin(ctx.raw, currentCoin)}` }
                }
            }
        }
    });

    // Cumulative Chart
    const cumCtx = document.getElementById('cumulativeChart').getContext('2d');
    cumulativeChart = new Chart(cumCtx, {
        type: 'line',
        data: {
            datasets: [{
                data: [],
                borderColor: '#58a6ff',
                backgroundColor: 'rgba(88, 166, 255, 0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 0
            }]
        },
        options: baseOpts
    });

    // ETF Zone Chart (same structure as price zone chart)
    const etfCtx = document.getElementById('etfZoneChart');
    if (etfCtx) {
        etfZoneChart = new Chart(etfCtx.getContext('2d'), {
            type: 'line',
            data: {
                datasets: [
                    {
                        label: 'ETF Price',
                        data: [],
                        borderColor: '#a371f7',
                        borderWidth: 2,
                        pointRadius: 0,
                        pointHoverRadius: 5,
                        tension: 0.1,
                        fill: false,
                        yAxisID: 'yPrice',
                        order: 1
                    },
                    {
                        label: 'Accumulation',
                        data: [],
                        backgroundColor: 'rgba(63, 185, 80, 0.3)',
                        borderColor: 'rgba(63, 185, 80, 0.6)',
                        borderWidth: 0,
                        pointRadius: 0,
                        fill: 'origin',
                        yAxisID: 'yPrice',
                        order: 2
                    },
                    {
                        label: 'Distribution',
                        data: [],
                        backgroundColor: 'rgba(248, 81, 73, 0.3)',
                        borderColor: 'rgba(248, 81, 73, 0.6)',
                        borderWidth: 0,
                        pointRadius: 0,
                        fill: 'origin',
                        yAxisID: 'yPrice',
                        order: 2
                    }
                ]
            },
            options: {
                ...baseOpts,
                scales: {
                    x: { ...baseOpts.scales.x },
                    yPrice: {
                        type: 'linear',
                        position: 'left',
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: {
                            color: '#8b949e',
                            callback: (v) => '$' + formatNumber(v, 2)
                        },
                        title: { display: true, text: 'Coin Price (USD)', color: '#8b949e' }
                    }
                },
                plugins: {
                    ...baseOpts.plugins,
                    tooltip: {
                        ...baseOpts.plugins.tooltip,
                        callbacks: {
                            label: (ctx) => {
                                if (ctx.dataset.label === 'ETF Price') {
                                    return `Price: $${formatNumber(ctx.parsed.y, 2)}`;
                                }
                                return null;
                            }
                        }
                    }
                }
            }
        });
    }
}

function updateCharts() {
    const sorted = [...volumeData].sort((a, b) => new Date(a.date) - new Date(b.date));

    // Build price data and zone backgrounds
    const priceData = [];
    const accumulationData = [];
    const distributionData = [];

    for (const d of sorted) {
        const date = new Date(d.date);
        const price = d.close_price;
        const isAccumulation = d.net_volume > 0;

        priceData.push({ x: date, y: price });

        // For accumulation zones: show price where buying happened
        if (isAccumulation) {
            accumulationData.push({ x: date, y: price });
            distributionData.push({ x: date, y: null });
        } else {
            // For distribution zones: show price where selling happened
            accumulationData.push({ x: date, y: null });
            distributionData.push({ x: date, y: price });
        }
    }

    // Update Price Zone Chart
    priceZoneChart.data.datasets[0].data = priceData;
    priceZoneChart.data.datasets[1].data = accumulationData;
    priceZoneChart.data.datasets[2].data = distributionData;
    priceZoneChart.update('none');

    // Net Volume Chart
    netVolumeChart.data.labels = sorted.map(d => new Date(d.date));
    netVolumeChart.data.datasets[0].data = sorted.map(d => d.net_volume);
    netVolumeChart.data.datasets[0].backgroundColor = sorted.map(d =>
        d.net_volume >= 0 ? 'rgba(63, 185, 80, 0.8)' : 'rgba(248, 81, 73, 0.8)'
    );
    netVolumeChart.update('none');

    // Cumulative Chart
    if (cumulativeData.length) {
        const sortedCum = [...cumulativeData].sort((a, b) => new Date(a.date) - new Date(b.date));
        cumulativeChart.data.labels = sortedCum.map(d => new Date(d.date));
        cumulativeChart.data.datasets[0].data = sortedCum.map(d => d.cumulative_volume);
        const last = sortedCum[sortedCum.length - 1]?.cumulative_volume || 0;
        cumulativeChart.data.datasets[0].borderColor = last >= 0 ? '#3fb950' : '#f85149';
        cumulativeChart.data.datasets[0].backgroundColor = last >= 0
            ? 'rgba(63, 185, 80, 0.1)' : 'rgba(248, 81, 73, 0.1)';
        cumulativeChart.update('none');
    }
}

function updateEtfChart() {
    if (!etfZoneChart || !etfData.length || !volumeData.length) {
        // Hide ETF section if no data
        document.getElementById('etfChartSection')?.classList.add('hidden');
        return;
    }

    // Show ETF section
    document.getElementById('etfChartSection')?.classList.remove('hidden');

    // Create a map of ETF data by date for quick lookup
    const etfByDate = {};
    let earliestEtfDate = null;
    for (const d of etfData) {
        etfByDate[d.date] = d;
        if (!earliestEtfDate || d.date < earliestEtfDate) {
            earliestEtfDate = d.date;
        }
    }

    // Use coin price from volumeData, but only starting from the earliest ETF data date
    // This ensures the chart only shows the period when ETF data is available
    const sorted = [...volumeData]
        .filter(d => d.date >= earliestEtfDate)  // Filter to only dates with ETF data available
        .sort((a, b) => new Date(a.date) - new Date(b.date));

    // Build price data and zone backgrounds based on ETF signals
    const priceData = [];
    const accumulationData = [];
    const distributionData = [];

    for (const d of sorted) {
        const date = new Date(d.date);
        const price = d.close_price;  // Coin price from Binance
        const etfRecord = etfByDate[d.date];

        priceData.push({ x: date, y: price });

        // Use ETF net_volume to determine zone coloring (if ETF data exists for this date)
        if (etfRecord) {
            const isAccumulation = etfRecord.net_volume > 0;

            if (isAccumulation) {
                accumulationData.push({ x: date, y: price });
                distributionData.push({ x: date, y: null });
            } else {
                accumulationData.push({ x: date, y: null });
                distributionData.push({ x: date, y: price });
            }
        } else {
            // No ETF data for this date - no zone coloring
            accumulationData.push({ x: date, y: null });
            distributionData.push({ x: date, y: null });
        }
    }

    // Update ETF Zone Chart
    etfZoneChart.data.datasets[0].data = priceData;
    etfZoneChart.data.datasets[1].data = accumulationData;
    etfZoneChart.data.datasets[2].data = distributionData;
    etfZoneChart.update('none');
}

// =============================================================================
// Stats & Trends
// =============================================================================

function updateStats(summary, dateRange) {
    if (!summary) return;

    document.getElementById('totalBuyVolume').textContent = formatNumber(summary.total_buy_volume, 0) + ' ' + currentCoin;
    document.getElementById('totalBuyUsd').textContent = formatCurrency(summary.total_buy_usd, true);
    document.getElementById('totalSellVolume').textContent = formatNumber(summary.total_sell_volume, 0) + ' ' + currentCoin;
    document.getElementById('totalSellUsd').textContent = formatCurrency(summary.total_sell_usd, true);

    const net = summary.total_net_volume || 0;
    const netEl = document.getElementById('totalNetVolume');
    netEl.textContent = formatCoin(net, currentCoin);
    netEl.className = `stat-value ${net >= 0 ? 'cell-positive' : 'cell-negative'}`;
    document.getElementById('totalNetUsd').textContent = formatCurrency(summary.total_net_usd, true);

    if (dateRange) {
        document.getElementById('dataRange').textContent = `${dateRange.earliest || '--'} → ${dateRange.latest || '--'}`;
        document.getElementById('totalDays').textContent = `${dateRange.count || 0} days`;
    }
}

function calculateTrends() {
    if (volumeData.length < 7) return;
    const sorted = [...volumeData].sort((a, b) => new Date(b.date) - new Date(a.date));

    const calc = (days) => sorted.length >= days
        ? sorted.slice(0, days).reduce((s, d) => s + (d.net_volume || 0), 0)
        : null;

    const set = (id, labelId, val) => {
        const el = document.getElementById(id);
        const lbl = document.getElementById(labelId);
        if (val !== null) {
            el.textContent = formatCoin(val, currentCoin);
            el.className = `metric-value ${val >= 0 ? 'positive' : 'negative'}`;
            lbl.textContent = val >= 0 ? '🟢 Accumulation' : '🔴 Distribution';
        }
    };

    set('trend7d', 'trend7dLabel', calc(7));
    set('trend30d', 'trend30dLabel', calc(30));
    set('trend90d', 'trend90dLabel', calc(90));
}

async function updateSyncStatus() {
    try {
        const status = await fetchSyncStatus(currentCoin);
        document.getElementById('lastSync').textContent = status?.last_sync_timestamp
            ? new Date(status.last_sync_timestamp).toLocaleDateString() : 'Never';
        document.getElementById('syncStatus').textContent = status?.total_records
            ? `${status.total_records} days` : 'Click Sync';
    } catch (e) { console.error(e); }
}

// =============================================================================
// Table
// =============================================================================

function renderTable() {
    const tbody = document.getElementById('volumeTableBody');
    const search = document.getElementById('tableSearch').value.toLowerCase();
    let filtered = volumeData;
    if (search) filtered = volumeData.filter(d => d.date.includes(search));

    filtered.sort((a, b) => {
        let av = a[sortColumn], bv = b[sortColumn];
        if (sortColumn === 'date') { av = new Date(av); bv = new Date(bv); }
        return sortDirection === 'asc' ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1);
    });

    const totalPages = Math.ceil(filtered.length / ROWS_PER_PAGE);
    const start = (currentPage - 1) * ROWS_PER_PAGE;
    const page = filtered.slice(start, start + ROWS_PER_PAGE);

    tbody.innerHTML = page.map(d => `
        <tr>
            <td>${d.date}</td>
            <td>$${formatNumber(d.close_price, 2)}</td>
            <td class="cell-positive">${formatNumber(d.buy_volume, 1)}</td>
            <td class="cell-negative">${formatNumber(d.sell_volume, 1)}</td>
            <td class="${d.net_volume >= 0 ? 'cell-positive' : 'cell-negative'}">${formatCoin(d.net_volume, currentCoin)}</td>
            <td class="${d.net_volume >= 0 ? 'cell-positive' : 'cell-negative'}">${formatCurrency(d.net_volume_usd)}</td>
            <td><span class="zone-badge ${d.net_volume >= 0 ? 'zone-acc' : 'zone-dist'}">${d.net_volume >= 0 ? 'ACC' : 'DIST'}</span></td>
        </tr>
    `).join('');

    document.getElementById('pageInfo').textContent = `Page ${currentPage} of ${totalPages || 1}`;
    document.getElementById('prevPage').disabled = currentPage <= 1;
    document.getElementById('nextPage').disabled = currentPage >= totalPages;
}

// =============================================================================
// Events
// =============================================================================

function setupEvents() {
    document.getElementById('coinSelect').addEventListener('change', e => {
        currentCoin = e.target.value;
        loadData();
    });

    document.getElementById('syncBtn').addEventListener('click', async () => {
        showLoading('Syncing...');
        try {
            const res = await triggerSync(currentCoin, false);
            showToast(res.message || 'Synced!', res.success ? 'success' : 'error');
            if (res.success) await loadData();
        } catch (e) { showToast(e.message, 'error'); }
        hideLoading();
    });

    document.getElementById('fullSyncBtn').addEventListener('click', async () => {
        if (!confirm(`Fetch ALL history for ${currentCoin}?`)) return;
        showLoading(`Fetching all ${currentCoin}...`);
        try {
            const res = await triggerSync(currentCoin, true);

            // Also sync ETF data if coin has ETF mapping
            if (etfMappings[currentCoin]) {
                showLoading(`Fetching ETF data for ${currentCoin}...`);
                await triggerEtfSync(currentCoin);
            }

            showToast(res.message || 'Done!', res.success ? 'success' : 'error');
            if (res.success) await loadData();
        } catch (e) { showToast(e.message, 'error'); }
        hideLoading();
    });

    document.getElementById('exportBtn').addEventListener('click', () => {
        const s = document.getElementById('startDate').value;
        const e = document.getElementById('endDate').value;
        let url = `${API_BASE}/api/export?coin=${currentCoin}`;
        if (s) url += `&start_date=${s}`;
        if (e) url += `&end_date=${e}`;
        window.location.href = url;
    });

    document.querySelectorAll('.quick-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.quick-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const days = parseInt(btn.dataset.days);
            if (days === 0) {
                document.getElementById('startDate').value = '';
                document.getElementById('endDate').value = '';
            } else {
                const r = getDateRange(days);
                document.getElementById('startDate').value = r.start;
                document.getElementById('endDate').value = r.end;
            }
        });
    });

    document.getElementById('applyFilter').addEventListener('click', () => loadData());
    document.getElementById('tableSearch').addEventListener('input', () => { currentPage = 1; renderTable(); });

    document.querySelectorAll('th[data-sort]').forEach(th => {
        th.addEventListener('click', () => {
            const col = th.dataset.sort;
            sortDirection = sortColumn === col && sortDirection === 'desc' ? 'asc' : 'desc';
            sortColumn = col;
            renderTable();
        });
    });

    document.getElementById('prevPage').addEventListener('click', () => { if (currentPage > 1) { currentPage--; renderTable(); } });
    document.getElementById('nextPage').addEventListener('click', () => {
        const total = Math.ceil(volumeData.length / ROWS_PER_PAGE);
        if (currentPage < total) { currentPage++; renderTable(); }
    });
}

// =============================================================================
// Data Loading
// =============================================================================

async function loadData() {
    showLoading(`Loading ${currentCoin}...`);
    try {
        const s = document.getElementById('startDate').value || null;
        const e = document.getElementById('endDate').value || null;

        const [volumes, cumulative, summaryData] = await Promise.all([
            fetchVolumes(currentCoin, s, e),
            fetchCumulative(currentCoin, s),
            fetchSummary(currentCoin)
        ]);

        volumeData = volumes;
        cumulativeData = cumulative;

        updateStats(summaryData.summary, summaryData.dateRange);
        updateCharts();
        calculateTrends();
        renderTable();
        updateSyncStatus();

        // Load ETF data if coin has ETF mapping
        const etfTicker = etfMappings[currentCoin];
        if (etfTicker) {
            try {
                const etfResult = await fetchEtfData(currentCoin, s, e);
                etfData = etfResult.data || [];

                // Update ETF chart title and ticker
                document.getElementById('etfChartTitle').textContent = `${currentCoin} ETF (${etfTicker})`;
                document.getElementById('etfTicker').textContent = etfTicker;

                updateEtfChart();
            } catch (etfErr) {
                console.log('ETF data not available:', etfErr);
                etfData = [];
                document.getElementById('etfChartSection')?.classList.add('hidden');
            }
        } else {
            // No ETF for this coin - hide section
            etfData = [];
            document.getElementById('etfChartSection')?.classList.add('hidden');
        }
    } catch (e) {
        console.error(e);
        showToast('Error: ' + e.message, 'error');
    }
    hideLoading();
}

async function init() {
    await fetchConfig();
    const select = document.getElementById('coinSelect');
    select.innerHTML = configuredCoins.map(c => `<option value="${c}">${c}</option>`).join('');
    currentCoin = configuredCoins[0] || 'BTC';
    initCharts();
    setupEvents();
    loadData();
}

document.addEventListener('DOMContentLoaded', init);

// =============================================================================
// Smart Alerts
// =============================================================================

let currentAlerts = [];
let currentSeverityFilter = '';

async function fetchAlerts(coin, severity = null) {
    let url = `${API_BASE}/api/alerts?coin=${coin}&limit=50`;
    if (severity) url += `&severity=${severity}`;
    const res = await fetch(url);
    const data = await res.json();
    if (data.success) return data.alerts;
    return [];
}

async function fetchAlertsSummary(coin) {
    const res = await fetch(`${API_BASE}/api/alerts/summary?coin=${coin}&days=7`);
    const data = await res.json();
    if (data.success) return data.summary;
    return null;
}

async function scanForAlerts(coin = null) {
    const res = await fetch(`${API_BASE}/api/alerts/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ coin: coin || currentCoin, days: 7 })
    });
    return await res.json();
}

function getAlertIcon(alertType) {
    const icons = {
        'whale_buy': '🐋',
        'whale_sell': '🐋',
        'whale_accumulation': '💰',
        'whale_distribution': '📤',
        'volume_spike': '📊',
        'buy_volume_spike': '📈',
        'sell_volume_spike': '📉',
        'bullish_divergence': '⬆️',
        'bearish_divergence': '⬇️',
        'rsi_oversold': '🔵',
        'rsi_overbought': '🔴',
        'high_futures_premium': '⚡',
        'futures_discount': '⚡',
        'extreme_funding_rate': '💸',
        'extreme_negative_funding': '💸',
        'backwardation_signal': '🎯',
        'contango_warning': '⚠️'
    };
    return icons[alertType] || '🚨';
}

function renderAlertsFeed() {
    const feed = document.getElementById('alertsFeed');
    
    if (!currentAlerts || currentAlerts.length === 0) {
        feed.innerHTML = `
            <div class="alerts-empty">
                <div class="alerts-empty-icon">🔍</div>
                <h3>No alerts found</h3>
                <p>Click "Scan Now" to detect whale trades and unusual activity</p>
            </div>
        `;
        return;
    }
    
    feed.innerHTML = currentAlerts.map(alert => {
        const icon = getAlertIcon(alert.alert_type);
        const severity = alert.severity || 'low';
        const date = new Date(alert.timestamp || alert.date);
        const timeAgo = formatTimeAgo(date);
        
        // Build metadata items
        const metaItems = [];
        
        if (alert.value_usd) {
            metaItems.push(`
                <div class="alert-meta-item">
                    <span class="alert-meta-label">Value</span>
                    <span class="alert-meta-value">${formatCurrency(alert.value_usd, true)}</span>
                </div>
            `);
        }
        
        if (alert.volume) {
            metaItems.push(`
                <div class="alert-meta-item">
                    <span class="alert-meta-label">Volume</span>
                    <span class="alert-meta-value">${formatNumber(alert.volume, 0)} ${alert.coin}</span>
                </div>
            `);
        }
        
        if (alert.zscore) {
            metaItems.push(`
                <div class="alert-meta-item">
                    <span class="alert-meta-label">Z-Score</span>
                    <span class="alert-meta-value ${alert.zscore > 0 ? 'positive' : 'negative'}">${alert.zscore.toFixed(2)}σ</span>
                </div>
            `);
        }
        
        if (alert.rsi) {
            metaItems.push(`
                <div class="alert-meta-item">
                    <span class="alert-meta-label">RSI</span>
                    <span class="alert-meta-value">${alert.rsi.toFixed(1)}</span>
                </div>
            `);
        }
        
        if (alert.price) {
            metaItems.push(`
                <div class="alert-meta-item">
                    <span class="alert-meta-label">Price</span>
                    <span class="alert-meta-value">$${formatNumber(alert.price, 2)}</span>
                </div>
            `);
        }
        
        return `
            <div class="alert-item ${severity}">
                <div class="alert-icon">${icon}</div>
                <div class="alert-content">
                    <div class="alert-header">
                        <div>
                            <span class="alert-type-badge">${alert.coin}</span>
                            <span class="alert-severity-badge ${severity}">${severity.toUpperCase()}</span>
                        </div>
                        <span class="alert-timestamp">${timeAgo}</span>
                    </div>
                    <h4 class="alert-title">${formatAlertType(alert.alert_type)}</h4>
                    <p class="alert-description">${alert.description || 'No description'}</p>
                    ${metaItems.length > 0 ? `
                        <div class="alert-meta">
                            ${metaItems.join('')}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');
}

function formatAlertType(type) {
    return type
        .replace(/_/g, ' ')
        .split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

function formatTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);
    
    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
    
    return date.toLocaleDateString();
}

function updateAlertSummary(summary) {
    if (!summary) {
        document.getElementById('criticalCount').textContent = '0';
        document.getElementById('highCount').textContent = '0';
        document.getElementById('mediumCount').textContent = '0';
        document.getElementById('lowCount').textContent = '0';
        return;
    }
    
    document.getElementById('criticalCount').textContent = summary.critical || '0';
    document.getElementById('highCount').textContent = summary.high || '0';
    document.getElementById('mediumCount').textContent = summary.medium || '0';
    document.getElementById('lowCount').textContent = summary.low || '0';
}

async function loadAlerts() {
    try {
        const [alerts, summary] = await Promise.all([
            fetchAlerts(currentCoin, currentSeverityFilter),
            fetchAlertsSummary(currentCoin)
        ]);
        
        currentAlerts = alerts;
        renderAlertsFeed();
        updateAlertSummary(summary);
    } catch (e) {
        console.error('Error loading alerts:', e);
        document.getElementById('alertsFeed').innerHTML = `
            <div class="alerts-empty">
                <div class="alerts-empty-icon">⚠️</div>
                <h3>Error loading alerts</h3>
                <p>${e.message}</p>
            </div>
        `;
    }
}

function setupAlertsEvents() {
    // Scan alerts button
    document.getElementById('scanAlertsBtn').addEventListener('click', async () => {
        showLoading('Scanning for smart actions...');
        try {
            const res = await scanForAlerts();
            showToast(res.message || 'Scan complete!', res.success ? 'success' : 'error');
            if (res.success) await loadAlerts();
        } catch (e) {
            showToast('Error: ' + e.message, 'error');
        }
        hideLoading();
    });
    
    // Severity filter
    document.getElementById('alertSeverityFilter').addEventListener('change', (e) => {
        currentSeverityFilter = e.target.value;
        loadAlerts();
    });
}

// Modify the init function to include alerts
const originalInit = init;
init = async function() {
    await originalInit();
    setupAlertsEvents();
    loadAlerts();
};

