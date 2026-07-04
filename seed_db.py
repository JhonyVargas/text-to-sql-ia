"""Crea y siembra data/ventas.db con datos sinteticos de una tienda de tecnologia.

Ejecutar una sola vez (o cuando se quiera regenerar la base de datos):
    python seed_db.py
"""
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "ventas.db"

PRODUCTS = [
    ("Laptop", "Laptops", 899.0),
    ("Mouse", "Accessories", 19.0),
    ("Keyboard", "Accessories", 39.0),
    ("Monitor", "Monitors", 219.0),
    ("Headphones", "Audio", 59.0),
    ("Smartphone", "Phones", 599.0),
    ("Tablet", "Tablets", 349.0),
    ("Webcam", "Accessories", 45.0),
    ("Speaker", "Audio", 79.0),
    ("Smartwatch", "Wearables", 199.0),
]

CITIES = ["Madrid", "Barcelona", "Valencia", "Sevilla", "Bilbao"]

CUSTOMERS = [
    "Ana Garcia", "Luis Torres", "Marta Diaz", "Carlos Ruiz", "Sofia Lopez",
    "Diego Fernandez", "Elena Morales", "Pablo Gomez", "Laura Sanchez", "Javier Romero",
]

TABLE_NAME = "ventas"


def build_rows(n: int = 120):
    start = date(2025, 1, 1)
    rows = []
    for i in range(1, n + 1):
        product, category, base_price = random.choice(PRODUCTS)
        quantity = random.randint(1, 5)
        price = round(base_price * random.uniform(0.9, 1.1), 2)
        city = random.choice(CITIES)
        customer = random.choice(CUSTOMERS)
        sale_date = (start + timedelta(days=random.randint(0, 500))).isoformat()
        rows.append((i, product, category, price, quantity, city, customer, sale_date))
    return rows


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        f"""
        CREATE TABLE {TABLE_NAME} (
            id INTEGER PRIMARY KEY,
            product TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            city TEXT NOT NULL,
            customer TEXT NOT NULL,
            sale_date TEXT NOT NULL
        )
        """
    )
    conn.executemany(
        f"INSERT INTO {TABLE_NAME} VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        build_rows(),
    )
    conn.commit()
    conn.close()
    print(f"Base de datos creada en {DB_PATH}")


if __name__ == "__main__":
    main()
