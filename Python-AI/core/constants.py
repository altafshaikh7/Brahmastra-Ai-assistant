"""
Global constants used across the project.
"""

from pathlib import Path

# -----------------------------------------------------
# Project Information
# -----------------------------------------------------

PROJECT_NAME = "BRAHMASTRA AI"

PROJECT_DESCRIPTION = (
    "Enterprise-grade AI Assistant built with FastAPI."
)

COMPANY = "BRAHMASTRA"

AUTHOR = "BRAHMASTRA TEAM"

# -----------------------------------------------------
# Paths
# -----------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

LOG_DIR = BASE_DIR / "logs"

STORAGE_DIR = BASE_DIR / "storage"

DOCS_DIR = BASE_DIR / "docs"

# -----------------------------------------------------
# API
# -----------------------------------------------------

API_V1 = "/api/v1"

HEALTH_ENDPOINT = "/health"

STATUS_ENDPOINT = "/status"

TOOLS_ENDPOINT = "/tools"

AUTOMATION_ENDPOINT = "/automation"

# -----------------------------------------------------
# Logging
# -----------------------------------------------------

DEFAULT_LOG_LEVEL = "INFO"

LOG_FILE_NAME = "brahmastra.log"

# -----------------------------------------------------
# Security
# -----------------------------------------------------

JWT_ALGORITHM = "HS256"

TOKEN_TYPE = "Bearer"

# -----------------------------------------------------
# Time
# -----------------------------------------------------

SECONDS = 1

MINUTE = 60

HOUR = 3600

DAY = 86400