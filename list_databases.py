#!/usr/bin/env python3
"""List databases - finds and displays SQLite database files."""

import os
import sys
import glob
import sqlite3


def find_sqlite_databases(search_path="."):
    """Find all SQLite database files in the given path."""
    databases = []
    patterns = ["*.db", "*.sqlite", "*.sqlite3"]
    for pattern in patterns:
        matches = glob.glob(os.path.join(search_path, "**", pattern), recursive=True)
        databases.extend(matches)
    return sorted(set(databases))


def get_database_info(db_path):
    """Get basic info about a SQLite database."""
    info = {
        "path": db_path,
        "size_bytes": os.path.getsize(db_path),
        "tables": [],
    }
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        info["tables"] = [row[0] for row in cursor.fetchall()]
        conn.close()
    except sqlite3.Error as e:
        info["error"] = str(e)
    return info


def list_databases(search_path="."):
    """List all databases found in the search path."""
    databases = find_sqlite_databases(search_path)

    if not databases:
        print(f"No databases found in '{search_path}'")
        return []

    print(f"Found {len(databases)} database(s) in '{search_path}':\n")
    results = []
    for db_path in databases:
        info = get_database_info(db_path)
        size_kb = info["size_bytes"] / 1024
        print(f"  {db_path}")
        print(f"    Size:   {size_kb:.1f} KB")
        if "error" in info:
            print(f"    Error:  {info['error']}")
        else:
            table_list = ", ".join(info["tables"]) if info["tables"] else "(no tables)"
            print(f"    Tables: {table_list}")
        print()
        results.append(info)
    return results


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    list_databases(path)
