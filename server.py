#!/usr/bin/env python3
import http.server
import socketserver
import json
import os
import sqlite3
import sys
import time
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data.db")


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                engine_category TEXT NOT NULL,
                engine_model TEXT NOT NULL,
                radiator_type TEXT NOT NULL,
                generator_category TEXT NOT NULL,
                generator_power TEXT NOT NULL,
                control_system TEXT NOT NULL,
                base_type TEXT NOT NULL,
                unit_color TEXT NOT NULL,
                price_engine_combo REAL NOT NULL,
                price_generator_combo REAL NOT NULL,
                price_radiator REAL NOT NULL,
                price_control REAL NOT NULL,
                price_base REAL NOT NULL,
                price_color REAL NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quote_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quote_id INTEGER NOT NULL,
                section TEXT NOT NULL,
                name TEXT NOT NULL,
                extra TEXT,
                price REAL NOT NULL,
                FOREIGN KEY (quote_id) REFERENCES quotes(id)
            )
            """
        )
        conn.commit()


def list_quotes():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            SELECT id,
                   engine_category,
                   engine_model,
                   radiator_type,
                   generator_category,
                   generator_power,
                   control_system,
                   base_type,
                   unit_color,
                   created_at
            FROM quotes
            ORDER BY id DESC
            """
        )
        return [
            {
                "id": row[0],
                "engine_category": row[1],
                "engine_model": row[2],
                "radiator_type": row[3],
                "generator_category": row[4],
                "generator_power": row[5],
                "control_system": row[6],
                "base_type": row[7],
                "unit_color": row[8],
                "created_at": row[9],
            }
            for row in cursor.fetchall()
        ]


