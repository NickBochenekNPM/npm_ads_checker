# Ads Checker

Checks whether a nonprofit is running Google Ads, and whether those ads look
like **Google Ad Grants** or **paid** advertising, by looking each domain up
in the [Google Ads Transparency Center](https://adstransparency.google.com/).
It also looks up the organization's EIN and latest reported revenue on
[ProPublica Nonprofit Explorer](https://projects.propublica.org/nonprofits/).

You give it a list of domains in the Google Sheet; it writes one row of results
per domain back to the Sheet.

- **Runs on:** Google Cloud Run, service `ads-checker` in project
  `central-search-harmony` (us-central1)
- **Spreadsheet:** [`1eSozbeuS1vO92IlTNk2ZfQVPvd8-LJNG_HXhyCTjuRY`](https://docs.google.com/spreadsheets/d/1eSozbeuS1vO92IlTNk2ZfQVPvd8-LJNG_HXhyCTjuRY/edit)
  — the same workbook as the [Website Analyzer](https://github.com/NickBochenekNPM/websiteAnalyzer)
- **Read this in Google Docs:** [Ads Checker — README](https://docs.google.com/document/d/1PZNOhckXx9VuvouGtJ1Z6ETOcKmwMYPqOtZ1eE5pC9k/edit),
  or **Sheet Tools → Help: Ads Checker** in the Sheet. It's updated
  automatically from this file (see [README sync](#readme-sync)).

---

## Using it

### Your workspace

Everyone works in their own pair of tabs, so one person's run never touches
another's data:

| Tab | What it's for |
|---|---|
| `<your name> - Ads Checker Input` | The domains you want checked |
| `<your name> - Ads Checker Output` | Results, one row per domain |

If you don't have these tabs yet, create them once with **Set up new workspace**
in the Sheet's menu: it asks for your name and creates both tabs with their
header rows. Running it again for a name that already has tabs does nothing.

### Running a check

1. On your **Input** tab, put one domain per row in **column A**, starting on
   row 2. `example.org`, `www.example.org` and `https://example.org/about` all
   work; only the domain is used.
2. Optionally, put the organization's name in **column B**. It makes the
   ProPublica lookup more accurate (see [Things to keep in mind](#things-to-keep-in-mind)).
3. With your Input **or** Output tab selected, choose **Run Ads Check** from
   the Sheet's menu. It works out whose workspace to run from the tab you're
   looking at, so make sure it's yours. On any other tab it asks you to select
   one first.
4. A pop-up confirms how many domains were queued. Results arrive in your
   Output tab one row at a time over the next few minutes, not all at once,
   and not necessarily in input order.

Every run checks **every** domain on your Input tab and **adds** new rows to
the Output tab; it never clears old results. Remove domains you've already
checked from the Input tab first if you don't want them checked again.

### Reading the results

| Column | Meaning |
|---|---|
| Domain | The domain checked, without `https://` or `www.` |
| Org name | Column B of your Input tab. Blank if you left it blank, even when a name was detected automatically for the ProPublica lookup |
| EIN | From ProPublica, when a confident name match was found |
| Revenue | Total revenue on the most recent 990 ProPublica has. `Not found` = no confident match or no filings; `Error` = the lookup failed |
| Tax year | The tax year that revenue figure is from |
| Form 990 | Link to that filing on ProPublica |
| Ads running | `Yes`, `No`, or `Error (…)` if the Transparency Center page couldn't be read |
| Ad count | Number of ads the Transparency Center reports for the domain |
| Ad funded by | The "Ad funded by" disclosure text, if the ad has one |
| Funding type | See below |
| Date range | The time window searched (`All time` by default) |
| Date checked | When the check ran |

**Funding type**

| Value | When |
|---|---|
| `Grant` | Ads are running and the disclosure mentions a grant — typically "Google Ad Grants" |
| `Disclosed` | Ads are running with a funding disclosure that doesn't mention a grant |
| `Paid` | Ads are running with **no** funding disclosure — usually paid advertising |
| `None` | No ads found |
| `Error` | The Transparency Center page couldn't be loaded or read |

### Things to keep in mind

- **Only the first ad is opened** to read its funding disclosure. A domain
  running both Ad Grants and paid ads can show either.
- **`Paid` is an inference.** It means the first ad had no disclosure, not that
  the advertiser confirmed paying.
- **Ads are matched by domain.** Ads that point somewhere else, such as a
  separate donation site, won't be found under the org's main domain.
- **Revenue and EIN are best-effort.** The ProPublica search uses the name in
  column B, or the site's own name from its homepage, and only accepts a match
  above 50% name similarity. Small or recently formed nonprofits, and
  organizations whose public name differs from their legal name, often come
  back `Not found`. Adding the legal name in column B helps.
- **`Error` rows aren't retried.** Run the check again for those domains.

---

## How it works

```
Google Sheet — "Run Ads Check" (scripts/sheet_menu.gs)
      │  GET /run?user=<name>
      ▼
Cloud Run /run — reads <name>'s Input tab, makes sure the Output tab exists,
      │          creates one Cloud Task per domain, and returns immediately
      ▼
Cloud Tasks queue "ads-checker"
      │  POST /process {domain, org_name, user}
      ▼
Cloud Run /process — for one domain:
      1. opens the Transparency Center in headless Chromium (Playwright), reads
         the ad count, opens the first ad and reads its "Ad funded by" line
      2. finds the org name (Input column B, else the homepage's
         og:site_name or <title>)
      3. ProPublica: name → EIN → latest filing's revenue and 990 link
      4. appends one row to <name>'s Output tab
```

### Project structure

```
app.py                     Flask routes: /init, /run, /process, /health
config.py                  Settings: date range, region, spreadsheet, tab names, columns
sheets.py                  Google Sheets read/write (gspread)
scraper/
  base.py                  Playwright browser setup, URL builder, org-name lookup
  ads_transparency.py      Transparency Center scraper and funding-type logic
  propublica.py            ProPublica name → EIN → revenue lookup
scripts/sheet_menu.gs      Apps Script for the Sheet menu (runAdsCheck, initWorkspace)
Dockerfile                 Playwright Python base image + gunicorn
```

### Endpoints

| Route | Called by | Does |
|---|---|---|
| `GET /init?user=<name>` | "Set up new workspace" menu item | Creates `<name>`'s Input/Output tabs if missing. Safe to repeat |
| `GET /run?user=<name>` | "Run Ads Check" menu item | Queues one task per domain on `<name>`'s Input tab; returns `{"status": "ok", "enqueued": N}` |
| `POST /process` | Cloud Tasks | Checks one domain and appends its row |
| `GET /health` | Health checks | Returns `{"status": "ok"}` |

---

## Configuration

Behaviour settings live in `config.py`:

| Setting | Default | Effect |
|---|---|---|
| `DATE_PRESET` | `ALL_TIME` | Transparency Center date window: `ALL_TIME`, `LAST_7`, `LAST_30`, `LAST_90`, `LAST_365` |
| `REGION` | `US` | Transparency Center region |
| `REQUEST_DELAY_SECONDS` | `2` | Pause (plus 0.5–1.5s jitter) before opening the first ad |
| `INPUT_COLUMNS` / `OUTPUT_COLUMNS` | — | Header rows written to new tabs. Changing `OUTPUT_COLUMNS` also needs `_result_to_row()` in `sheets.py` changed to match |

`MAX_CONCURRENT_PAGES` is defined but not currently used.

Deployment settings come from environment variables:

| Variable | Purpose |
|---|---|
| `SPREADSHEET_ID` | Target spreadsheet (defaults to the shared workbook above) |
| `GCP_PROJECT_ID` | Project that holds the Cloud Tasks queue |
| `CLOUD_RUN_SERVICE_URL` | This service's own URL; tasks are sent to `<URL>/process` |
| `CLOUD_TASKS_SERVICE_ACCOUNT` | Service account Cloud Tasks signs its requests as |
| `CLOUD_TASKS_QUEUE` | Queue name (default `ads-checker`) |
| `CLOUD_TASKS_LOCATION` | Queue region (default `us-central1`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Local runs only: path to a service-account key. On Cloud Run the attached service account is used instead |

---

## Running locally

```bash
pip install -r requirements.txt
playwright install chromium
```

Put a service-account key at `service_account.json` (see
`service_account.json.example`; the file is git-ignored) and share the
spreadsheet with that account's `client_email` as an Editor. Then:

```bash
GOOGLE_APPLICATION_CREDENTIALS=service_account.json python app.py
```

`/init` and `/health` work fully locally. `/run` creates real Cloud Tasks
(it needs the Cloud Tasks variables above), and Cloud Tasks can only deliver
them to a public URL, so `/process` can't be exercised end-to-end from your
machine. To test the scraper itself, call `scrape_domain()` and `lookup_org()`
directly from a Python shell.

---

## Deploying

The service runs as `sheet-writer@central-search-harmony.iam.gserviceaccount.com`,
which already has Editor access to the spreadsheet.

```bash
gcloud config set project central-search-harmony

gcloud builds submit --tag gcr.io/central-search-harmony/ads-checker && \
gcloud run deploy ads-checker \
  --image gcr.io/central-search-harmony/ads-checker \
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

`--set-env-vars` **replaces** every environment variable on the service, so
always pass the full set above, never just the one you're changing.

Settings live on the service but not in the command above. A redeploy leaves
them as they are:

| Setting | Live value | Why |
|---|---|---|
| Concurrency | 1 request per instance | Each check runs its own Chromium; one at a time keeps it inside 2 GiB |
| Max instances | 20 | Up to 20 domains are checked at once |
| Invoker | `allUsers` | Needed for the Sheet to call it (see [Known limitations](#known-limitations)) |

The `ads-checker` queue sends up to **20 tasks at a time, 5 per second**, and
retries a failed task up to **100 times** with backoff of up to an hour. Only
a failure to write the row is retried.

### One-time setup (already done; for rebuilding from scratch)

```bash
# Queue the /run endpoint sends tasks to
gcloud tasks queues create ads-checker --location=us-central1 \
  --max-concurrent-dispatches=20 --max-dispatches-per-second=5

# One check per instance, up to 20 at once
gcloud run services update ads-checker --region=us-central1 \
  --concurrency=1 --max-instances=20

# Let the service account create tasks that call the service
gcloud run services add-iam-policy-binding ads-checker \
  --region=us-central1 \
  --member="serviceAccount:sheet-writer@central-search-harmony.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

### Sheet menu

The workbook's Apps Script project is shared with the Website Analyzer, and
Apps Script allows only one `onOpen()` per project, so the single menu is
defined in the Website Analyzer repo's
[`apps-script/Menu.gs`](https://github.com/NickBochenekNPM/websiteAnalyzer/blob/main/apps-script/Menu.gs).
`scripts/sheet_menu.gs` here deliberately has no `onOpen()`. It defines
`runAdsCheck()` and `initWorkspace()`, which that menu calls by name.

To change the Ads Checker side, edit `scripts/sheet_menu.gs` and paste it into
the Sheet's Apps Script project (Extensions → Apps Script). It isn't deployed
automatically. `Menu.gs` wires up **Run Ads Check**, **Set up new workspace
(Ads Checker)** and **Help: Ads Checker**.

### README sync

This README is copied into a Google Doc,
[Ads Checker — README](https://docs.google.com/document/d/1PZNOhckXx9VuvouGtJ1Z6ETOcKmwMYPqOtZ1eE5pC9k/edit),
by the **Sync README to Google Doc** GitHub Action
(`.github/workflows/sync-readme.yml`) whenever `README.md` changes on `main`.
You can also run it by hand from the repo's Actions tab. **Edit this file, not
the Doc**: the Doc is overwritten on every sync.

It signs in to Google as `readme-sync@central-search-harmony.iam.gserviceaccount.com`
through workload identity federation, so no key is stored in GitHub. That
account's only access is Editor on the two README Docs. The Website Analyzer
README's [README sync](https://github.com/NickBochenekNPM/websiteAnalyzer#readme-sync)
section covers how it works and what to do if a sync fails. The script,
`.github/scripts/sync_readme_to_doc.py`, is identical in both repos.

---

## Troubleshooting

**"Select your … Ads Checker Input or …Output tab first"**
The tab you had selected isn't an Ads Checker tab. Select your own Input or
Output tab and run it again.

**"Could not read sheet: …" / "No domains found in …"**
There's no Input tab for that name, or it has no domains below the header row.
Use **Set up new workspace**, or check the tab name matches
`<name> - Ads Checker Input` exactly.

**A whole run comes back as `Error` rows**
Google has probably changed the Transparency Center page. The selectors to
update are in `scraper/ads_transparency.py`: `.ads-count-searchable` for the
ad count, `creative-preview` / `[data-creative-id]` for ad cards, and the
"Ad funded by" text match in `extract_funded_by()`.

**Rows are missing**
Look at the service's logs in Cloud Run for `/process` errors. A failure to
write the row returns a 500, so Cloud Tasks retries that domain on its own; a
scraping failure is written as an `Error` row instead and isn't retried.

---

## Known limitations

- **No authentication on the public endpoints.** The service has to allow
  unauthenticated calls so the Sheet can reach it. Anyone with the URL can call
  `/run` and `/init`, and `/process` only checks for Cloud Tasks'
  `X-CloudTasks-QueueName` header, which any caller can send.
- **One browser per domain.** Each `/process` call starts and closes its own
  Chromium. That's simple and isolated, but slower and more memory-hungry
  than sharing one; the service is sized at 2 GiB for it.
- **The org name found automatically isn't written to the Output tab**, only
  used for the ProPublica lookup.
