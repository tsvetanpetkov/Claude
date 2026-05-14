#!/usr/bin/env python3
"""
One-time migration: load 2025 NYC taxi data + other datasets into Railway Postgres.

Run from the repo root with DATABASE_URL set:

    export DATABASE_URL=postgresql://user:pass@host:5432/dbname
    pip install pandas pyarrow requests sqlalchemy psycopg2-binary
    python migrate_to_postgres.py

Get DATABASE_URL from: Railway dashboard → your project → Postgres → Connect tab.
"""
import io
import os
import sqlite3

import pandas as pd
import requests
from sqlalchemy import create_engine

DATABASE_URL = os.environ["DATABASE_URL"]
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

# ── 1. NYC Taxi (full 2025, all available months) ─────────────────────────────
TLC_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{month}.parquet"
MONTHS = [f"2025-{m:02d}" for m in range(1, 13)]

print("[1/3] Migrating NYC taxi data (TLC 2025 monthly parquet → trips)...")
frames = []
for month in MONTHS:
    url = TLC_URL.format(month=month)
    r = requests.get(url, timeout=120)
    if r.status_code == 404:
        print(f"      {month}: not yet published, skipping")
        continue
    r.raise_for_status()
    df_month = pd.read_parquet(io.BytesIO(r.content))
    frames.append(df_month)
    print(f"      {month}: {len(df_month):,} rows downloaded")

taxi_df = pd.concat(frames, ignore_index=True)
print(f"      Writing {len(taxi_df):,} total rows to Postgres...")
taxi_df.to_sql("trips", engine, if_exists="replace", index=False, chunksize=10_000)
print(f"      Done — {len(taxi_df):,} rows written")

# ── 2. Stock prices (SQLite → Postgres) ───────────────────────────────────────
sq = sqlite3.connect("test.db")

print("[2/3] Migrating stock prices   (test.db → stock_prices)...")
stocks_df = pd.read_sql("SELECT * FROM stock_prices", sq)
stocks_df.to_sql("stock_prices", engine, if_exists="replace", index=False)
print(f"      {len(stocks_df):,} rows written")

# ── 3. E-commerce clickstream (SQLite → Postgres) ─────────────────────────────
print("[3/3] Migrating e-commerce data (test.db → ecommerce_clickstream)...")
ecom_df = pd.read_sql("SELECT * FROM ecommerce_clickstream", sq)
ecom_df.to_sql("ecommerce_clickstream", engine, if_exists="replace", index=False)
print(f"      {len(ecom_df):,} rows written")

sq.close()
print("\nDone! All data is now in Postgres.")
