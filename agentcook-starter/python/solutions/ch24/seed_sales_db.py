"""Create data/sales.db with 30 days of demo orders ending today.

python -m solutions.ch24.seed_sales_db [path]
"""

import random
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

from app.config import settings

PRODUCTS = [
    ("蓝牙耳机Pro", "耳机", 299.0),
    ("开放式运动耳机", "耳机", 459.0),
    ("iPhone 16", "手机", 4999.0),
    ("快充充电器65W", "配件", 129.0),
    ("磨砂手机壳", "配件", 39.0),
]


def seed(path: str | Path, days: int = 30, seed: int = 42) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            DROP TABLE IF EXISTS order_items;
            DROP TABLE IF EXISTS orders;
            CREATE TABLE orders (id INTEGER PRIMARY KEY, date TEXT NOT NULL, category TEXT NOT NULL, amount REAL NOT NULL);
            CREATE TABLE order_items (
                id INTEGER PRIMARY KEY,
                order_id INTEGER NOT NULL REFERENCES orders(id),
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL
            );
            CREATE INDEX idx_orders_date ON orders(date);
            """
        )
        today = date.today()
        for offset in range(days):
            day = (today - timedelta(days=offset)).isoformat()
            for _ in range(rng.randint(3, 8)):
                name, category, price = rng.choice(PRODUCTS)
                qty = rng.randint(1, 3)
                order_id = conn.execute(
                    "INSERT INTO orders (date, category, amount) VALUES (?, ?, ?)", (day, category, price * qty)
                ).lastrowid
                conn.execute(
                    "INSERT INTO order_items (order_id, product_name, quantity) VALUES (?, ?, ?)", (order_id, name, qty)
                )
        conn.commit()
    finally:
        conn.close()
    return path


if __name__ == "__main__":
    target = seed(sys.argv[1] if len(sys.argv) > 1 else settings.sales_db_path)
    print(f"wrote {target}")
