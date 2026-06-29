"""
Tool Schema Definitions
OpenAI/GLM-compatible function schema for tool calling.
"""

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "check_medicine_stock",
            "description": "Checks price, availability, and prescription necessity of a medicine.",
            "parameters": {
                "type": "object",
                "properties": {
                    "medicine_name": {
                        "type": "string",
                        "description": "Name of the medicine to check",
                    }
                },
                "required": ["medicine_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_pharmacy_order",
            "description": "Places a pending delivery order for items in stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "Customer's full name",
                    },
                    "delivery_address": {
                        "type": "string",
                        "description": "Delivery address for the order",
                    },
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "medicine_name": {
                                    "type": "string",
                                    "description": "Name of the medicine",
                                },
                                "quantity": {
                                    "type": "integer",
                                    "description": "Number of strips/units",
                                },
                            },
                            "required": ["medicine_name", "quantity"],
                        },
                        "description": "List of medicines and quantities to order",
                    },
                },
                "required": ["customer_name", "delivery_address", "items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_order_status",
            "description": "Retrieves the current fulfillment status of a pharmacy order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID (e.g. RX-10001)",
                    }
                },
                "required": ["order_id"],
            },
        },
    },
]