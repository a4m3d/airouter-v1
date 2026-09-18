import base64
import os
import sys

# Make the backend package importable and set safe test secrets before imports.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "ai_router_test")
os.environ["ENCRYPTION_MASTER_KEY"] = base64.b64encode(b"0" * 32).decode()
os.environ["ADMIN_JWT_SECRET"] = "test-jwt-secret"
os.environ["ADMIN_DASHBOARD_TOKEN"] = "test-admin-token"
