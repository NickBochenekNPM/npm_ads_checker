# Ads Transparency Checker

Checks the Google Ads Transparency Center for a list of domains and writes
results to a Google Sheet. Deployed on Google Cloud Run.

---

## Project structure

```
ads_checker/
├── app.py                   # Flask routes
├── config.py                # Date presets, region, and all settings
├── sheets.py                # Google Sheets read/write (gspread)
├── scraper/
│   ├── __init__.py
│   ├── base.py              # Shared Playwright browser setup + URL builder
│   ├── ads_transparency.py  # Ads Transparency Center scraper
│   └── guidestar.py         # Stub — ready to implement later
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## Local development setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Google Sheets API — service account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use your existing one)
3. Enable the **Google Sheets API** and **Google Drive API**
4. Create a **Service Account** under IAM & Admin → Service Accounts
5. Download the JSON key and save it as `service_account.json` in this folder
6. Open your Google Sheet and **share it with the service account email**
   (it looks like `name@project.iam.gserviceaccount.com`) with Editor access

### 3. Configure the spreadsheet

Set your spreadsheet ID in `config.py`:
```python
SPREADSHEET_ID = "your-spreadsheet-id-here"
```
The ID is the long string in your sheet's URL:
`https://docs.google.com/spreadsheets/d/THIS_PART_HERE/edit`

Your Input sheet should have:
- **Column A**: Domain (e.g. `hillel.org`)
- **Column B**: Org name (optional, e.g. `Hillel International`)
- **Row 1**: Header row (e.g. `Domain`, `Org name`) — skipped automatically

### 4. Adjust settings (optional)

In `config.py`:
```python
DATE_PRESET = DatePreset.ALL_TIME   # or LAST_30, LAST_90, etc.
REGION = "US"                        # or "GB", "CA", etc.
```

### 5. Run locally

```bash
python app.py
```

Then visit: `http://localhost:8080/run`

---

## Cloud Run deployment

### 1. Set environment variables in Cloud Run

| Variable | Value |
|---|---|
| `SPREADSHEET_ID` | Your Google Sheet ID |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON (or use Workload Identity) |

### 2. Build and deploy

```bash
# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Build and push container
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/ads-checker

# Deploy to Cloud Run
gcloud run deploy ads-checker \
  --image gcr.io/YOUR_PROJECT_ID/ads-checker \
  --platform managed \
  --region us-central1 \
  --timeout 300 \
  --memory 2Gi \
  --allow-unauthenticated
```

### 3. Trigger a run

Visit the Cloud Run URL + `/run`:
`https://your-service-url.run.app/run`

---

## Output sheet columns

| Column | Description |
|---|---|
| Domain | The domain checked |
| Org name | From input sheet (if provided) |
| Ads running | Yes / No / Error |
| Ad count | Number of ads found |
| Ad funded by | Raw text from disclosure (e.g. "Google Ad Grants") |
| Funding type | Grant / Paid / None / Error |
| Date range | Configured date window (e.g. "All time") |
| Date checked | Date the scrape ran |

**Funding type logic:**
- `Grant` — ads running + "Ad funded by" disclosure present
- `Paid` — ads running + no disclosure (absence is significant)
- `None` — no ads running
- `Error` — scraper could not load the page

---

## Adding GuideStar support later

See `scraper/guidestar.py` — the stub is ready.
Steps are documented at the top of that file.

---

## Notes

- Playwright runs headless Chromium on the server — your coworkers don't need
  anything installed
- A polite delay is added between each domain request to avoid rate limiting
- If Google changes the Transparency Center page layout, update the selectors
  in `scraper/ads_transparency.py`
- Cloud Run scales to zero when not in use — cost is effectively zero for
  light internal usage
