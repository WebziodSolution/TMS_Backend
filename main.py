import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. First, explicitly load the base .env file to pull in APP_ENV=local
base_env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(base_env_path):
    # override=True ensures that if it's already set in the terminal, 
    # the .env file can still set or update it if needed.
    load_dotenv(dotenv_path=base_env_path, override=True)

# 2. Now os.getenv will correctly read "local" from your .env file
app_env = os.getenv("APP_ENV", "env")

# 3. Load the specific overrides (override=True ensures these values overwrite the base ones)
if app_env == "local":
    load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env.local"), override=True)
elif app_env == "prod":
    load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env.prod"), override=True)
else:
    load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env.dev"), override=True)

import logging
import logging.config

# Determine logging path based on environment
default_log_path = os.path.join(BASE_DIR, "logs", "tms.log")
if app_env == "prod":
    log_file_path = os.getenv("LOG_FILE_PATH", "/devwebapp_desk_ematrix/webroot/desk.ematrixinfotech.com/py/logs/tms.log")
elif app_env == "dev":
    log_file_path = os.getenv("LOG_FILE_PATH", "/home/kagadnet/public_html/devdesk.ematrixinfotech.com/py/logs/tms.log")
else:
    log_file_path = os.getenv("LOG_FILE_PATH", default_log_path)

# Ensure the logs directory exists
log_dir = os.path.dirname(log_file_path)
if log_dir:
    os.makedirs(log_dir, exist_ok=True)

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s %(asctime)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": '%(levelprefix)s %(asctime)s - "%(request_line)s" %(status_code)s',
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "file": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "access_console": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "formatter": "file",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": log_file_path,
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "encoding": "utf8",
        },
    },
    "loggers": {
        "uvicorn": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False
        },
        "uvicorn.error": {
            "level": "INFO",
            "handlers": ["console", "file"],
            "propagate": False
        },
        "uvicorn.access": {
            "handlers": ["access_console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "fastapi": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False
        },
        "": {  # Root logger
            "handlers": ["console", "file"],
            "level": "INFO",
        },
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)    

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from routes import router as api_router
from core.response import success_response

app = FastAPI(title="Ticket Management System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    # Extract the first error message to be more user-friendly
    error_msg = exc.errors()[0].get("msg", "Validation error")
    
    # Try to make it slightly more contextual based on field
    if len(errors) > 0 and "loc" in errors[0] and len(errors[0]["loc"]) > 1:
        field_name = errors[0]["loc"][-1]
        if field_name != "body":
            error_msg = f"{field_name.capitalize()}: {error_msg}"
            
    return JSONResponse(
        status_code=400,
        content={"status": 400, "message": error_msg, "result": None}
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": exc.status_code, "message": exc.detail, "result": None}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.info(f"Internal Error: {exc}") # Log it for debugging
    return JSONResponse(
        status_code=500,
        content={"status": 500, "message": "An internal server error occurred", "result": None}
    )

app.include_router(api_router)

@app.get("/test")
def read_root():
    return success_response(None, "TMS API is running.")

# python -m venv .venv
# .\venv\Scripts\activate
# pip install -r requirements.txt
# uvicorn main:app --reload --host 0.0.0.0 --port 5000
# for /d /r "C:\Jay\TMS\backend" %i in (__pycache__) do @if exist "%i" rd /s /q "%i"
# tail -f /devwebapp_desk_ematrix/webroot/desk.ematrixinfotech.com/py/logs/tms.log