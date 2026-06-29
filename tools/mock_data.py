"""
Mock Pharmacy Database
Provides inventory, order, and customer data for development.
Replace with real API calls when pharmacy system is ready.
"""

# Mock inventory — medicine database
MOCK_INVENTORY = [
    {
        "name": "Paracetamol",
        "available": True,
        "stock": 500,
        "price_per_strip": 40.0,
        "requires_prescription": False,
        "category": "OTC",
        "manufacturer": "Cipla",
    },
    {
        "name": "Amoxicillin",
        "available": True,
        "stock": 45,
        "price_per_strip": 120.0,
        "requires_prescription": True,
        "category": "Schedule H",
        "manufacturer": "Sun Pharma",
    },
    {
        "name": "Lipitor",
        "available": False,
        "stock": 0,
        "price_per_strip": 350.0,
        "requires_prescription": True,
        "category": "Schedule H",
        "manufacturer": "Pfizer",
    },
    {
        "name": "Crocin",
        "available": True,
        "stock": 300,
        "price_per_strip": 35.0,
        "requires_prescription": False,
        "category": "OTC",
        "manufacturer": "GSK",
    },
    {
        "name": "Aspirin",
        "available": True,
        "stock": 200,
        "price_per_strip": 25.0,
        "requires_prescription": False,
        "category": "OTC",
        "manufacturer": "USV",
    },
    {
        "name": "Metformin",
        "available": True,
        "stock": 150,
        "price_per_strip": 55.0,
        "requires_prescription": True,
        "category": "Schedule H",
        "manufacturer": "USV",
    },
    {
        "name": "Omeprazole",
        "available": True,
        "stock": 80,
        "price_per_strip": 90.0,
        "requires_prescription": False,
        "category": "OTC",
        "manufacturer": "Dr. Reddy's",
    },
    {
        "name": "Azithromycin",
        "available": True,
        "stock": 60,
        "price_per_strip": 180.0,
        "requires_prescription": True,
        "category": "Schedule H",
        "manufacturer": "Cipla",
    },
    {
        "name": "Vitamin D3",
        "available": True,
        "stock": 400,
        "price_per_strip": 65.0,
        "requires_prescription": False,
        "category": "Supplement",
        "manufacturer": "D-Blue",
    },
    {
        "name": "Cough Syrup",
        "available": True,
        "stock": 120,
        "price_per_strip": 75.0,
        "requires_prescription": False,
        "category": "OTC",
        "manufacturer": "Cipla",
    },
    {
        "name": "Insulin",
        "available": True,
        "stock": 30,
        "price_per_strip": 450.0,
        "requires_prescription": True,
        "category": "Schedule H",
        "manufacturer": "Lupin",
    },
    {
        "name": "Pantoprazole",
        "available": True,
        "stock": 100,
        "price_per_strip": 70.0,
        "requires_prescription": False,
        "category": "OTC",
        "manufacturer": "Sun Pharma",
    },
]

# Mock orders — keyed by order_id
MOCK_ORDERS = {
    "RX-10001": {
        "order_id": "RX-10001",
        "customer_name": "Raj Patel",
        "phone_number": "919820370923",
        "items": [{"medicine_name": "Paracetamol", "quantity": 2}],
        "status": "Out for Delivery",
        "estimated_delivery": "45 minutes",
        "delivery_address": "12 Marine Drive, Mumbai",
    },
    "RX-10002": {
        "order_id": "RX-10002",
        "customer_name": "Priya Sharma",
        "phone_number": "919876543210",
        "items": [{"medicine_name": "Metformin", "quantity": 3}],
        "status": "Confirmed",
        "estimated_delivery": "2 hours",
        "delivery_address": "45 Linking Road, Bandra",
    },
    "RX-10003": {
        "order_id": "RX-10003",
        "customer_name": "Amit Singh",
        "phone_number": "919812345678",
        "items": [{"medicine_name": "Azithromycin", "quantity": 1}],
        "status": "Pending",
        "estimated_delivery": "3 hours",
        "delivery_address": "78 Hill Road, Bandra",
    },
}

# Order counter for generating new order IDs
_order_counter = 10004