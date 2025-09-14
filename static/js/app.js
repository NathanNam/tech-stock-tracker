/**
 * Tech Stock Tracker - Frontend JavaScript
 * Handles auto-refresh, manual refresh, and UI interactions
 */

class StockTracker {
    constructor() {
        this.refreshInterval = 60; // seconds
        this.countdownTimer = null;
        this.autoRefreshTimer = null;
        this.isRefreshing = false;
        
        this.init();
    }
    
    init() {
        console.log('Initializing Stock Tracker...');
        this.startCountdown();
        this.setupAutoRefresh();
        this.setupEventListeners();
        this.updateMarketStatus();
    }
    
    /**
     * Start the countdown timer
     */
    startCountdown() {
        let seconds = this.refreshInterval;
        const countdownElement = document.getElementById('countdown');
        const refreshCountdownElement = document.getElementById('refresh-countdown');
        
        if (this.countdownTimer) {
            clearInterval(this.countdownTimer);
        }
        
        this.countdownTimer = setInterval(() => {
            seconds--;
            
            if (countdownElement) {
                countdownElement.textContent = seconds;
                
                // Add animation for last 10 seconds
                if (seconds <= 10) {
                    countdownElement.classList.add('countdown-animation');
                } else {
                    countdownElement.classList.remove('countdown-animation');
                }
            }
            
            if (refreshCountdownElement) {
                refreshCountdownElement.textContent = `Next refresh in ${seconds}s`;
            }
            
            if (seconds <= 0) {
                this.resetCountdown();
            }
        }, 1000);
    }
    
    /**
     * Reset countdown to initial value
     */
    resetCountdown() {
        if (this.countdownTimer) {
            clearInterval(this.countdownTimer);
        }
        this.startCountdown();
    }
    
    /**
     * Setup auto-refresh functionality
     */
    setupAutoRefresh() {
        if (this.autoRefreshTimer) {
            clearInterval(this.autoRefreshTimer);
        }
        
        this.autoRefreshTimer = setInterval(() => {
            this.autoRefresh();
        }, this.refreshInterval * 1000);
    }
    
    /**
     * Auto-refresh stock data
     */
    async autoRefresh() {
        if (!this.isRefreshing) {
            console.log('Auto-refreshing stock data...');
            await this.refreshData();
        }
    }
    
    /**
     * Manual refresh triggered by user
     */
    async refreshData() {
        if (this.isRefreshing) return;
        
        this.isRefreshing = true;
        this.showLoadingState();
        
        try {
            const response = await fetch('/api/refresh', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showSuccess('Stock data refreshed successfully!');
                this.updateStockTable(result.data);
                this.updateLastUpdateTime();
                this.resetCountdown();
            } else {
                this.showError(`Failed to refresh data: ${result.error}`);
            }
        } catch (error) {
            console.error('Refresh error:', error);
            this.showError('Failed to refresh data. Please check your connection.');
        } finally {
            this.isRefreshing = false;
            this.hideLoadingState();
        }
    }
    
    /**
     * Update the stock table with new data
     */
    updateStockTable(stockData) {
        if (!stockData) {
            console.log('No stock data to update');
            return;
        }
        
        const tableBody = document.querySelector('#stocks-table tbody');
        if (!tableBody) {
            console.log('Stock table not found, reloading page...');
            window.location.reload();
            return;
        }
        
        // Update each row
        stockData.forEach(stock => {
            const row = document.querySelector(`tr[data-symbol="${stock.symbol}"]`);
            if (row) {
                this.updateStockRow(row, stock);
            }
        });
        
        this.updateStats(stockData);
    }
    
    /**
     * Update a single stock row
     */
    updateStockRow(row, stock) {
        const cells = row.querySelectorAll('td');
        if (cells.length < 6) return;
        
        // Price
        const priceCell = cells[2];
        const oldPrice = parseFloat(priceCell.textContent.replace('$', ''));
        const newPrice = stock.price;
        priceCell.textContent = `$${newPrice.toFixed(2)}`;
        
        // Animate price changes
        if (newPrice > oldPrice) {
            row.classList.add('price-up');
            setTimeout(() => row.classList.remove('price-up'), 600);
        } else if (newPrice < oldPrice) {
            row.classList.add('price-down');
            setTimeout(() => row.classList.remove('price-down'), 600);
        }
        
        // Change
        const changeCell = cells[3];
        const changeSpan = changeCell.querySelector('span');
        changeSpan.textContent = `${stock.change > 0 ? '+' : ''}$${stock.change.toFixed(2)}`;
        changeSpan.className = stock.is_positive ? 'text-success' : stock.is_negative ? 'text-danger' : 'text-muted';
        
        // Change %
        const changePercentCell = cells[4];
        const changePercentSpan = changePercentCell.querySelector('span');
        changePercentSpan.textContent = `${stock.change_percent > 0 ? '+' : ''}${stock.change_percent.toFixed(2)}%`;
        changePercentSpan.className = (stock.is_positive ? 'text-success' : stock.is_negative ? 'text-danger' : 'text-muted') + ' fw-bold';
        
        // Volume
        const volumeCell = cells[5];
        volumeCell.textContent = `${stock.volume_millions.toFixed(1)}M`;
    }
    
