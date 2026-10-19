import gspread
import google.auth
from datetime import date
from functools import lru_cache
from gspread.http_client import BackOffHTTPClient
from gspread.utils import absolute_range_name
from config import Config

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


@lru_cache(maxsize=1)
def get_client() -> gspread.Client:
    # On Cloud Run, ADC uses the runtime service account automatically.
    # Locally, set GOOGLE_APPLICATION_CREDENTIALS to your service_account.json path.
    # BackOffHTTPClient retries 429 quota errors with exponential backoff.
    creds, _ = google.auth.default(scopes=SCOPES)
    return gspread.authorize(creds, http_client=BackOffHTTPClient)


@lru_cache(maxsize=1)
def _get_spreadsheet() -> gspread.Spreadsheet:
    # Opening a spreadsheet costs a read request; do it once per instance
    # since every Cloud Tasks worker shares the same per-user read quota.
    return get_client().open_by_key(Config.SPREADSHEET_ID)


def read_input_rows(user: str) -> list[dict]:
    """
    Read domain/org rows from `user`'s own Input tab.
    Column A: domain URL (required)
    Column B: org name (optional)
    Returns a list of dicts with keys 'domain' and 'org_name'.
    Skips empty rows and the header row.
    """
    sheet = _get_spreadsheet()
    worksheet = sheet.worksheet(Config.input_tab_name(user))
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


def _get_or_create_input_worksheet(sheet, user: str):
    tab_name = Config.input_tab_name(user)
    try:
        return sheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        return sheet.add_worksheet(title=tab_name, rows=1000, cols=10)


def _get_or_create_output_worksheet(sheet, user: str):
    tab_name = Config.output_tab_name(user)
    try:
        return sheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        return sheet.add_worksheet(title=tab_name, rows=1000, cols=20)


def initialize_user(user: str) -> bool:
    """
    Create `user`'s Input and Output tabs if they don't already exist.
    Safe to call more than once. Returns True if either tab was newly
    created, False if both already existed.
    """
    sheet = _get_spreadsheet()

    created = False

    input_worksheet = _get_or_create_input_worksheet(sheet, user)
    if not any(input_worksheet.get_all_values()):
        input_worksheet.append_row(Config.INPUT_COLUMNS)
        created = True

    output_worksheet = _get_or_create_output_worksheet(sheet, user)
    if not any(output_worksheet.get_all_values()):
        output_worksheet.append_row(Config.OUTPUT_COLUMNS)
        created = True

    return created


def _result_to_row(r: dict) -> list:
    return [
        r.get("domain", ""),
        r.get("org_name", ""),
        r.get("ein", ""),
        r.get("revenue", ""),
        r.get("tax_year", ""),
        r.get("form_990_url", ""),
        r.get("ads_running", ""),
        r.get("ad_count", ""),
        r.get("ad_funded_by", ""),
        r.get("funding_type", ""),
        r.get("date_range", ""),
        r.get("date_checked", str(date.today())),
    ]


def write_output_header(user: str) -> None:
    """Write the header row to `user`'s Output tab only if it's empty."""
    sheet = _get_spreadsheet()
    worksheet = _get_or_create_output_worksheet(sheet, user)
    if not any(worksheet.get_all_values()):
        worksheet.append_row(Config.OUTPUT_COLUMNS)


def append_output_row(user: str, result: dict) -> None:
    """
    Append a single result row to `user`'s Output tab. Safe to call concurrently.
    Appends by range name so it makes no read requests (the Output tab is
    created by /run before any tasks are enqueued).
    """
    _get_spreadsheet().values_append(
        absolute_range_name(Config.output_tab_name(user)),
        params={"valueInputOption": "RAW"},
        body={"values": [_result_to_row(result)]},
    )
