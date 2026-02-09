#!/usr/bin/env python3
import http.server
import json
import os
import sqlite3
import sys
import http.server
import socketserver
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data.db")


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS engine_options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                model TEXT NOT NULL,
                price REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS generator_options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                power TEXT NOT NULL,
                price REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS radiator_options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS control_options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS base_options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS color_options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL
            )
            """
        )
        conn.commit()


def list_simple(table, columns, order_by):
    with sqlite3.connect(DB_PATH) as conn:
        col_sql = ", ".join(columns)
        cursor = conn.execute(
            f"SELECT {col_sql} FROM {table} ORDER BY {order_by}"
        )
        rows = cursor.fetchall()
        items = []
        for row in rows:
            item = {}
            for idx, col in enumerate(columns):
                item[col] = row[idx]
            items.append(item)
        return items


def parse_price(value):
    try:
        price_value = float(value)
    except (TypeError, ValueError):
        return None
    if price_value < 0:
        return None
    return price_value


def parse_items(items, required_fields):
    if items is None:
        return [], None
    if not isinstance(items, list):
        return None, "invalid_items"
    parsed = []
    for item in items:
        if not isinstance(item, dict):
            return None, "invalid_items"
        parsed_item = {}
        for field in required_fields:
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                return None, f"invalid_{field}"
            parsed_item[field] = value.strip()
        price_value = parse_price(item.get("price"))
        if price_value is None:
            return None, "invalid_price"
        parsed_item["price"] = price_value
        parsed.append(parsed_item)
    return parsed, None


def insert_rows(table, columns, rows):
    if not rows:
        return 0
    placeholders = ", ".join(["?"] * len(columns))
    col_sql = ", ".join(columns)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})",
            rows,
        )
        conn.commit()
    return len(rows)


def replace_all_options(payload):
    total_inserted = 0
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM engine_options")
        conn.execute("DELETE FROM generator_options")
        conn.execute("DELETE FROM radiator_options")
        conn.execute("DELETE FROM control_options")
        conn.execute("DELETE FROM base_options")
        conn.execute("DELETE FROM color_options")

        if payload["engine"]:
            conn.executemany(
                "INSERT INTO engine_options (category, model, price) VALUES (?, ?, ?)",
                [(i["category"], i["model"], i["price"]) for i in payload["engine"]],
            )
            total_inserted += len(payload["engine"])
        if payload["generator"]:
            conn.executemany(
                "INSERT INTO generator_options (category, power, price) VALUES (?, ?, ?)",
                [(i["category"], i["power"], i["price"]) for i in payload["generator"]],
            )
            total_inserted += len(payload["generator"])
        if payload["radiator"]:
            conn.executemany(
                "INSERT INTO radiator_options (name, price) VALUES (?, ?)",
                [(i["name"], i["price"]) for i in payload["radiator"]],
            )
            total_inserted += len(payload["radiator"])
        if payload["control"]:
            conn.executemany(
                "INSERT INTO control_options (name, price) VALUES (?, ?)",
                [(i["name"], i["price"]) for i in payload["control"]],
            )
            total_inserted += len(payload["control"])
        if payload["base"]:
            conn.executemany(
                "INSERT INTO base_options (name, price) VALUES (?, ?)",
                [(i["name"], i["price"]) for i in payload["base"]],
            )
            total_inserted += len(payload["base"])
        if payload["color"]:
            conn.executemany(
                "INSERT INTO color_options (name, price) VALUES (?, ?)",
                [(i["name"], i["price"]) for i in payload["color"]],
            )
            total_inserted += len(payload["color"])
        conn.commit()
    return total_inserted


def list_all_options():
    return {
        "engine": list_simple(
            "engine_options", ["id", "category", "model", "price"], "category, model"
        ),
        "generator": list_simple(
            "generator_options", ["id", "category", "power", "price"], "category, power"
        ),
        "radiator": list_simple("radiator_options", ["id", "name", "price"], "name"),
        "control": list_simple("control_options", ["id", "name", "price"], "name"),
        "base": list_simple("base_options", ["id", "name", "price"], "name"),
        "color": list_simple("color_options", ["id", "name", "price"], "name"),
    }


def delete_option(section, item_id):
    table_map = {
        "engine": "engine_options",
        "generator": "generator_options",
        "radiator": "radiator_options",
        "control": "control_options",
        "base": "base_options",
        "color": "color_options",
    }
    table = table_map.get(section)
    if not table:
        return False
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
        conn.commit()
        return cursor.rowcount > 0


class Handler(http.server.SimpleHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""
        try:
            return json.loads(body.decode("utf-8")), None
        except json.JSONDecodeError:
            return None, "invalid_json"

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/options":
            self._send_json(200, list_all_options())
            return

        if parsed.path == "/":
            self.send_response(302)
            self.send_header("Location", "/quote.html")
            self.end_headers()
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/options":
            self.send_error(404, "Not Found")
            return

        payload, err = self._read_json()
        if err:
            self._send_json(400, {"error": err})
            return

        engine_items, err = parse_items(
            payload.get("engine"), ["category", "model"]
        )
        if err:
            self._send_json(400, {"error": f"engine_{err}"})
            return

        generator_items, err = parse_items(
            payload.get("generator"), ["category", "power"]
        )
        if err:
            self._send_json(400, {"error": f"generator_{err}"})
            return

        radiator_items, err = parse_items(payload.get("radiator"), ["name"])
        if err:
            self._send_json(400, {"error": f"radiator_{err}"})
            return

        control_items, err = parse_items(payload.get("control"), ["name"])
        if err:
            self._send_json(400, {"error": f"control_{err}"})
            return

        base_items, err = parse_items(payload.get("base"), ["name"])
        if err:
            self._send_json(400, {"error": f"base_{err}"})
            return

        color_items, err = parse_items(payload.get("color"), ["name"])
        if err:
            self._send_json(400, {"error": f"color_{err}"})
            return

        total_inserted = replace_all_options(
            {
                "engine": engine_items,
                "generator": generator_items,
                "radiator": radiator_items,
                "control": control_items,
                "base": base_items,
                "color": color_items,
            }
        )

        self._send_json(201, {"ok": True, "inserted": total_inserted})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")
        if len(parts) != 3 or parts[0] != "api" or parts[1] != "options":
            self.send_error(404, "Not Found")
            return

        section = parts[2]
        query = parsed.query
        item_id = None
        if query.startswith("id="):
            try:
                item_id = int(query.split("=", 1)[1])
            except ValueError:
                item_id = None

        if item_id is None or item_id <= 0:
            self._send_json(400, {"error": "invalid_id"})
            return

        deleted = delete_option(section, item_id)
        if not deleted:
            self._send_json(404, {"error": "not_found"})
            return
        self._send_json(200, {"ok": True, "deleted": True})

# 定义一个支持多线程的类
class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass

def main():
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Invalid port, using 8000")

    init_db()

    with ThreadingTCPServer(("0.0.0.0", port), Handler) as httpd:
        print(f"多线程服务器已启动: http://服务器IP:{port}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
