import gspread
from datetime import date
from google.oauth2.service_account import Credentials
from config import Config

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


def get_client() -> gspread.Client:
    creds = Credentials.from_service_account_file(
        Config.SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return gspread.authorize(creds)


def read_input_rows() -> list[dict]:
    """
    Read domain/org rows from the Input tab.
    Column A: domain URL (required)
    Column B: org name (optional)
    Returns a list of dicts with keys 'domain' and 'org_name'.
    Skips empty rows and the header row.
    """
    client = get_client()
    sheet = client.open_by_key(Config.SPREADSHEET_ID)
    worksheet = sheet.worksheet(Config.INPUT_TAB_NAME)
    rows = worksheet.get_all_values()

    results = []
    for i, row in enumerate(rows):
        if i == 0:
            continue  # skip header
        domain = row[0].strip() if len(row) > 0 else ""
        org_name = row[1].strip() if len(row) > 1 else ""
        if domain:
            results.append({"domain": domain, "org_name": org_name})

    return results


def write_output_rows(results: list[dict]) -> None:
    """
    Write scrape results to the Output tab.
    Clears existing content, writes a fresh header, then all result rows.
    """
    client = get_client()
    sheet = client.open_by_key(Config.SPREADSHEET_ID)

    # Get or create the Output tab
    try:
        worksheet = sheet.worksheet(Config.OUTPUT_TAB_NAME)
    except gspread.WorksheetNotFound:
        worksheet = sheet.add_worksheet(
            title=Config.OUTPUT_TAB_NAME, rows=1000, cols=20
        )

    worksheet.clear()

    # Write header
    header = Config.OUTPUT_COLUMNS
    all_rows = [header]

    # Write data rows
    for r in results:
        row = [
            r.get("domain", ""),
            r.get("org_name", ""),
            r.get("ads_running", ""),
            r.get("ad_count", ""),
            r.get("ad_funded_by", ""),
            r.get("funding_type", ""),
            r.get("date_range", ""),
            r.get("date_checked", str(date.today())),
        ]
        all_rows.append(row)

    worksheet.update(all_rows, "A1")
