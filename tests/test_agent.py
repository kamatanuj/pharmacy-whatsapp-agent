"""
Test Suite — Pharmacy WhatsApp AI Agent
10 test cases from the development plan.
Run: python -m pytest tests/test_agent.py -v
"""

import os
import sys
import json
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tools.pharmacy_tools import (
    check_medicine_stock,
    create_pharmacy_order,
    check_order_status,
    AVAILABLE_TOOLS,
)
from app.memory import init_db, get_chat_history, save_to_history, clear_session_memory
from tools.schema import TOOLS_SCHEMA


class TestCheckMedicineStock:
    """Tests for check_medicine_stock tool"""

    def test_1_paracetamol_in_stock(self):
        """Test 1: Paracetamol — should be available, no Rx"""
        result = check_medicine_stock("paracetamol")
        assert result["available"] is True
        assert result["stock"] == 500
        assert result["price_per_strip"] == 40.0
        assert result["requires_prescription"] is False

    def test_6_amoxicillin_rx_required(self):
        """Test 6: Amoxicillin — should require prescription"""
        result = check_medicine_stock("amoxicillin")
        assert result["available"] is True
        assert result["requires_prescription"] is True

    def test_7_lipitor_out_of_stock(self):
        """Test 7: Lipitor — should be out of stock"""
        result = check_medicine_stock("lipitor")
        assert result["available"] is False
        assert result["stock"] == 0

    def test_unknown_medicine(self):
        """Test: Unknown medicine — should return not available"""
        result = check_medicine_stock("xyzabc123")
        assert result["available"] is False


class TestCreatePharmacyOrder:
    """Tests for create_pharmacy_order tool"""

    def test_2_create_order(self):
        """Test 2: Create order for paracetamol"""
        result = create_pharmacy_order(
            customer_name="Test Customer",
            phone_number="919820370923",
            delivery_address="123 Test Street, Mumbai",
            items=[{"medicine_name": "Paracetamol", "quantity": 2}],
        )
        assert result["status"] == "success"
        assert "RX-" in result["order_id"]
        assert "Paracetamol x2" in result["message"]


class TestCheckOrderStatus:
    """Tests for check_order_status tool"""

    def test_3_existing_order(self):
        """Test 3: Check status of existing order RX-10001"""
        result = check_order_status("RX-10001")
        assert result["order_id"] == "RX-10001"
        assert result["status"] == "Out for Delivery"
        assert "45" in result["estimated_delivery"]

    def test_nonexistent_order(self):
        """Test: Check status of non-existent order"""
        result = check_order_status("RX-99999")
        assert result["status"] == "Not Found"


class TestMemory:
    """Tests for SQLite memory management"""

    def test_5_restart_clears_memory(self):
        """Test 5: Restart command clears session"""
        init_db()
        test_phone = "919999999999"
        save_to_history(test_phone, "user", "Hello")
        save_to_history(test_phone, "assistant", "Hi there!")
        history = get_chat_history(test_phone)
        assert len(history) == 2

        clear_session_memory(test_phone)
        history = get_chat_history(test_phone)
        assert len(history) == 0

    def test_history_limit(self):
        """Test: History returns only last 15 messages"""
        init_db()
        test_phone = "918888888888"
        for i in range(20):
            save_to_history(test_phone, "user", f"Message {i}")
            save_to_history(test_phone, "assistant", f"Reply {i}")

        history = get_chat_history(test_phone, limit=15)
        assert len(history) <= 15


class TestToolSchema:
    """Tests for tool schema format"""

    def test_schema_has_required_tools(self):
        """Test: Schema includes all 3 tools"""
        names = [t["function"]["name"] for t in TOOLS_SCHEMA]
        assert "check_medicine_stock" in names
        assert "create_pharmacy_order" in names
        assert "check_order_status" in names

    def test_phone_number_not_in_schema(self):
        """Test: phone_number is NOT in create_order schema (auto-injected)"""
        order_tool = next(
            t for t in TOOLS_SCHEMA if t["function"]["name"] == "create_pharmacy_order"
        )
        props = order_tool["function"]["parameters"]["properties"]
        assert "phone_number" not in props


class TestToolRegistry:
    """Tests for available tools registry"""

    def test_all_tools_registered(self):
        """Test: All tools are in AVAILABLE_TOOLS"""
        assert "check_medicine_stock" in AVAILABLE_TOOLS
        assert "create_pharmacy_order" in AVAILABLE_TOOLS
        assert "check_order_status" in AVAILABLE_TOOLS
        assert "download_prescription_image" in AVAILABLE_TOOLS