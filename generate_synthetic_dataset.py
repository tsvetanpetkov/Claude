"""
Generate a synthetic customer orders dataset and save it as a Parquet file.

Schema:
    order_id        - unique UUID
    customer_id     - unique UUID per customer
    customer_name   - full name
    customer_email  - email address
    customer_country- country of the customer
    order_date      - date the order was placed (last 3 years)
    product_name    - product purchased
    product_category- category of the product
    quantity        - number of units ordered
    unit_price      - price per unit (USD)
    total_price     - quantity * unit_price
    status          - order status (pending/shipped/delivered/cancelled)
    payment_method  - payment method used
"""

import random
import uuid
from datetime import datetime, timedelta

import pandas as pd
from faker import Faker

fake = Faker()
random.seed(42)
Faker.seed(42)

# --- Configuration ---
NUM_CUSTOMERS = 500
NUM_ORDERS = 5_000
OUTPUT_FILE = "customer_orders.parquet"

PRODUCTS = [
    ("Wireless Headphones", "Electronics"),
    ("Bluetooth Speaker", "Electronics"),
    ("USB-C Hub", "Electronics"),
    ("Mechanical Keyboard", "Electronics"),
    ("Laptop Stand", "Electronics"),
    ("Running Shoes", "Apparel"),
    ("Winter Jacket", "Apparel"),
    ("Yoga Mat", "Sports"),
    ("Dumbbell Set", "Sports"),
    ("Coffee Maker", "Home & Kitchen"),
    ("Air Fryer", "Home & Kitchen"),
    ("Blender", "Home & Kitchen"),
    ("Novel: The Last Light", "Books"),
    ("Python Programming Guide", "Books"),
    ("Vitamin C Supplement", "Health"),
    ("Protein Powder", "Health"),
    ("Desk Lamp", "Office"),
    ("Ergonomic Chair", "Office"),
    ("Gaming Mouse", "Electronics"),
    ("Smart Watch", "Electronics"),
]

STATUSES = ["pending", "shipped", "delivered", "delivered", "delivered", "cancelled"]
PAYMENT_METHODS = ["credit_card", "debit_card", "paypal", "bank_transfer", "crypto"]

START_DATE = datetime.now() - timedelta(days=3 * 365)


def random_date(start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def build_customers(n: int) -> list[dict]:
    customers = []
    for _ in range(n):
        customers.append(
            {
                "customer_id": str(uuid.uuid4()),
                "customer_name": fake.name(),
                "customer_email": fake.unique.email(),
                "customer_country": fake.country(),
            }
        )
    return customers


def build_orders(customers: list[dict], n: int) -> list[dict]:
    orders = []
    for _ in range(n):
        customer = random.choice(customers)
        product_name, product_category = random.choice(PRODUCTS)
        quantity = random.randint(1, 10)
        unit_price = round(random.uniform(5.0, 500.0), 2)
        order_date = random_date(START_DATE, datetime.now())

        orders.append(
            {
                "order_id": str(uuid.uuid4()),
                "customer_id": customer["customer_id"],
                "customer_name": customer["customer_name"],
                "customer_email": customer["customer_email"],
                "customer_country": customer["customer_country"],
                "order_date": order_date.date(),
                "product_name": product_name,
                "product_category": product_category,
                "quantity": quantity,
                "unit_price": unit_price,
                "total_price": round(quantity * unit_price, 2),
                "status": random.choice(STATUSES),
                "payment_method": random.choice(PAYMENT_METHODS),
            }
        )
    return orders


def main():
    print(f"Generating {NUM_CUSTOMERS} customers and {NUM_ORDERS} orders...")
    customers = build_customers(NUM_CUSTOMERS)
    orders = build_orders(customers, NUM_ORDERS)

    df = pd.DataFrame(orders)
    df["order_date"] = pd.to_datetime(df["order_date"])
    df.sort_values("order_date", inplace=True)
    df.reset_index(drop=True, inplace=True)

    df.to_parquet(OUTPUT_FILE, index=False)
    print(f"Saved {len(df)} rows to '{OUTPUT_FILE}'")
    print(f"\nSchema:\n{df.dtypes.to_string()}")
    print(f"\nSample:\n{df.head(3).to_string()}")


if __name__ == "__main__":
    main()
