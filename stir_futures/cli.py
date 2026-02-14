from __future__ import annotations

import argparse

from stir_futures.data.cache import get_effr, get_sofr


def _add_date_range(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start", dest="start_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", dest="end_date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--refresh", action="store_true", help="Force refresh from NY Fed API")


def main() -> None:
    parser = argparse.ArgumentParser(description="STIR Futures utilities")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="Fetch and cache NY Fed rates")
    fetch.add_argument("rate", choices=["sofr", "effr"], help="Rate to fetch")
    _add_date_range(fetch)

    args = parser.parse_args()

    if args.command == "fetch":
        if args.rate == "sofr":
            df = get_sofr(args.start_date, args.end_date, refresh=args.refresh)
        else:
            df = get_effr(args.start_date, args.end_date, refresh=args.refresh)
        print(f"Fetched {len(df)} rows for {args.rate.upper()}.")


if __name__ == "__main__":
    main()
