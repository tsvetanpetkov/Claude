#!/usr/bin/env python3
"""
One-time migration: load data_explorer files into Railway Postgres.

Run from the data_explorer repo root with DATABASE_URL set:

    export DATABASE_URL=postgresql://user:pass@host:5432/dbname
    python migrate_to_postgres.py

Get DATABASE_URL from: Railway dashboard → your project → Postgres → Connect tab.
"""
import os
import sqlite3
import duckdb
import pandas as pd
from sqlalchemy import create_engine

DATABASE_URL = os.environ["DATABASE_URL"]
# SQLAlchemy requires postgresql://, Railway supplies postgres://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

print("[1/3] Migrating NYC taxi data  (taxi_sample.parquet → trips)...")
taxi_df = duckdb.execute("SELECT * FROM read_parquet('taxi_sample.parquet')").df()
taxi_df.to_sql("trips", engine, if_exists="replace", index=False, chunksize=10_000)
print(f"      {len(taxi_df):,} rows written")

sq = sqlite3.connect("test.db")

print("[2/3] Migrating stock prices   (test.db → stock_prices)...")
stocks_df = pd.read_sql("SELECT * FROM stock_prices", sq)
stocks_df.to_sql("stock_prices", engine, if_exists="replace", index=False)
print(f"      {len(stocks_df):,} rows written")

print("[3/3] Migrating e-commerce data (test.db → ecommerce_clickstream)...")
ecom_df = pd.read_sql("SELECT * FROM ecommerce_clickstream", sq)
ecom_df.to_sql("ecommerce_clickstream", engine, if_exists="replace", index=False)
print(f"      {len(ecom_df):,} rows written")

sq.close()
print("\nDone! All data is now in Postgres.")
