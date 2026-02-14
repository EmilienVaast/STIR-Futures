# STIR Futures Pricing Model

Pricing models for CME Short-Term Interest Rate (STIR) futures:

| Contract | Description |
|----------|-------------|
| **SR3** | Three-Month SOFR futures |
| **SR1** | One-Month SOFR futures |
| **ZQ** | 30-Day Federal Funds futures |

## Features

- **Realized settlements** — Compute 2025 final settlement prices using NY Fed fixings and CME methodology
- **Expected prices** — Project 2026 prices under configurable FOMC policy scenarios
- **Data caching** — Automatic local storage (Parquet) of SOFR/EFFR rates from NY Fed API

## Quick Start

```bash
# Install
pip install -e .

# Run the example notebook
jupyter notebook examples/run_all.ipynb
```

Or fetch data via CLI:
```bash
stir-futures fetch sofr --start 2024-12-01 --end 2026-12-31
stir-futures fetch effr --start 2024-12-01 --end 2026-12-31
```

## Project Structure

```
stir_futures/
├── config.py          # Scenario parameters & official prices
├── calendars.py       # IMM dates, business-day logic
├── scenarios.py       # FOMC policy path builder
├── rounding.py        # CME-style rounding
├── reporting.py       # Table formatting
├── cli.py             # Command-line interface
├── data/
│   ├── nyfed.py       # NY Fed API fetchers
│   └── cache.py       # Parquet read/write
└── pricing/
    ├── sr1.py         # SR1 settlement logic
    ├── sr3.py         # SR3 settlement logic
    └── zq.py          # ZQ settlement logic

examples/
└── run_all.ipynb      # Full workflow demo

data/                  # Auto-generated cache (not committed)
```

## Scenario Assumptions

All assumptions are configurable in `stir_futures/config.py`.

### ZQ (Fed Funds futures)
- Expected EFFR = midpoint of Fed Funds target range
- Policy changes effective the day after FOMC decision
- Settlement = calendar-day average of expected EFFR

### SR1 (1-Month SOFR)
- Base SOFR = EFFR + 3 bps
- Additional +10 bps jump on mid-month (15th) and last business day
- Settlement = calendar-day average of expected SOFR

### SR3 (3-Month SOFR)
- Uses daily SOFR from SR1 assumptions
- CME compounding over the reference quarter
- Late-2026 contracts require extending the path into 2027

## Requirements

- Python 3.9+
- pandas, pyarrow, requests, QuantLib-Python
- jupyter (for notebooks)

## License

MIT
