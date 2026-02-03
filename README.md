Venkat – STIR Pricing Model (SR3 / SR1 / ZQ)

Python implementation of basic pricing models for CME STIR futures:
- **SR3 (Three-Month SOFR futures)**
- **SR1 (One-Month SOFR futures)**
- **ZQ (30-Day Federal Funds futures)**

The model computes:
1) **Realized (historical) final settlement prices for 2025 expiries** using NY Fed fixings and CME-style settlement logic  
2) **Expected ZQ prices for 2026** under a rule-based FOMC policy path  
3) **Expected SR1 prices for 2026** using a rule-based SOFR path relative to Fed Funds  
4) **Expected SR3 prices for 2026** using the expected policy path + expected SOFR rules (requires extending the path into early 2027)

---

# Repo structure:
#   notebooks/
#     run_all.ipynb            # main entry notebook (imports from src/)
#   src/
#     nyfed_api.py             # NY Fed Markets API fetchers (SOFR/EFFR)
#     dates_calendars.py       # IMM dates, business-day logic, calendars
#     rounding.py              # CME-style rounding helpers
#     zq.py                    # ZQ settlement + expected tables
#     sr1.py                   # SR1 settlement + expected tables
#     sr3.py                   # SR3 settlement + expected tables
#     scenarios.py             # policy path builders (FOMC cut schedule)
#     reporting.py             # dashed-table printer utilities
#     constants.py             # month codes, shared constants


---

## Installation

**Python**: 3.9+ recommended

```bash
pip install -r requirements.txt

How to Run

Open and run:

notebooks/run_all.ipynb → “Run All”

This prints:

realized 2025 tables for SR3 / SR1 / ZQ (with optional comparison to Barchart values)

expected 2026 tables for ZQ, SR1, SR3 under scenario assumptions

Key Assumptions (Scenario Objectives)
Objective 2 (ZQ expected, 2026)

Expected EFFR = midpoint of Fed Funds target range

FOMC policy changes modeled as step changes effective the day after meeting decision day

Monthly expected settlement uses calendar-day arithmetic average of expected daily EFFR

Objective 3 (SR1 expected, 2026)

Base SOFR = EFFR + 3 bps

SOFR has an additional +10 bps jump on:

the 15th of the month (or next Monday if weekend: 16th/17th)

the last business day of the month

Monthly settlement uses calendar-day arithmetic average of expected daily SOFR

Objective 4 (SR3 expected, 2026)

Uses expected daily SOFR from Objective 3

Uses SR3 compounding method over the SR3 reference quarter

Requires extending expected paths into early 2027 because late-2026 contracts settle into 2027