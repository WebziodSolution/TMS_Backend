import os
import sys

# Ensure the backend directory is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from a2wsgi import ASGIMiddleware
from main import app

# Wrap the FastAPI ASGI app as a WSGI application
application = ASGIMiddleware(app)
