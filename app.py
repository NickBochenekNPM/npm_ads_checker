import concurrent.futures
import logging
from flask import Flask, jsonify
from scraper.base import BrowserManager, polite_delay, fetch_org_name
from scraper.ads_transparency import scrape_domain
from scraper.propublica import lookup_org
from sheets import read_input_rows, write_output_rows

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/run", methods=["GET"])
def run():
    """
    Main trigger endpoint.
    Coworkers visit /run in their browser to kick off a scrape.

    Flow:
    1. Read domains from the Input sheet
    2. Scrape each domain (Ads Transparency Center)
    3. Write results to the Output sheet
    4. Return a summary JSON response
    """
    log.info("Run triggered")

    try:
        rows = read_input_rows()
    except Exception as e:
        log.error("Could not read input sheet: %s", e)
        return jsonify({"status": "error", "message": f"Could not read sheet: {e}"}), 500

    if not rows:
        log.warning("No domains found in Input sheet")
        return jsonify({"status": "error", "message": "No domains found in Input sheet."}), 400

    log.info("Loaded %d domain(s) from Input sheet", len(rows))
    results = []

    with BrowserManager() as manager:
        for i, row in enumerate(rows, start=1):
            domain = row["domain"]
            org_name = row["org_name"]
            log.info("[%d/%d] Scraping ads: %s", i, len(rows), domain)

            context = manager.new_context()
            try:
                result = scrape_domain(
                    context=context,
                    domain=domain,
                    org_name=org_name,
                )
            finally:
                context.close()

            log.info("[%d/%d] Ads result: %s (funding: %s)", i, len(rows), result["ads_running"], result["funding_type"])

            if not org_name:
                org_name = fetch_org_name(result["domain"])

            log.info("[%d/%d] Looking up financials: %s", i, len(rows), org_name or "(no name found)")
            try:
                propublica_data = lookup_org(org_name)
            except Exception as e:
                log.warning("[%d/%d] ProPublica lookup failed for '%s': %s", i, len(rows), org_name, e)
                propublica_data = {"ein": "", "revenue": "Error", "tax_year": ""}

            log.info("[%d/%d] Financials: EIN=%s revenue=%s (%s)", i, len(rows), propublica_data.get("ein"), propublica_data.get("revenue"), propublica_data.get("tax_year"))

            result.update(propublica_data)
            results.append(result)
            polite_delay()  # pause between domains

    log.info("Scraping complete. Writing %d row(s) to Output sheet", len(results))
    try:
        write_output_rows(results)
    except Exception as e:
        log.error("Could not write to Output sheet: %s", e)
        return jsonify({
            "status": "error",
            "message": f"Scrape completed but could not write to sheet: {e}",
            "results": results,
        }), 500

    # Build a plain-English summary
    ads_running = [r for r in results if r["ads_running"] == "Yes"]
    paid = [r for r in ads_running if r["funding_type"] == "Paid"]
    grant = [r for r in ads_running if r["funding_type"] == "Grant"]
    errors = [r for r in results if "Error" in str(r.get("ads_running", ""))]

    log.info("Done. total=%d ads_running=%d paid=%d grant=%d errors=%d",
             len(results), len(ads_running), len(paid), len(grant), len(errors))

    return jsonify({
        "status": "success",
        "summary": {
            "total_checked": len(results),
            "ads_running": len(ads_running),
            "paid_ads": len(paid),
            "grant_funded": len(grant),
            "no_ads": len(results) - len(ads_running),
            "errors": len(errors),
        },
        "results": results,
    })


@app.route("/health", methods=["GET"])
def health():
    """Simple health check — confirms the app is running."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    # Local development only — Cloud Run uses gunicorn
    app.run(host="0.0.0.0", port=8080, debug=True)
