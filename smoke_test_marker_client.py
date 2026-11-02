import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from marker_client import MarkerClient


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = {
            "tasks": [
                {
                    "id": "m-123",
                    "title": "Tarea demo",
                    "description": "Descripción de prueba",
                    "status": "open",
                    "url": "https://marker.io/task/m-123",
                    "project": {"id": "proj-1", "name": "Proyecto Demo"},
                }
            ]
        }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


server = HTTPServer(("127.0.0.1", 8765), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    client = MarkerClient("http://127.0.0.1:8765", None, None, "testkey", None, "api_key")
    print(client.get_tasks())
finally:
    server.shutdown()
    server.server_close()
