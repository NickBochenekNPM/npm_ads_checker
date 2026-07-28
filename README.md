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

Each person who uses the tool works out of their own tab pair in the shared
spreadsheet: **`<name> - Ads Checker Input`** and **`<name> - Ads Checker
Output`** (e.g. `Kristen - Ads Checker Input`, `Kristen - Ads Checker Output`
— the naming is set in `config.py` via `Config.input_tab_name()` /
`Config.output_tab_name()`). This keeps everyone's domains and results in
separate workspaces without any risk of one person's run reading or
overwriting another's data.

To onboard a new person, call `/init?user=<name>` once (or use the **Set up
new workspace** menu item — see below) — this creates both
`<name> - Ads Checker Input` and `<name> - Ads Checker Output`, with header
rows already in place, ready for domains to be added to Column A (and
optionally an org name in Column B). It's safe to call more than once; it
does nothing if the tabs already exist.

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

Then visit: `http://localhost:8080/run?user=Kristen` (substitute the name whose
`<name> - Ads Checker Input` tab you want to process)

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

### 6. Onboard a person, then trigger a run

First, set up their workspace (one time only):
`https://your-service-url.run.app/init?user=Kristen`

This creates `Kristen - Ads Checker Input` and `Kristen - Ads Checker Output`
if they don't already exist, and is safe to call again later — it's a no-op
if both tabs are already there.

Then, whenever they want to trigger a run, visit `/run` with the same `user`:
`https://your-service-url.run.app/run?user=Kristen`

This returns immediately with `{"status": "ok", "enqueued": N}`, where N is the
count of domains in `Kristen - Ads Checker Input`. Each domain is processed in
the background by Cloud Tasks — results appear in `Kristen - Ads Checker
Output` as tasks complete.

---

## Google Sheet menu

A custom menu can be added to the Sheet so anyone can trigger a run without touching the Cloud Run URL.

1. In the Google Sheet, go to **Extensions → Apps Script**
2. Add `scripts/sheet_menu.gs` as a file in the project — it defines
   `runAdsCheck` and `initWorkspace`, but deliberately does **not** define
   `onOpen()`
3. Make sure exactly one file in the project defines `onOpen()` and wires up
   menu items for these functions (Apps Script shares one global scope per
   project, so a second `onOpen()` would silently overwrite the first and its
   menu would never appear). If this is the only tool on the sheet, that can
   be as simple as:
   ```js
   function onOpen() {
     SpreadsheetApp.getUi()
       .createMenu('Ads Checker')
       .addItem('Run check', 'runAdsCheck')
       .addItem('Set up new workspace', 'initWorkspace')
       .addToUi();
   }
   ```
   If the sheet already has other tools with their own menu items, add these
   two items into that existing `onOpen()` instead.
4. Click **Save**, then close the tab and reload the Sheet

**Set up new workspace** prompts for a name and calls `/init?user=<name>`,
creating that person's tab pair if it doesn't exist yet — do this once per
new person before they use **Run check** for the first time.

**Run check** doesn't ask who you are — it looks at whichever tab is
currently active (`SpreadsheetApp.getActiveSheet()`) and derives the
workspace name from it, e.g. selecting the `Kristen - Ads Checker Input` tab
and clicking **Run check** runs `/run?user=Kristen`. This means the person
running it never has to type or remember anything, and it can never run
against the wrong workspace by accident — it always matches whatever tab
you're looking at. If the active tab isn't one of the Ads Checker tabs, it
tells you to select the right one first instead of guessing.

---

## Output sheet columns

Each of these appears once per person, in their own `<name> - Ads Checker
Output` tab.

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
