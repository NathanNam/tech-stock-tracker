# Product Requirements Document: Tech Stock Price Tracker

## Overview
A Python application that displays real-time stock prices for major technology companies with a clean, user-friendly interface.

## Target Stocks
The application will track the following companies:
- **Alphabet** (GOOGL)
- **Amazon** (AMZN)
- **Apple** (AAPL)
- **Meta Platforms** (META)
- **Microsoft** (MSFT)
- **Nvidia** (NVDA)
- **Tesla** (TSLA)
- **Oracle** (ORCL)
- **Broadcom** (AVGO)

## Core Requirements

### Data Features
- Fetch current stock prices from a reliable API (e.g., yfinance)
- Display price, daily change ($ and %), and trading volume
- Show last update timestamp
- Auto-refresh data every 60 seconds (configurable)

### Display Requirements
- Clean tabular format showing all stocks at once
- Color coding: green for positive changes, red for negative
- Sort options: by name, price, or daily change percentage
- Company name alongside ticker symbol

### Technical Specifications
- **Language**: Python 3.8+
- **Libraries**: 
  - `yfinance` for stock data
  - `rich` or `tabulate` for terminal display
  - `click` for CLI interface (optional)
- **Error Handling**: Graceful handling of API failures or network issues
- **Performance**: Asynchronous fetching for faster updates

### User Interface
- Terminal-based application with clear formatting
- Commands:
  - `refresh` - Manual data refresh
  - `sort [field]` - Sort by price/change/name
  - `quit` - Exit application
- Display refresh indicator during data fetching

### Optional Enhancements
- Historical price chart (1-day or 1-week)
- Market status indicator (open/closed)
- Portfolio tracking (track total value of holdings)
- Export data to CSV
- Desktop notifications for significant price changes (>5%)

## Success Criteria
- Application runs without errors on Python 3.8+
- All 9 stocks display with accurate, up-to-date information
- Data refreshes work reliably
- Interface is intuitive and responsive
- Code is well-documented and maintainable

## Running the Application
```bash
# Install dependencies
pip install -r requirements.txt

# Run the Flask app
python app.py

# Access in browser
http://localhost:5000
```

## Example Output
```
Tech Stock Tracker - Last Updated: 2025-09-13 14:30:45
Next auto-refresh in: 24 seconds
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Company          Symbol   Price     Change    % Change  Volume
────────────────────────────────────────────────────────────
Apple            AAPL     $178.45   +2.35     +1.33%    45.2M
Microsoft        MSFT     $425.80   -3.20     -0.75%    22.1M
Nvidia           NVDA     $485.90   +12.45    +2.63%    38.7M
...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[R]efresh  [S]ort  [Q]uit
```

## Implementation Notes
- Start with basic price display functionality
- Add features incrementally
- Ensure proper error handling from the start
- Consider rate limiting to avoid API restrictions