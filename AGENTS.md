# AGENTS.md - Trading List Project Guidelines

## Project Overview

This is a Python-based stock screening system for Chinese A-shares (上证A股), using technical indicators to filter bullish stocks and score trend strength.

**Project Structure:**
- `trading_list.py` - CLI stock screener
- `list_gui.py` - GUI version (tkinter)
- `tech/` - Technical indicator modules
- `data/` - Data fetching and database modules
- `utils/` - Utility modules (logger)
- `shareholding.txt` - Portfolio holdings

## Commands

### Setup
```bash
pip install -r requirements.txt
```

### Run Application
```bash
# GUI (recommended)
python list_gui.py

# CLI - default (skip data update)
python trading_list.py

# CLI - with data update
python trading_list.py --update

# CLI - with specific date
python trading_list.py -d 2025-03-07

# CLI - full parameters
python trading_list.py -d 2025-03-07 -b 10.0 --update
```

### Database Operations
```bash
# Initialize database (clears existing data)
python -c "from data.init_db import init_db; init_db()"

# Extract data from Sina Finance
python -c "from data.extract_data import main; main()"
```

### Testing
**No test framework is configured.** This project does not have unit tests.
To test individual modules, import and call functions directly in Python interpreter.

### Data Management
```bash
# Check database content
sqlite3 data/stock_data.db ".tables"
sqlite3 data/stock_data.db "SELECT * FROM stock_prices LIMIT 10"
```

## Code Style Guidelines

### General
- Python 3.8+ compatible
- UTF-8 encoding: `# -*- coding: utf-8 -*-` at file start
- Docstrings for all modules, classes, and functions
- Comments in Chinese for Chinese financial domain

### Imports
- Standard library imports first
- Third-party imports second (pandas, numpy, pandas_ta)
- Local module imports last
- Use `sys.path.insert(0, ...)` for cross-module imports

Example:
```python
import pandas as pd
import pandas_ta as ta
from typing import Optional, List
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from data.read_data import get_stock_price_before_date
from utils.logger import get_logger
```

### Naming Conventions
- **Functions**: `snake_case` (e.g., `calculate_supertrend`, `filter_bullish_stocks`)
- **Variables**: `snake_case` (e.g., `stock_code`, `trend_direction`)
- **Constants**: `UPPER_CASE` (e.g., `DB_PATH`, `REQUEST_DELAY`)
- **Classes**: `PascalCase` (e.g., `StockFilterGUI`, `RealAdjustFactorFetcher`)
- **Private methods**: `_leading_underscore` (e.g., `_init_session`)

### Type Hints
- Use type hints for function parameters and return values
- Use `Optional[X]` for nullable values
- Use `List[X]` for list types
- Use `pd.DataFrame` and `pd.Series` for pandas types

Example:
```python
def get_stock_supertrend(stock_code: str, end_date: str, days: int = 50) -> Optional[pd.DataFrame]:
    ...
```

### Error Handling
- Use `try/except` for external API calls and file operations
- Log warnings for recoverable errors using `logger.warning()`
- Return `None` or empty DataFrame on failure
- Check DataFrame emptiness before processing

Example:
```python
try:
    result = some_api_call()
except Exception as e:
    logger.warning(f"API call failed: {e}")
    return None

if df.empty or len(df) < required_length:
    return pd.DataFrame()
```

### Logging
- Use module-level logger: `logger = get_logger(__name__)`
- Log levels: `info` for progress, `warning` for issues, `error` for failures
- Include context in log messages (stock code, values)

### DataFrame Operations
- Always make copies: `df = df.copy()`
- Check DataFrame validity before calculations
- Return empty DataFrame on insufficient data
- Use pandas-ta for technical indicators

### File Organization
- One technical indicator per file in `tech/` directory
- Each module should be self-contained with proper imports
- Database operations in `data/` directory
- Shared utilities in `utils/` directory

### Configuration
- No external config files - use module-level constants
- Database path: `data/stock_data.db`
- Portfolio file: `shareholding.txt` (root directory)
- Log output: `logs/` directory

### GUI Guidelines (tkinter)
- Use classes for organizing GUI components
- Use `StoppableThread` for background tasks
- Update UI using `root.after()` for thread safety
- Handle window close events properly

### Comments
- Module docstrings explain functionality and usage
- Function docstrings include Args, Returns, and description
- Inline comments for complex logic
- Comments in Chinese for business logic

## Dependencies

Core dependencies:
- `pandas` - Data manipulation
- `numpy` - Numerical operations
- `pandas-ta` - Technical analysis indicators
- `akshare` - Chinese stock data API
- `python-dotenv` - Environment variables

## Important Notes

1. **Data Source**: Uses Sina Finance API for Chinese stock data
2. **Database**: SQLite with 5 years of historical data
3. **Rate Limiting**: 0.3s delay between API requests
4. **Stock Universe**: Shanghai A-shares (60xxxx codes)
5. **No Unit Tests**: Project relies on manual testing
