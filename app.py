import concurrent.futures
from flask import Flask, jsonify
from scraper.base import BrowserManager, polite_delay
from scraper.ads_transparency import scrape_domain
from sheets import read_input_rows, write_output_rows
from config import Config

app = Flask(__name__)

#TODO Ad count is obviously wrong.


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
    try:
        rows = read_input_rows()
    except Exception as e:
        return jsonify({"status": "error", "message": f"Could not read sheet: {e}"}), 500

    if not rows:
        return jsonify({"status": "error", "message": "No domains found in Input sheet."}), 400

    results = []

    with BrowserManager() as manager:
        for row in rows:
            context = manager.new_context()
            try:
                result = scrape_domain(
                    context=context,
                    domain=row["domain"],
                    org_name=row["org_name"],
                )
                results.append(result)
            finally:
                context.close()

            polite_delay()  # pause between domains

    try:
        write_output_rows(results)
    except Exception as e:
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
