"""SQLite-backed inventory API and stock-risk model for InventoryFlow AI."""

from __future__ import annotations

import json
import math
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.environ.get("INVENTORYFLOW_DB", BASE_DIR / "inventoryflow.sqlite3"))
API_PREFIX = "/api"

SEED_ITEMS = [
    {"id": "SKU-1001", "name": "Steel Coil A-18", "sku": "STL-018", "category": "Raw Materials", "quantity": 142, "reorderLevel": 240, "warehouse": "Warehouse North", "supplier": "Atlas Metals Ltd.", "leadTimeDays": 12, "unitPrice": 82.0},
    {"id": "SKU-1002", "name": "Carton Box 12x12", "sku": "PKG-112", "category": "Packaging", "quantity": 368, "reorderLevel": 520, "warehouse": "Dispatch Hub", "supplier": "Boxline Supply", "leadTimeDays": 7, "unitPrice": 2.5},
    {"id": "SKU-1003", "name": "Microcontroller Batch 7", "sku": "ELE-207", "category": "Electronics", "quantity": 210, "reorderLevel": 340, "warehouse": "Central Store", "supplier": "CircuitLink", "leadTimeDays": 16, "unitPrice": 18.75},
    {"id": "SKU-1004", "name": "Printer Cartridges", "sku": "OFF-410", "category": "Office Supplies", "quantity": 860, "reorderLevel": 420, "warehouse": "HQ Annex", "supplier": "OfficeCore", "leadTimeDays": 4, "unitPrice": 45.0},
]

SEED_TICKETS = [
    {"id": "INV1042", "title": "Raw material stock below reorder threshold", "user": "Ariana D.", "department": "Procurement", "category": "Raw Materials", "priority": "Critical", "status": "In Progress", "assigned": "Maya Singh", "created": "2026-09-10 09:15", "updated": "2026-09-10 10:05", "sla": "00:42:17", "location": "Warehouse North", "asset": "Steel Coil A-18", "aiConfidence": 94, "quantity": 142, "reorderLevel": 240, "supplier": "Atlas Metals Ltd.", "leadTime": "12 days", "description": "Inventory is falling below forecasted consumption and supplier lead time has increased."},
    {"id": "INV1043", "title": "Packaging boxes low in dispatch zone", "user": "Noah B.", "department": "Operations", "category": "Packaging", "priority": "Medium", "status": "Assigned", "assigned": "Jason Wu", "created": "2026-09-10 08:20", "updated": "2026-09-10 08:50", "sla": "04:38:12", "location": "Dispatch Hub", "asset": "Carton Box 12x12", "aiConfidence": 88, "quantity": 368, "reorderLevel": 520, "supplier": "Boxline Supply", "leadTime": "7 days", "description": "Stock count indicates fewer than two days of packaging inventory remains."},
    {"id": "INV1044", "title": "Electronics parts replenishment delay", "user": "Leah M.", "department": "Finance", "category": "Electronics", "priority": "High", "status": "Pending", "assigned": "Sana Ali", "created": "2026-09-10 07:05", "updated": "2026-09-10 08:15", "sla": "06:12:08", "location": "Central Store", "asset": "Microcontroller Batch 7", "aiConfidence": 91, "quantity": 210, "reorderLevel": 340, "supplier": "CircuitLink", "leadTime": "16 days", "description": "Supplier lead time for the critical electronics batch has slipped beyond target."},
    {"id": "INV1045", "title": "Office consumables overstock warning", "user": "Rohan P.", "department": "Facilities", "category": "Office Supplies", "priority": "Low", "status": "Resolved", "assigned": "Nina Q.", "created": "2026-09-09 16:20", "updated": "2026-09-09 17:05", "sla": "21:57:10", "location": "HQ Annex", "asset": "Printer Cartridges", "aiConfidence": 85, "quantity": 860, "reorderLevel": 420, "supplier": "OfficeCore", "leadTime": "4 days", "description": "Two-week demand projection suggests a surplus and recommends reallocation to regional sites."},
]

