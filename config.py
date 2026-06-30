import os
from enum import Enum


class DatePreset(Enum):
    ALL_TIME = ""
    LAST_7 = "Last+7+days"
    LAST_30 = "Last+30+days"
    LAST_90 = "Last+90+days"
    LAST_365 = "Last+365+days"


class Config:
    # --- Date range ---
    # Change this to adjust the date window for all scrapes
    DATE_PRESET = DatePreset.ALL_TIME

    # --- Region ---
    REGION = "US"  # e.g. "GB", "CA", "AU"

    # --- Scraper behavior ---
    PLAYWRIGHT_HEADLESS = True
    REQUEST_DELAY_SECONDS = 2       # polite pause between domains
    MAX_CONCURRENT_PAGES = 3        # parallel Playwright contexts

    # --- Google Sheets ---
    # Set via environment variable or hardcode for local dev
    SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1eSozbeuS1vO92IlTNk2ZfQVPvd8-LJNG_HXhyCTjuRY")
    INPUT_TAB_NAME = "Input"
    OUTPUT_TAB_NAME = "Output"

    # --- Google Service Account ---
    # Path to your service account JSON file (local dev)
    # In Cloud Run, set GOOGLE_APPLICATION_CREDENTIALS env var instead
    SERVICE_ACCOUNT_FILE = os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS", "service_account.json"
    )

    # --- Cloud Tasks ---
    GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
    CLOUD_TASKS_LOCATION = os.environ.get("CLOUD_TASKS_LOCATION", "us-central1")
    CLOUD_TASKS_QUEUE = os.environ.get("CLOUD_TASKS_QUEUE", "ads-checker")
    # Full HTTPS URL of this Cloud Run service, e.g. https://ads-checker-xyz-uc.a.run.app
    CLOUD_RUN_SERVICE_URL = os.environ.get("CLOUD_RUN_SERVICE_URL", "")
    # Service account email that Cloud Tasks uses to sign OIDC tokens for /process
    CLOUD_TASKS_SERVICE_ACCOUNT = os.environ.get("CLOUD_TASKS_SERVICE_ACCOUNT", "")

    # --- Output column order ---
    OUTPUT_COLUMNS = [
        "Domain",
        "Org name",
        "EIN",
        "Revenue",
        "Tax year",
        "Form 990",
        "Ads running",
        "Ad count",
        "Ad funded by",
        "Funding type",
        "Date range",
        "Date checked",
    ]