def insert_quote(payload):
    created_at = time.strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO quotes (
                engine_category,
                engine_model,
                radiator_type,
                generator_category,
                generator_power,
                control_system,
                base_type,
                unit_color,
                price_engine_combo,
                price_generator_combo,
                price_radiator,
                price_control,
                price_base,
                price_color,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["engine_category"],
                payload["engine_model"],
                payload["radiator_type"],
                payload["generator_category"],
                payload["generator_power"],
                payload["control_system"],
                payload["base_type"],
                payload["unit_color"],
                payload["price_engine_combo"],
                payload["price_generator_combo"],
                payload["price_radiator"],
                payload["price_control"],
                payload["price_base"],
                payload["price_color"],
                created_at,
            ),
        )
        quote_id = cursor.lastrowid
        items = payload.get("items", [])
        if items:
            conn.executemany(
                """
                INSERT INTO quote_items (quote_id, section, name, extra, price)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        quote_id,
                        item["section"],
                        item["name"],
                        item.get("extra"),
                        item["price"],
                    )
                    for item in items
                ],
            )
        conn.commit()


def list_options():
    with sqlite3.connect(DB_PATH) as conn:
        def distinct(column):
            return [
                row[0]
                for row in conn.execute(
                    f"SELECT DISTINCT {column} FROM quotes WHERE {column} IS NOT NULL AND {column} != ''"
                )
            ]

        return {
            "engine_category": distinct("engine_category"),
            "engine_model": distinct("engine_model"),
            "radiator_type": distinct("radiator_type"),
            "generator_category": distinct("generator_category"),
            "generator_power": distinct("generator_power"),
            "control_system": distinct("control_system"),
            "base_type": distinct("base_type"),
            "unit_color": distinct("unit_color"),
        }


class Handler(http.server.SimpleHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/quotes":
            self._send_json(200, {"items": list_quotes()})
            return

        if parsed.path == "/api/options":
            self._send_json(200, list_options())
            return

        if parsed.path == "/":
            self.send_response(302)
            self.send_header("Location", "/display.html")
            self.end_headers()
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/quotes":
            self.send_error(404, "Not Found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid_json"})
            return

        if "engine_items" in payload:
            def parse_items(items, name_key, extra_key=None):
                if not isinstance(items, list) or not items:
                    return None, "invalid_items"
                parsed = []
                for item in items:
                    if not isinstance(item, dict):
                        return None, "invalid_items"
                    name = item.get(name_key)
                    extra = item.get(extra_key) if extra_key else None
                    price = item.get("price")
                    if not isinstance(name, str) or not name.strip():
                        return None, "invalid_items"
                    if extra_key:
                        if not isinstance(extra, str) or not extra.strip():
                            return None, "invalid_items"
                        extra = extra.strip()
                    try:
                        price_value = float(price)
                    except (TypeError, ValueError):
                        return None, "invalid_items"
                    if price_value < 0:
                        return None, "invalid_items"
                    parsed.append(
                        {
                            "name": name.strip(),
                            "extra": extra,
                            "price": price_value,
                        }
                    )
                return parsed, None

            engine_items, err = parse_items(
                payload.get("engine_items"), "engine_category", "engine_model"
            )
            if err:
                self._send_json(400, {"error": "invalid_engine_items"})
                return

            generator_items, err = parse_items(
                payload.get("generator_items"), "generator_category", "generator_power"
            )
            if err:
                self._send_json(400, {"error": "invalid_generator_items"})
                return

            radiator_items, err = parse_items(
                payload.get("radiator_items"), "radiator_type"
            )
            if err:
                self._send_json(400, {"error": "invalid_radiator_items"})
                return

            control_items, err = parse_items(
                payload.get("control_items"), "control_system"
            )
            if err:
                self._send_json(400, {"error": "invalid_control_items"})
                return

            base_items, err = parse_items(payload.get("base_items"), "base_type")
            if err:
                self._send_json(400, {"error": "invalid_base_items"})
                return

            color_items, err = parse_items(payload.get("color_items"), "unit_color")
            if err:
                self._send_json(400, {"error": "invalid_color_items"})
                return

            items = []
            for item in engine_items:
                items.append(
                    {
                        "section": "engine",
                        "name": item["name"],
                        "extra": item["extra"],
                        "price": item["price"],
                    }
                )
            for item in generator_items:
                items.append(
                    {
                        "section": "generator",
                        "name": item["name"],
                        "extra": item["extra"],
                        "price": item["price"],
                    }
                )
            for item in radiator_items:
                items.append(
                    {
                        "section": "radiator",
                        "name": item["name"],
                        "extra": None,
                        "price": item["price"],
                    }
                )
            for item in control_items:
                items.append(
                    {
                        "section": "control",
                        "name": item["name"],
                        "extra": None,
                        "price": item["price"],
                    }
                )
            for item in base_items:
                items.append(
                    {
                        "section": "base",
                        "name": item["name"],
                        "extra": None,
                        "price": item["price"],
                    }
                )
            for item in color_items:
                items.append(
                    {
                        "section": "color",
                        "name": item["name"],
                        "extra": None,
                        "price": item["price"],
                    }
                )

            first_engine = engine_items[0]
            first_generator = generator_items[0]
            first_radiator = radiator_items[0]
            first_control = control_items[0]
            first_base = base_items[0]
            first_color = color_items[0]

            data = {
                "engine_category": first_engine["name"],
                "engine_model": first_engine["extra"],
                "radiator_type": first_radiator["name"],
                "generator_category": first_generator["name"],
                "generator_power": first_generator["extra"],
                "control_system": first_control["name"],
                "base_type": first_base["name"],
                "unit_color": first_color["name"],
                "price_engine_combo": first_engine["price"],
                "price_generator_combo": first_generator["price"],
                "price_radiator": first_radiator["price"],
                "price_control": first_control["price"],
                "price_base": first_base["price"],
                "price_color": first_color["price"],
                "items": items,
            }
            insert_quote(data)
            self._send_json(201, {"ok": True})
            return

        required_fields = [
            "engine_category",
            "engine_model",
            "radiator_type",
            "generator_category",
            "generator_power",
            "control_system",
            "base_type",
            "unit_color",
        ]
        price_fields = [
            "price_engine_combo",
            "price_generator_combo",
            "price_radiator",
            "price_control",
            "price_base",
            "price_color",
        ]

        data = {}
        for field in required_fields:
            value = payload.get(field)
            if not isinstance(value, str) or not value.strip():
                self._send_json(400, {"error": f"invalid_{field}"})
                return
            data[field] = value.strip()

        for field in price_fields:
            value = payload.get(field)
            try:
                price_value = float(value)
            except (TypeError, ValueError):
                self._send_json(400, {"error": f"invalid_{field}"})
                return
            if price_value < 0:
                self._send_json(400, {"error": f"invalid_{field}"})
                return
            data[field] = price_value

        insert_quote(data)
        self._send_json(201, {"ok": True})


def main():
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Invalid port, using 8000")

    init_db()

    with socketserver.TCPServer(("0.0.0.0", port), Handler) as httpd:
        print(f"Serving on http://0.0.0.0:{port}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
