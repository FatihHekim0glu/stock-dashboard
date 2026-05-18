"""Fetch SPY daily history and save it as the offline test fixture.

Run from the repo root:

    python scripts/fetch_spy_fixture.py

The output file backs the oracle tests so the suite can run without network.
"""

from pathlib import Path

import yfinance as yf

FIXTURE_PATH = Path("tests/data/SPY_D.csv")
KEEP_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


def main() -> None:
    df = yf.Ticker("SPY").history(period="max", auto_adjust=True)
    df = df.reset_index()
    df.columns = [c.lower() for c in df.columns]
    df = df.rename(columns={"index": "date"})
    df = df[KEEP_COLUMNS]

    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(FIXTURE_PATH, index=False)

    print(f"Saved {len(df)} rows to tests/data/SPY_D.csv")


if __name__ == "__main__":
    main()
