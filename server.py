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
            CREATE TABLE IF NOT EXISTS brands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def list_brands():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT id, brand, created_at FROM brands ORDER BY id DESC"
        )
        return [
            {"id": row[0], "brand": row[1], "created_at": row[2]}
            for row in cursor.fetchall()
        ]


def insert_brand(brand):
    created_at = time.strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO brands (brand, created_at) VALUES (?, ?)",
            (brand, created_at),
        )
        conn.commit()


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
        if parsed.path == "/api/brands":
            self._send_json(200, {"items": list_brands()})
            return

        if parsed.path == "/":
            self.send_response(302)
            self.send_header("Location", "/display.html")
            self.end_headers()
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/brands":
            self.send_error(404, "Not Found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid_json"})
            return

        brand = payload.get("brand")
        if not isinstance(brand, str) or not brand.strip():
            self._send_json(400, {"error": "invalid_brand"})
            return

        insert_brand(brand.strip())
        self._send_json(201, {"ok": True, "brand": brand})


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
