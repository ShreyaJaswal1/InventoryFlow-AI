import importlib.util
import tempfile
import unittest
from pathlib import Path


BACKEND_PATH = Path(__file__).with_name("inventory items.py")
SPEC = importlib.util.spec_from_file_location("inventory_backend", BACKEND_PATH)
backend = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backend)


class InventoryManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "inventory-test.sqlite3"
        self.manager = backend.InventoryManager(self.database_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_seed_items_survive_reopen(self):
        self.assertEqual(4, len(self.manager.list_items()))
        reopened = backend.InventoryManager(self.database_path)
        self.assertEqual(self.manager.list_items(), reopened.list_items())

    def test_add_item_persists_price_and_stock_fields(self):
        item = {
            "id": "SKU-2001", "name": "Test cable", "sku": "CBL-2001", "category": "Cables",
            "quantity": 8, "reorderLevel": 10, "warehouse": "North", "supplier": "Cable Co",
            "leadTimeDays": 5, "unitPrice": 3.25,
        }
        saved = self.manager.add_item(item)
        self.assertEqual("Low stock", saved["status"])
        stored = next(row for row in self.manager.list_items() if row["sku"] == "CBL-2001")
        self.assertEqual(3.25, stored["unitPrice"])
        self.assertEqual(8, stored["quantity"])

    def test_negative_stock_is_rejected(self):
        with self.assertRaises(ValueError):
            self.manager.add_item({"id": "bad", "name": "Bad", "sku": "BAD", "quantity": -1})

    def test_analysis_saves_input_and_output(self):
        input_data = {"title": "Steel Coil", "quantity": 2, "reorderLevel": 10, "leadTimeDays": 14}
        output = self.manager.analyze(input_data)
        self.assertEqual("High", output["risk"])
        entry = self.manager.history(1)[0]
        self.assertEqual("analysis", entry["kind"])
        self.assertEqual(input_data, entry["input"])
        self.assertEqual(output, entry["output"])

    def test_model_train_test_returns_holdout_metrics(self):
        report = self.manager.train_test()
        self.assertEqual("Nearest-centroid classifier", report["algorithm"])
        self.assertGreater(report["trainingRows"], 0)
        self.assertGreater(report["testRows"], 0)
        self.assertGreaterEqual(report["accuracy"], 0)
        self.assertLessEqual(report["accuracy"], 1)

    def test_room_bookings_are_persisted(self):
        rooms = self.manager.get_rooms()
        rooms["calendar"]["Boardroom A"].append({"date": "2026-10-22", "time": "10:00", "duration": "30 min", "title": "Saved test"})
        self.manager.save_rooms(rooms)
        reopened = backend.InventoryManager(self.database_path)
        self.assertEqual("Saved test", reopened.get_rooms()["calendar"]["Boardroom A"][-1]["title"])


if __name__ == "__main__":
    unittest.main()