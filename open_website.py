#!/usr/bin/env python3
"""Opens donotask.streamlit.app once every 12 hours."""

import webbrowser
import time

URL = "https://donotask.streamlit.app"
INTERVAL_HOURS = 12
INTERVAL_SECONDS = INTERVAL_HOURS * 3600

if __name__ == "__main__":
    print(f"Scheduled website opener: {URL}")
    print(f"Opening every {INTERVAL_HOURS} hours. Press Ctrl+C to stop.\n")

    while True:
        print(f"Opening {URL}...")
        webbrowser.open(URL)
        print(f"Next open in {INTERVAL_HOURS} hours. Sleeping...")
        time.sleep(INTERVAL_SECONDS)