    /**
     * Update statistics cards
     */
    updateStats(stockData) {
        const stocksUp = stockData.filter(s => s.is_positive).length;
        const stocksDown = stockData.filter(s => s.is_negative).length;
        
        const statsCards = document.querySelectorAll('.card-title');
        if (statsCards.length >= 3) {
            statsCards[0].textContent = stocksUp;
            statsCards[1].textContent = stocksDown;
            statsCards[2].textContent = stockData.length;
        }
    }
    
    /**
     * Show loading state
     */
    showLoadingState() {
        const loadingIndicator = document.getElementById('loading-indicator');
        const stocksTable = document.getElementById('stocks-table');
        
        if (loadingIndicator) {
            loadingIndicator.classList.remove('d-none');
        }
        
        if (stocksTable) {
            stocksTable.classList.add('loading');
        }
        
        // Disable refresh button
        const refreshBtn = document.querySelector('button[onclick="refreshData()"]');
        if (refreshBtn) {
            refreshBtn.disabled = true;
            refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Refreshing...';
        }
    }
    
    /**
     * Hide loading state
     */
    hideLoadingState() {
        const loadingIndicator = document.getElementById('loading-indicator');
        const stocksTable = document.getElementById('stocks-table');
        
        if (loadingIndicator) {
            loadingIndicator.classList.add('d-none');
        }
        
        if (stocksTable) {
            stocksTable.classList.remove('loading');
        }
        
        // Enable refresh button
        const refreshBtn = document.querySelector('button[onclick="refreshData()"]');
        if (refreshBtn) {
            refreshBtn.disabled = false;
            refreshBtn.innerHTML = '<i class="fas fa-sync-alt me-1"></i>Refresh';
        }
    }
    
    /**
     * Show success message
     */
    showSuccess(message) {
        this.showAlert(message, 'success');
    }
    
    /**
     * Show error message
     */
    showError(message) {
        this.showAlert(message, 'danger');
    }
    
    /**
     * Show alert message
     */
    showAlert(message, type) {
        const alertElement = document.getElementById('status-alert');
        const messageElement = document.getElementById('status-message');
        
        if (alertElement && messageElement) {
            alertElement.className = `alert alert-${type}`;
            alertElement.classList.remove('d-none');
            messageElement.textContent = message;
            
            // Auto-hide after 5 seconds
            setTimeout(() => {
                alertElement.classList.add('d-none');
            }, 5000);
        }
    }
    
    /**
     * Update last update time
     */
    updateLastUpdateTime() {
        const now = new Date();
        const timeString = now.toLocaleTimeString();
        const dateTimeString = now.toLocaleString();
        
        // Update navbar
        const lastUpdateElement = document.getElementById('last-update');
        if (lastUpdateElement) {
            lastUpdateElement.textContent = `Last Updated: ${dateTimeString}`;
        }
        
        // Update info panel
        const lastUpdateTimeElement = document.getElementById('last-update-time');
        if (lastUpdateTimeElement) {
            lastUpdateTimeElement.textContent = timeString;
        }
    }
    
    /**
     * Update market status
     */
    updateMarketStatus() {
        const marketStatusElement = document.getElementById('market-status');
        if (!marketStatusElement) return;
        
        const now = new Date();
        const day = now.getDay(); // 0 = Sunday, 6 = Saturday
        const hour = now.getHours();
        
        // Simple market hours check (NYSE: 9:30 AM - 4:00 PM ET, Mon-Fri)
        const isWeekday = day >= 1 && day <= 5;
        const isMarketHours = hour >= 9 && hour <= 16;
        const isMarketOpen = isWeekday && isMarketHours;
        
        if (isMarketOpen) {
            marketStatusElement.innerHTML = '<i class="fas fa-circle text-success"></i> Open';
            marketStatusElement.className = 'card-title text-success';
        } else {
            marketStatusElement.innerHTML = '<i class="fas fa-circle text-danger"></i> Closed';
            marketStatusElement.className = 'card-title text-danger';
        }
    }
    
    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Handle visibility change (pause when tab is hidden)
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                console.log('Tab hidden, pausing auto-refresh');
                if (this.countdownTimer) clearInterval(this.countdownTimer);
                if (this.autoRefreshTimer) clearInterval(this.autoRefreshTimer);
            } else {
                console.log('Tab visible, resuming auto-refresh');
                this.startCountdown();
                this.setupAutoRefresh();
            }
        });
        
        // Handle online/offline events
        window.addEventListener('online', () => {
            this.showSuccess('Connection restored. Refreshing data...');
            this.refreshData();
        });
        
        window.addEventListener('offline', () => {
            this.showError('Connection lost. Auto-refresh paused.');
            if (this.countdownTimer) clearInterval(this.countdownTimer);
            if (this.autoRefreshTimer) clearInterval(this.autoRefreshTimer);
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (event) => {
            if (event.ctrlKey || event.metaKey) {
                switch (event.key) {
                    case 'r':
                        event.preventDefault();
                        this.refreshData();
                        break;
                }
            }
        });
    }
    
    /**
     * Sort table by column
     */
    sortBy(field) {
        const url = new URL(window.location);
        url.searchParams.set('sort', field);
        window.location.href = url.toString();
    }
}

// Global functions for onclick handlers
function refreshData() {
    if (window.stockTracker) {
        window.stockTracker.refreshData();
    }
}

function autoRefresh() {
    if (window.stockTracker) {
        window.stockTracker.autoRefresh();
    }
}

function startCountdown() {
    if (window.stockTracker) {
        window.stockTracker.startCountdown();
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.stockTracker = new StockTracker();
    console.log('Stock Tracker initialized successfully');
});