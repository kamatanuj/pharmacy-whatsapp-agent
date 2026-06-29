"""
Pharmacy Action Tools
Functions called by GLM 5.2 via tool calling.
Currently uses mock_data — replace with real API calls when pharmacy system is ready.
"""

import os
import json
import sqlite3
import requests
from tools.mock_data import MOCK_INVENTORY, MOCK_ORDERS, _order_counter

PHARMACY_DB_URL = os.getenv("PHARMACY_DB_URL", "http://localhost:8001")
DB_API_KEY = os.getenv("DB_API_KEY", "mock_key")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID")

# Path to SQLite DB for persistent order storage
_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "orders.db")


def _init_orders_db():
    """Initialize the orders SQLite table."""
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            customer_name TEXT,
            phone_number TEXT,
            items TEXT,
            status TEXT,
            estimated_delivery TEXT,
            delivery_address TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def _save_order_to_db(order: dict):
    """Persist an order to SQLite so it survives restarts."""
    _init_orders_db()
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        """INSERT OR REPLACE INTO orders 
           (order_id, customer_name, phone_number, items, status, estimated_delivery, delivery_address)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            order["order_id"],
            order.get("customer_name", ""),
            order.get("phone_number", ""),
            json.dumps(order.get("items", [])),
            order.get("status", "Pending"),
            order.get("estimated_delivery", "2-3 hours"),
            order.get("delivery_address", ""),
        ),
    )
    conn.commit()
    conn.close()


def _get_order_from_db(order_id: str) -> dict:
    """Look up an order from SQLite. Falls back to MOCK_ORDERS if not found."""
    _init_orders_db()
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    conn.close()
    if row:
        return {
            "order_id": row["order_id"],
            "customer_name": row["customer_name"],
            "phone_number": row["phone_number"],
            "items": json.loads(row["items"]) if row["items"] else [],
            "status": row["status"],
            "estimated_delivery": row["estimated_delivery"],
            "delivery_address": row["delivery_address"],
        }
    return None


def check_medicine_stock(medicine_name: str) -> dict:
    """
    Query pharmacy inventory for stock level, pricing, and prescription requirement.

    Args:
        medicine_name: Name of the medicine to search for

    Returns:
        dict with keys: available (bool), stock (int), price_per_strip (float),
                        requires_prescription (bool), name (str)
    """
    # --- Mock implementation ---
    search = medicine_name.lower().strip()
    for med in MOCK_INVENTORY:
        if search in med["name"].lower() or med["name"].lower() in search:
            return {
                "name": med["name"],
                "available": med["available"],
                "stock": med["stock"],
                "price_per_strip": med["price_per_strip"],
                "requires_prescription": med["requires_prescription"],
                "category": med["category"],
                "manufacturer": med["manufacturer"],
            }

    # No match found
    return {
        "name": medicine_name,
        "available": False,
        "stock": 0,
        "price_per_strip": 0.0,
        "requires_prescription": False,
        "category": "Unknown",
        "manufacturer": "Unknown",
    }
    # --- Real API integration (future) ---
    # try:
    #     resp = requests.get(
    #         f"{PHARMACY_DB_URL}/inventory",
    #         params={"search": medicine_name},
    #         headers={"Authorization": f"Bearer {DB_API_KEY}"},
    #         timeout=10
    #     )
    #     resp.raise_for_status()
    #     return resp.json()
    # except Exception as e:
    #     return {"error": f"Inventory lookup failed: {str(e)}"}


def create_pharmacy_order(
    customer_name: str,
    phone_number: str,
    delivery_address: str,
    items: list,
) -> dict:
    """
    Create a pending order entry in the pharmacy sales system.

    Args:
        customer_name: Customer's full name
        phone_number: Auto-injected from sender's WhatsApp number
        delivery_address: Delivery address for the order
        items: List of {medicine_name, quantity} dicts

    Returns:
        dict with order_id, status, and confirmation message
    """
    global _order_counter

    # --- Mock implementation ---
    order_id = f"RX-{_order_counter}"
    _order_counter += 1

    order = {
        "order_id": order_id,
        "customer_name": customer_name,
        "phone_number": phone_number,
        "items": items,
        "status": "Pending",
        "estimated_delivery": "2-3 hours",
        "delivery_address": delivery_address,
    }
    MOCK_ORDERS[order_id] = order
    _save_order_to_db(order)  # Persist to SQLite

    items_str = ", ".join(
        [f"{i['medicine_name']} x{i['quantity']}" for i in items]
    )
    return {
        "status": "success",
        "order_id": order_id,
        "message": f"Order {order_id} placed for {items_str}. "
        f"Estimated delivery: 2-3 hours.",
    }
    # --- Real API integration (future) ---
    # try:
    #     resp = requests.post(
    #         f"{PHARMACY_DB_URL}/orders",
    #         json={
    #             "customer_name": customer_name,
    #             "phone_number": phone_number,
    #             "delivery_address": delivery_address,
    #             "items": items,
    #         },
    #         headers={"Authorization": f"Bearer {DB_API_KEY}"},
    #         timeout=10
    #     )
    #     resp.raise_for_status()
    #     return resp.json()
    # except Exception as e:
    #     return {"error": f"Order creation failed: {str(e)}"}


def check_order_status(order_id: str) -> dict:
    """
    Retrieve current fulfillment status of an order.

    Args:
        order_id: The order ID (e.g. RX-10001)

    Returns:
        dict with order_id, status, estimated_delivery
    """
    # --- Mock implementation (with DB persistence) ---
    # Check SQLite DB first (survives restarts)
    db_order = _get_order_from_db(order_id)
    if db_order:
        return {
            "order_id": db_order["order_id"],
            "status": db_order["status"],
            "estimated_delivery": db_order["estimated_delivery"],
        }

    # Fall back to in-memory mock data
    order = MOCK_ORDERS.get(order_id)
    if order:
        return {
            "order_id": order["order_id"],
            "status": order["status"],
            "estimated_delivery": order["estimated_delivery"],
        }

    return {
        "order_id": order_id,
        "status": "Not Found",
        "estimated_delivery": "N/A",
    }
    # --- Real API integration (future) ---
    # try:
    #     resp = requests.get(
    #         f"{PHARMACY_DB_URL}/orders/{order_id}",
    #         headers={"Authorization": f"Bearer {DB_API_KEY}"},
    #         timeout=10
    #     )
    #     resp.raise_for_status()
    #     return resp.json()
    # except Exception as e:
    #     return {"error": f"Order status lookup failed: {str(e)}"}


def download_prescription_image(media_id: str) -> dict:
    """
    Download a prescription image sent by customer via WhatsApp Media API.

    Step 1: Get media URL from Meta API
    Step 2: Download binary data from that URL
    Step 3: Save to prescriptions/ directory

    Args:
        media_id: The media ID from the WhatsApp message payload

    Returns:
        dict with success status and local file path
    """
    prescriptions_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "prescriptions"
    )
    os.makedirs(prescriptions_dir, exist_ok=True)

    try:
        # Step 1: Get media URL
        url = f"https://graph.facebook.com/v17.0/{media_id}"
        headers = {"Authorization": f"Bearer {META_ACCESS_TOKEN}"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        media_info = resp.json()
        media_url = media_info.get("url")

        if not media_url:
            return {"success": False, "error": "No media URL returned"}

        # Step 2: Download the actual image
        img_resp = requests.get(media_url, timeout=30)
        img_resp.raise_for_status()

        # Step 3: Save locally
        file_path = os.path.join(prescriptions_dir, f"{media_id}.jpg")
        with open(file_path, "wb") as f:
            f.write(img_resp.content)

        return {
            "success": True,
            "file_path": file_path,
            "message": "Prescription image saved successfully",
        }

    except Exception as e:
        return {"success": False, "error": f"Download failed: {str(e)}"}


# Tool registry — maps tool names to functions
AVAILABLE_TOOLS = {
    "check_medicine_stock": check_medicine_stock,
    "create_pharmacy_order": create_pharmacy_order,
    "check_order_status": check_order_status,
    "download_prescription_image": download_prescription_image,
}