SEED_ROOMS = {
    "rooms": [
        {"name": "Boardroom A", "type": "Executive", "seats": 12, "status": "Available", "time": "09:30 AM", "floor": "2nd Floor", "qrId": "BRD-A-204"},
        {"name": "Client Lounge", "type": "Hybrid", "seats": 8, "status": "Busy", "time": "11:00 AM", "floor": "Lobby", "qrId": "CLG-H-101"},
        {"name": "Focus Pod 3", "type": "Private", "seats": 4, "status": "Available", "time": "03:15 PM", "floor": "3rd Floor", "qrId": "FP3-303"},
        {"name": "Town Hall", "type": "Team", "seats": 20, "status": "Available", "time": "05:00 PM", "floor": "4th Floor", "qrId": "THL-410"},
    ],
    "meetings": {
        "Boardroom A": {"host": "Alicia Stone", "agenda": "Executive inventory review", "attendees": "8 invited", "duration": "45 min", "nextSlot": "09:30 AM", "access": "QR + passcode", "meetingId": "INV-2048"},
        "Client Lounge": {"host": "Liam Foster", "agenda": "Vendor check-in and demo", "attendees": "5 invited", "duration": "30 min", "nextSlot": "11:00 AM", "access": "QR + email invite", "meetingId": "CLT-1180"},
        "Focus Pod 3": {"host": "Maya Patel", "agenda": "One-to-one sync", "attendees": "2 invited", "duration": "20 min", "nextSlot": "03:15 PM", "access": "QR + direct link", "meetingId": "FP3-4401"},
        "Town Hall": {"host": "Operations Team", "agenda": "Weekly business call", "attendees": "18 invited", "duration": "60 min", "nextSlot": "05:00 PM", "access": "QR + room code", "meetingId": "THL-6611"},
    },
    "calendar": {
        "Boardroom A": [{"date": "2026-09-10", "time": "09:30", "duration": "45 min", "title": "Executive inventory review"}, {"date": "2026-09-10", "time": "12:00", "duration": "30 min", "title": "Supplier sync"}],
        "Client Lounge": [{"date": "2026-09-10", "time": "11:00", "duration": "30 min", "title": "Vendor check-in"}],
        "Focus Pod 3": [{"date": "2026-09-10", "time": "15:15", "duration": "20 min", "title": "One-to-one sync"}],
        "Town Hall": [{"date": "2026-09-10", "time": "17:00", "duration": "60 min", "title": "Weekly business call"}],
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class InventoryManager:
    """Persist inventory, tickets, room bookings, and model audit data in SQLite."""

    def __init__(self, database_path: Path | str = DATABASE_PATH) -> None:
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS inventory (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, sku TEXT NOT NULL UNIQUE,
                    category TEXT NOT NULL DEFAULT 'General', quantity INTEGER NOT NULL CHECK(quantity >= 0),
                    reorder_level INTEGER NOT NULL CHECK(reorder_level >= 0), warehouse TEXT NOT NULL DEFAULT '',
                    supplier TEXT NOT NULL DEFAULT '', lead_time_days REAL NOT NULL DEFAULT 7,
                    unit_price REAL NOT NULL DEFAULT 0 CHECK(unit_price >= 0),
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tickets (
                    id TEXT PRIMARY KEY, data_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS rooms (
                    id INTEGER PRIMARY KEY CHECK(id = 1), data_json TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS model_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, data_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS input_output_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
                    input_json TEXT NOT NULL, output_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                """
            )
            if connection.execute("SELECT COUNT(*) FROM inventory").fetchone()[0] == 0:
                for item in SEED_ITEMS:
                    self._upsert_item(connection, item)
            if connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 0:
                for ticket in SEED_TICKETS:
                    connection.execute(
                        "INSERT INTO tickets(id, data_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
                        (ticket["id"], json.dumps(ticket), utc_now(), utc_now()),
                    )
            if connection.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] == 0:
                connection.execute("INSERT INTO rooms(id, data_json, updated_at) VALUES (1, ?, ?)", (json.dumps(SEED_ROOMS), utc_now()))

    @staticmethod
    def _validate_item(item: dict[str, Any]) -> dict[str, Any]:
        normalized = {
            "id": str(item.get("id") or "").strip(),
            "name": str(item.get("name") or "").strip(),
            "sku": str(item.get("sku") or "").strip(),
            "category": str(item.get("category") or "General").strip(),
            "quantity": int(item.get("quantity", 0)),
            "reorderLevel": int(item.get("reorderLevel", 0)),
            "warehouse": str(item.get("warehouse") or "").strip(),
            "supplier": str(item.get("supplier") or "").strip(),
            "leadTimeDays": float(item.get("leadTimeDays", 7)),
            "unitPrice": float(item.get("unitPrice", 0)),
        }
        if not normalized["id"] or not normalized["name"] or not normalized["sku"]:
            raise ValueError("Item id, name, and SKU are required.")
        if normalized["quantity"] < 0 or normalized["reorderLevel"] < 0 or normalized["leadTimeDays"] < 0 or normalized["unitPrice"] < 0:
            raise ValueError("Quantity, reorder level, lead time, and unit price cannot be negative.")
        return normalized

    @staticmethod
    def _upsert_item(connection: sqlite3.Connection, item: dict[str, Any]) -> None:
        normalized = InventoryManager._validate_item(item)
        now = utc_now()
        connection.execute(
                        """INSERT INTO inventory(id, name, sku, category, quantity, reorder_level, warehouse, supplier, lead_time_days, unit_price, created_at, updated_at)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET name=excluded.name, sku=excluded.sku, category=excluded.category,
                 quantity=excluded.quantity, reorder_level=excluded.reorder_level, warehouse=excluded.warehouse,
                                 supplier=excluded.supplier, lead_time_days=excluded.lead_time_days, unit_price=excluded.unit_price, updated_at=excluded.updated_at""",
                        (normalized["id"], normalized["name"], normalized["sku"], normalized["category"], normalized["quantity"], normalized["reorderLevel"], normalized["warehouse"], normalized["supplier"], normalized["leadTimeDays"], normalized["unitPrice"], now, now),
        )

    @staticmethod
    def _item_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "name": row["name"], "sku": row["sku"], "category": row["category"],
            "quantity": row["quantity"], "reorderLevel": row["reorder_level"], "warehouse": row["warehouse"],
            "supplier": row["supplier"], "leadTimeDays": row["lead_time_days"], "unitPrice": row["unit_price"],
            "status": "Low stock" if row["quantity"] <= row["reorder_level"] else "Healthy",
        }

    def list_items(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return [self._item_dict(row) for row in connection.execute("SELECT * FROM inventory ORDER BY name COLLATE NOCASE")]

    def replace_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(items, list):
            raise ValueError("Items must be a list.")
        normalized = [self._validate_item(item) for item in items]
        with self._connect() as connection:
            connection.execute("DELETE FROM inventory")
            for item in normalized:
                self._upsert_item(connection, item)
            self._log(connection, "inventory_save", {"count": len(normalized)}, {"saved": len(normalized)})
        return self.list_items()

    def add_item(self, item: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as connection:
            self._upsert_item(connection, item)
            normalized = self._validate_item(item)
            output = {**normalized, "status": "Low stock" if normalized["quantity"] <= normalized["reorderLevel"] else "Healthy"}
            self._log(connection, "inventory_add", normalized, output)
        return output

    def list_tickets(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT data_json FROM tickets ORDER BY created_at DESC").fetchall()
            return [json.loads(row["data_json"]) for row in rows]

    def replace_tickets(self, tickets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(tickets, list):
            raise ValueError("Tickets must be a list.")
        with self._connect() as connection:
            connection.execute("DELETE FROM tickets")
            for ticket in tickets:
                if not isinstance(ticket, dict) or not ticket.get("id"):
                    raise ValueError("Every ticket must have an id.")
                now = utc_now()
                connection.execute("INSERT INTO tickets(id, data_json, created_at, updated_at) VALUES (?, ?, ?, ?)", (str(ticket["id"]), json.dumps(ticket), now, now))
            self._log(connection, "ticket_save", {"count": len(tickets)}, {"saved": len(tickets)})
        return self.list_tickets()

    def get_rooms(self) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT data_json FROM rooms WHERE id=1").fetchone()
            return json.loads(row["data_json"])

    def save_rooms(self, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data.get("rooms"), list):
            raise ValueError("Room data must include a rooms list.")
        with self._connect() as connection:
            connection.execute("UPDATE rooms SET data_json=?, updated_at=? WHERE id=1", (json.dumps(data), utc_now()))
            self._log(connection, "room_save", data, {"saved": True})
        return data

    @staticmethod
    def _log(connection: sqlite3.Connection, kind: str, input_data: Any, output_data: Any) -> None:
        connection.execute(
            "INSERT INTO input_output_log(kind, input_json, output_json, created_at) VALUES (?, ?, ?, ?)",
            (kind, json.dumps(input_data), json.dumps(output_data), utc_now()),
        )

    def history(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM input_output_log ORDER BY id DESC LIMIT ?", (max(1, min(limit, 500)),)).fetchall()
            return [{"id": row["id"], "kind": row["kind"], "input": json.loads(row["input_json"]), "output": json.loads(row["output_json"]), "createdAt": row["created_at"]} for row in rows]

    def analyze(self, data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("title") or data.get("name") or "").strip()
        if not name:
            raise ValueError("Item or SKU is required.")
        quantity = int(data.get("quantity", 0))
        reorder_level = int(data.get("reorderLevel", 0))
        lead_time = float(data.get("leadTimeDays", 7))
        if min(quantity, reorder_level, lead_time) < 0:
            raise ValueError("Quantity, reorder level, and lead time cannot be negative.")
        risk = "High" if quantity <= reorder_level else "Medium" if quantity <= reorder_level * 1.25 or lead_time >= 14 else "Low"
        output = {
            "item": name,
            "category": str(data.get("category") or "General"),
            "risk": risk,
            "priority": "Critical" if risk == "High" and lead_time >= 10 else "High" if risk == "High" else "Medium" if risk == "Medium" else "Low",
            "confidence": 0.9 if quantity <= reorder_level else 0.72,
            "recommendation": "Reorder now and confirm supplier availability." if risk == "High" else "Review the next replenishment cycle and monitor stock movement." if risk == "Medium" else "Stock is above its reorder point; continue routine monitoring.",
            "model": "stock-threshold-baseline",
            "features": {"quantity": quantity, "reorderLevel": reorder_level, "leadTimeDays": lead_time},
        }
        with self._connect() as connection:
            self._log(connection, "analysis", data, output)
        return output

    def train_test(self) -> dict[str, Any]:
        """Train/evaluate a nearest-centroid classifier from stored inventory rows."""
        items = self.list_items()
        labeled = []
        for item in items:
            reorder_level = float(item["reorderLevel"])
            ratio = float(item["quantity"]) / max(reorder_level, 1.0)
            lead_time = float(item.get("leadTimeDays", 7))
            label = int(item["quantity"] <= item["reorderLevel"])
            labeled.append(([ratio, lead_time / 30.0], label, item["sku"]))
        if len(labeled) < 4 or len({row[1] for row in labeled}) < 2:
            raise ValueError("Add at least four saved inventory items, including both low-stock and healthy examples, before training.")

        by_label: dict[int, list[tuple[list[float], int, str]]] = {0: [], 1: []}
        for row in labeled:
            by_label[row[1]].append(row)
        train: list[tuple[list[float], int, str]] = []
        test: list[tuple[list[float], int, str]] = []
        for label_rows in by_label.values():
            label_rows.sort(key=lambda row: row[2])
            if len(label_rows) > 1:
                test.append(label_rows.pop())
            train.extend(label_rows)
        centroids = {}
        for label in (0, 1):
            rows = [row[0] for row in train if row[1] == label]
            if rows:
                centroids[label] = [sum(row[index] for row in rows) / len(rows) for index in range(2)]
        if len(centroids) < 2 or not test:
            raise ValueError("The saved items do not provide enough examples in both classes to run a meaningful test.")

        predictions = []
        for features, expected, sku in test:
            predicted = min(centroids, key=lambda label: math.dist(features, centroids[label]))
            predictions.append({"sku": sku, "expected": "Low stock" if expected else "Healthy", "predicted": "Low stock" if predicted else "Healthy", "correct": predicted == expected})
        result = {
            "algorithm": "Nearest-centroid classifier",
            "featureDescription": "quantity / reorder level and supplier lead time / 30 days",
            "trainingRows": len(train),
            "testRows": len(test),
            "accuracy": round(sum(row["correct"] for row in predictions) / len(predictions), 4),
            "predictions": predictions,
            "note": "Labels are derived from each saved item's reorder level; evaluation is a small holdout test, not a production guarantee.",
        }
        with self._connect() as connection:
            connection.execute("INSERT INTO model_runs(data_json, created_at) VALUES (?, ?)", (json.dumps(result), utc_now()))
            self._log(connection, "model_train_test", {"inventoryCount": len(labeled)}, result)
        return result


_manager: InventoryManager | None = None


def get_manager() -> InventoryManager:
    global _manager
    if _manager is None:
        _manager = InventoryManager()
    return _manager


class InventoryRequestHandler(BaseHTTPRequestHandler):
    server_version = "InventoryFlow/1.0"

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def _json(self, status: int, data: Any) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _body(self) -> Any:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 2_000_000:
            raise ValueError("Request body is too large.")
        return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path in ("/", "/dashboard.html"):
                page_path = BASE_DIR / "index.html"
                if not page_path.exists():
                    page_path = BASE_DIR / "dashboard.html"
                content = page_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            elif path == f"{API_PREFIX}/health":
                self._json(200, {"ok": True, "database": str(DATABASE_PATH)})
            elif path == f"{API_PREFIX}/items":
                self._json(200, get_manager().list_items())
            elif path == f"{API_PREFIX}/tickets":
                self._json(200, get_manager().list_tickets())
            elif path == f"{API_PREFIX}/rooms":
                self._json(200, get_manager().get_rooms())
            elif path == f"{API_PREFIX}/history":
                self._json(200, get_manager().history())
            else:
                self._json(404, {"error": "Not found"})
        except (OSError, sqlite3.Error) as error:
            self._json(500, {"error": str(error)})

    def do_POST(self) -> None:
        self._handle_write()

    def do_PUT(self) -> None:
        self._handle_write()

    def _handle_write(self) -> None:
        path = urlparse(self.path).path
        try:
            data = self._body()
            if path == f"{API_PREFIX}/items":
                result = get_manager().replace_items(data) if isinstance(data, list) else get_manager().add_item(data)
            elif path == f"{API_PREFIX}/tickets":
                result = get_manager().replace_tickets(data)
            elif path == f"{API_PREFIX}/rooms":
                result = get_manager().save_rooms(data)
            elif path == f"{API_PREFIX}/analyze":
                result = get_manager().analyze(data)
            elif path == f"{API_PREFIX}/model/train-test":
                result = get_manager().train_test()
            else:
                self._json(404, {"error": "Not found"})
                return
            self._json(200, result)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
            self._json(400, {"error": str(error)})
        except sqlite3.IntegrityError as error:
            self._json(409, {"error": f"Inventory constraint failed: {error}"})
        except sqlite3.Error as error:
            self._json(500, {"error": str(error)})

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")


def main() -> None:
    host = os.environ.get("INVENTORYFLOW_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", os.environ.get("INVENTORYFLOW_PORT", "8001")))
    server = ThreadingHTTPServer((host, port), InventoryRequestHandler)
    print(f"InventoryFlow API and dashboard: http://{host}:{port}")
    print(f"SQLite database: {DATABASE_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down InventoryFlow.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()