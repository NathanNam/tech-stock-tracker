# Tech Stock Price Tracker

A Flask web application that displays real-time stock prices for major technology companies with a clean, responsive web interface.

![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![Flask](https://img.shields.io/badge/Flask-3.0%2B-green)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **Real-time stock data** for 9 major tech companies
- **Responsive web interface** with Bootstrap styling
- **Auto-refresh** every 60 seconds with live countdown
- **Manual refresh** and sorting options
- **Asynchronous data fetching** for better performance
- **RESTful API endpoints** for programmatic access
- **Comprehensive error handling** and logging
- **Trading volume** display in millions
- **Mobile-friendly** responsive design
- **Real-time price change animations**
- **Market status indicator**

## Tracked Companies

- **Alphabet** (GOOGL)
- **Amazon** (AMZN) 
- **Apple** (AAPL)
- **Meta Platforms** (META)
- **Microsoft** (MSFT)
- **Nvidia** (NVDA)
- **Tesla** (TSLA)
- **Oracle** (ORCL)
- **Broadcom** (AVGO)

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd tech_stock_tracker
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   
   # On Windows
   venv\\Scripts\\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Running the Flask Application

```bash
python app.py
```

Then open your web browser and navigate to: `http://localhost:8080`

### Web Interface Features

- **Dashboard View**: Clean, responsive table showing all stock data
- **Auto-refresh**: Data updates automatically every 60 seconds with live countdown
- **Manual Refresh**: Click the refresh button for instant updates
- **Sorting**: Use dropdown menu to sort by name, price, or change percentage
- **Mobile Responsive**: Works perfectly on desktop, tablet, and mobile devices
- **Real-time Animations**: Visual feedback for price changes

### Example Output

The web interface displays a clean, responsive table with:
- Company names and stock symbols
- Real-time prices with color coding
- Price changes in dollars and percentages
- Trading volume in millions
- Auto-refresh countdown timer
- Statistics cards showing market overview

### API Endpoints

The application provides RESTful API endpoints for programmatic access:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard view |
| `/api/stocks` | GET | Get current stock data (JSON) |
| `/api/refresh` | POST | Manually refresh stock data |
| `/api/status` | GET | Get application status |

#### API Examples

```bash
# Get current stock data
curl http://localhost:8080/api/stocks

# Refresh stock data
curl -X POST http://localhost:8080/api/refresh

# Get application status
curl http://localhost:8080/api/status
```

## Configuration

The application can be configured by editing `config.py`:

```python
class Config:
    # Stock symbols to track
    SYMBOLS = ['GOOGL', 'AMZN', 'AAPL', ...]
    
    # Refresh interval in seconds
    REFRESH_INTERVAL = 60
    
    # Display precision
    PRECISION = 2
    
    # Colors
    POSITIVE_COLOR = "green"
    NEGATIVE_COLOR = "red"
```

## Project Structure

```
tech_stock_tracker/
│
├── app.py               # Flask web application
├── stock_data.py        # Stock data fetching logic
├── config.py            # Configuration settings
├── utils.py             # Utility functions and error handling
├── requirements.txt     # Python dependencies
├── README.md            # This file
├── templates/           # HTML templates
│   ├── base.html        # Base template with navigation
│   ├── index.html       # Main dashboard template
│   └── error.html       # Error page template
├── static/              # Static assets
│   ├── css/
│   │   └── style.css    # Custom CSS styles
│   └── js/
│       └── app.js       # Frontend JavaScript
└── logs/                # Log files (created automatically)
```

## Dependencies

- **Flask** - Web framework for Python
- **yfinance** - For fetching real-time stock data
- **Bootstrap** - CSS framework for responsive design (CDN)
- **Font Awesome** - Icon library (CDN)
- **asyncio** - For asynchronous programming (built-in)

## Error Handling

The application includes comprehensive error handling for:

- Network connectivity issues
- API rate limiting
- Invalid stock symbols
- Data parsing errors
- Display rendering problems

Errors are logged to `logs/stock_tracker.log` for debugging purposes.

## Requirements

- Python 3.8 or higher
- Internet connection for fetching stock data
- Terminal that supports ANSI colors (most modern terminals)

## Limitations

- Stock data depends on yfinance API availability
- Real-time data may have slight delays
- Market hours are not strictly enforced
- Limited to the 9 pre-configured tech stocks

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Future Enhancements

- [ ] Add more stock symbols or custom symbol input
- [ ] Implement historical price charts
- [ ] Add market status indicator
- [ ] Portfolio tracking functionality
- [ ] Export data to CSV
- [ ] Desktop notifications for significant changes
- [ ] WebSocket-based real-time updates
- [ ] Dark/light theme options

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This application is for educational and informational purposes only. Stock prices are fetched from third-party APIs and may not be completely accurate or real-time. Do not use this application for actual trading decisions.

## Troubleshooting

### Common Issues

**"No module named 'yfinance'"**
- Make sure you've installed the requirements: `pip install -r requirements.txt`

**"Error fetching data"**
- Check your internet connection
- The yfinance API might be temporarily unavailable
- Some corporate firewalls block financial data APIs

**"Display looks garbled"**
- Ensure your terminal supports Unicode and ANSI colors
- Try resizing your terminal window
- Use a modern terminal emulator

**Application is slow**
- This is normal on first run as it fetches data for all stocks
- Subsequent refreshes should be faster due to caching

### Getting Help

If you encounter issues:

1. Check the log file in `logs/stock_tracker.log`
2. Ensure all dependencies are installed correctly
3. Verify your internet connection
4. Try running with `python -v main.py` for verbose output

For persistent issues, please open an issue on GitHub with:
- Your Python version
- Operating system
- Error messages from logs
- Steps to reproduce the problem