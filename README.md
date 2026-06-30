# Ads Transparency Checker

Checks the Google Ads Transparency Center for a list of domains and writes
results to a Google Sheet. Deployed on Google Cloud Run.

Project ID: central-search-harmony

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
│   └── propublica.py        # ProPublica → EIN → Open990 revenue lookup
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

### 1. Create the Cloud Tasks queue

```bash
gcloud tasks queues create ads-checker --location=us-central1
```

### 2. Set environment variables in Cloud Run

| Variable | Description |
|---|---|
| `SPREADSHEET_ID` | Your Google Sheet ID |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON (or use Workload Identity) |
| `GCP_PROJECT_ID` | Your GCP project ID |
| `CLOUD_RUN_SERVICE_URL` | Full HTTPS URL of this Cloud Run service (e.g. `https://ads-checker-xyz-uc.a.run.app`) |
| `CLOUD_TASKS_SERVICE_ACCOUNT` | Service account email Cloud Tasks uses to call `/process` (e.g. `ads-checker@project.iam.gserviceaccount.com`) |
| `CLOUD_TASKS_QUEUE` | Queue name (default: `ads-checker`) |
| `CLOUD_TASKS_LOCATION` | Queue region (default: `us-central1`) |

### 3. Initial deploy

The first deploy is two steps because the service URL isn't known until after the
first deployment.

```bash
# Authenticate
gcloud auth login
gcloud config set project central-search-harmony

# Build and push container
gcloud builds submit --tag gcr.io/central-search-harmony/ads-checker

# Deploy (CLOUD_RUN_SERVICE_URL added in the next step)
gcloud run deploy ads-checker \
  --image gcr.io/central-search-harmony/ads-checker \
  --platform managed \
  --region us-central1 \
  --timeout 300 \
  --memory 2Gi \
  --allow-unauthenticated \
  --service-account=sheet-writer@central-search-harmony.iam.gserviceaccount.com \
  --set-env-vars="GCP_PROJECT_ID=central-search-harmony,\
CLOUD_RUN_SERVICE_URL=https://ads-checker-127286750848.us-central1.run.app,\
CLOUD_TASKS_SERVICE_ACCOUNT=sheet-writer@central-search-harmony.iam.gserviceaccount.com,\
SPREADSHEET_ID=1eSozbeuS1vO92IlTNk2ZfQVPvd8-LJNG_HXhyCTjuRY"
```

### 4. Grant Cloud Tasks permission to invoke the service

```bash
gcloud run services add-iam-policy-binding ads-checker \
  --region=us-central1 \
  --member="serviceAccount:sheet-writer@central-search-harmony.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

### 5. Redeploy (future updates)

```bash
gcloud builds submit --tag gcr.io/central-search-harmony/ads-checker && \
gcloud run deploy ads-checker \
  --image gcr.io/central-search-harmony/ads-checker \
  --platform managed \
  --region us-central1 \
  --timeout 300 \
  --memory 2Gi \
  --allow-unauthenticated \
  --service-account=sheet-writer@central-search-harmony.iam.gserviceaccount.com \
  --set-env-vars="GCP_PROJECT_ID=central-search-harmony,\
CLOUD_RUN_SERVICE_URL=https://ads-checker-127286750848.us-central1.run.app,\
CLOUD_TASKS_SERVICE_ACCOUNT=sheet-writer@central-search-harmony.iam.gserviceaccount.com,\
SPREADSHEET_ID=1eSozbeuS1vO92IlTNk2ZfQVPvd8-LJNG_HXhyCTjuRY"
```

### 6. Trigger a run

Visit the Cloud Run URL + `/run`:
`https://your-service-url.run.app/run`

This returns immediately with `{"status": "ok", "enqueued": N}`. Each domain is
processed in the background by Cloud Tasks — results appear in the Output sheet
as tasks complete.

---

## Google Sheet menu

A custom **Ads Checker** menu can be added to the Sheet so anyone can trigger a run without touching the Cloud Run URL.

1. In the Google Sheet, go to **Extensions → Apps Script**
2. Delete any placeholder code and paste in the contents of `scripts/sheet_menu.gs`
3. Click **Save**, then close the tab and reload the Sheet
4. An **Ads Checker** menu will appear in the menu bar with a **Run check** option

Clicking **Run check** calls `/run` and shows a confirmation dialog with the number of domains enqueued.

---

## Output sheet columns

| Column | Description |
|---|---|
| Domain | The domain checked |
| Org name | From input sheet (if provided) |
| Ads running | Yes / No / Error |
| EIN | Employer Identification Number (from ProPublica) |
| Revenue | Total revenue from most recent 990 filing (Open990) |
| Tax year | Fiscal year of the revenue figure |
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

## Notes

- Playwright runs headless Chromium on the server — your coworkers don't need
  anything installed
- A polite delay is added between each domain request to avoid rate limiting
- If Google changes the Transparency Center page layout, update the selectors
  in `scraper/ads_transparency.py`
- Cloud Run scales to zero when not in use — cost is effectively zero for
  light internal usage
