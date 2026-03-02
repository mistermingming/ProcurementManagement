#!/usr/bin/env python3
import http.server
import json
import os
import sqlite3
import sys
import socketserver
from urllib.parse import parse_qs, urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data.db")


TABLE_CONFIG = {
    "frequency": {
        "columns": ["id", "value"],
        "write_columns": ["value"],
        "order_by": "value",
        "readonly": True,
    },
    "phase": {
        "columns": ["id", "value"],
        "write_columns": ["value"],
        "order_by": "value",
    },
    "voltage": {
        "columns": ["id", "frequency", "voltage"],
        "write_columns": ["frequency", "voltage"],
        "order_by": "frequency, voltage",
    },
    "engine": {
        "columns": ["id", "frequency", "brand", "model", "price"],
        "write_columns": ["frequency", "brand", "model", "price"],
        "order_by": "frequency, brand, model",
    },
    "generator": {
        "columns": ["id", "frequency", "brand", "model", "price"],
        "write_columns": ["frequency", "brand", "model", "price"],
        "order_by": "frequency, brand, model",
    },
    "generator_tank": {
        "columns": ["generator_id", "tank_value", "price"],
        "write_columns": ["generator_id", "tank_value", "price"],
        "order_by": "generator_id, tank_value",
    },
    "control_system": {
        "columns": ["id", "name", "price"],
        "write_columns": ["name", "price"],
        "order_by": "name",
    },
    "switch": {
        "columns": ["id", "name", "price"],
        "write_columns": ["name", "price"],
        "order_by": "name",
    },
    "base": {
        "columns": ["id", "name", "price"],
        "write_columns": ["name", "price"],
        "order_by": "name",
    },
    "battery": {
        "columns": ["id", "name", "price"],
        "write_columns": ["name", "price"],
        "order_by": "name",
    },
    "silencer": {
        "columns": ["id", "name", "price"],
        "write_columns": ["name", "price"],
        "order_by": "name",
    },
    "elbow": {
        "columns": ["id", "name", "price"],
        "write_columns": ["name", "price"],
        "order_by": "name",
    },
}


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS frequency (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                value TEXT NOT NULL UNIQUE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS phase (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                value TEXT NOT NULL UNIQUE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS voltage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                frequency TEXT NOT NULL,
                voltage TEXT NOT NULL,
                FOREIGN KEY (frequency) REFERENCES frequency(value)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS engine (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                frequency TEXT NOT NULL,
                brand TEXT NOT NULL,
                model TEXT NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY (frequency) REFERENCES frequency(value)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS generator (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                frequency TEXT NOT NULL,
                brand TEXT NOT NULL,
                model TEXT NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY (frequency) REFERENCES frequency(value)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS generator_tank (
                generator_id INTEGER NOT NULL,
                tank_value TEXT NOT NULL,
                price REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (generator_id, tank_value),
                FOREIGN KEY (generator_id) REFERENCES generator(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS control_system (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                price REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS switch (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                price REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS base (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                price REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS battery (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                price REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS silencer (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                price REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS elbow (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                price REAL NOT NULL
            )
            """
        )
        conn.executemany(
            "INSERT OR IGNORE INTO frequency (value) VALUES (?)",
            [("50hz",), ("60hz",)],
        )
        conn.commit()


def list_table_rows(table):
    config = TABLE_CONFIG.get(table)
    if not config:
        return None
    columns = config["columns"]
    order_by = config["order_by"]
    col_sql = ", ".join(columns)
    with get_conn() as conn:
        cursor = conn.execute(
            f"SELECT {col_sql} FROM {table} ORDER BY {order_by}"
        )
        rows = cursor.fetchall()
    items = []
    for row in rows:
        item = {}
        for col in columns:
            item[col] = row[col]
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


def validate_frequency(conn, value):
    if not isinstance(value, str) or not value.strip():
        return False
    cursor = conn.execute(
        "SELECT 1 FROM frequency WHERE value = ? LIMIT 1", (value.strip(),)
    )
    return cursor.fetchone() is not None


def validate_generator_id(conn, value):
    try:
        generator_id = int(value)
    except (TypeError, ValueError):
        return None
    if generator_id <= 0:
        return None
    cursor = conn.execute(
        "SELECT 1 FROM generator WHERE id = ? LIMIT 1", (generator_id,)
    )
    if cursor.fetchone() is None:
        return None
    return generator_id


def parse_row(conn, table, row):
    if not isinstance(row, dict):
        return None, "invalid_row"
    config = TABLE_CONFIG[table]
    parsed = {}
    for column in config["write_columns"]:
        value = row.get(column)
        if column == "price":
            price_value = parse_price(value)
            if price_value is None:
                return None, "invalid_price"
            parsed[column] = price_value
            continue
        if column == "frequency":
            if not validate_frequency(conn, value):
                return None, "invalid_frequency"
            parsed[column] = value.strip()
            continue
        if column == "generator_id":
            generator_id = validate_generator_id(conn, value)
            if generator_id is None:
                return None, "invalid_generator_id"
            parsed[column] = generator_id
            continue
        if not isinstance(value, str) or not value.strip():
            return None, f"invalid_{column}"
        parsed[column] = value.strip()
    return parsed, None


def replace_table_rows(table, rows):
    config = TABLE_CONFIG[table]
    if config.get("readonly"):
        return None, "readonly"
    if rows is None:
        return None, "invalid_rows"
    if not isinstance(rows, list):
        return None, "invalid_rows"
    with get_conn() as conn:
        parsed_rows = []
        for row in rows:
            parsed, err = parse_row(conn, table, row)
            if err:
                return None, err
            parsed_rows.append(parsed)

        try:
            conn.execute(f"DELETE FROM {table}")
            if parsed_rows:
                columns = config["write_columns"]
                col_sql = ", ".join(columns)
                placeholders = ", ".join(["?"] * len(columns))
                conn.executemany(
                    f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})",
                    [tuple(row[col] for col in columns) for row in parsed_rows],
                )
            conn.commit()
        except sqlite3.IntegrityError:
            return None, "integrity_error"
    return len(parsed_rows), None


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
        if parsed.path == "/api/meta":
            with get_conn() as conn:
                freq_rows = conn.execute(
                    "SELECT value FROM frequency ORDER BY value"
                ).fetchall()
                generator_rows = conn.execute(
                    "SELECT id, frequency, brand, model FROM generator ORDER BY id"
                ).fetchall()
            self._send_json(
                200,
                {
                    "frequency": [row["value"] for row in freq_rows],
                    "generators": [
                        {
                            "id": row["id"],
                            "frequency": row["frequency"],
                            "brand": row["brand"],
                            "model": row["model"],
                        }
                        for row in generator_rows
                    ],
                },
            )
            return

        if parsed.path == "/api/table":
            params = parse_qs(parsed.query)
            table = params.get("name", [None])[0]
            if table not in TABLE_CONFIG:
                self._send_json(404, {"error": "table_not_found"})
                return
            rows = list_table_rows(table)
            self._send_json(200, {"rows": rows})
            return

        if parsed.path == "/":
            self.send_response(302)
            self.send_header("Location", "/admin.html")
            self.end_headers()
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/table":
            self.send_error(404, "Not Found")
            return

        params = parse_qs(parsed.query)
        table = params.get("name", [None])[0]
        if table not in TABLE_CONFIG:
            self._send_json(404, {"error": "table_not_found"})
            return

        payload, err = self._read_json()
        if err:
            self._send_json(400, {"error": err})
            return

        rows = payload.get("rows")
        inserted, err = replace_table_rows(table, rows)
        if err:
            self._send_json(400, {"error": err})
            return
        self._send_json(200, {"ok": True, "inserted": inserted})

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
