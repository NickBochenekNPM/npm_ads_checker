import json
import logging
from flask import Flask, jsonify, request
from google.cloud import tasks_v2
from scraper.base import BrowserManager, fetch_org_name
from scraper.ads_transparency import scrape_domain
from scraper.propublica import lookup_org
from sheets import read_input_rows, write_output_header, append_output_row
from config import Config

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
    Dispatcher endpoint — reads the Input sheet, resets the Output sheet header,
    and enqueues one Cloud Task per domain. Returns immediately.
    """
    log.info("Run triggered")

    try:
        rows = read_input_rows()
    except Exception as e:
        log.error("Could not read input sheet: %s", e)
        return jsonify({"status": "error", "message": f"Could not read sheet: {e}"}), 500

    if not rows:
        return jsonify({"status": "error", "message": "No domains found in Input sheet."}), 400

    try:
        write_output_header()
    except Exception as e:
        log.error("Could not initialize Output sheet: %s", e)
        return jsonify({"status": "error", "message": f"Could not initialize Output sheet: {e}"}), 500

    tasks_client = tasks_v2.CloudTasksClient()
    queue_path = tasks_client.queue_path(
        Config.GCP_PROJECT_ID,
        Config.CLOUD_TASKS_LOCATION,
        Config.CLOUD_TASKS_QUEUE,
    )

    enqueued = 0
    for row in rows:
        payload = json.dumps({"domain": row["domain"], "org_name": row["org_name"]}).encode()
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": f"{Config.CLOUD_RUN_SERVICE_URL}/process",
                "headers": {"Content-Type": "application/json"},
                "body": payload,
                "oidc_token": {"service_account_email": Config.CLOUD_TASKS_SERVICE_ACCOUNT},
            }
        }
        tasks_client.create_task(parent=queue_path, task=task)
        enqueued += 1

    log.info("Enqueued %d task(s)", enqueued)
    return jsonify({"status": "ok", "enqueued": enqueued})


@app.route("/process", methods=["POST"])
def process():
    """
    Worker endpoint called by Cloud Tasks — processes one domain.
    Cloud Tasks sends an OIDC token; restrict this route to Cloud Run invokers only via IAM.
    The X-CloudTasks-QueueName header provides a secondary guard against accidental direct calls.
    """
    if not request.headers.get("X-CloudTasks-QueueName"):
        return jsonify({"status": "error", "message": "Forbidden"}), 403

    data = request.get_json(force=True)
    domain = (data.get("domain") or "").strip()
    org_name = (data.get("org_name") or "").strip()

    if not domain:
        return jsonify({"status": "error", "message": "Missing domain"}), 400

    log.info("Processing: %s", domain)

    with BrowserManager() as manager:
        context = manager.new_context()
        try:
            result = scrape_domain(context=context, domain=domain, org_name=org_name)
        finally:
            context.close()

    if not org_name:
        org_name = fetch_org_name(result["domain"])

    try:
        propublica_data = lookup_org(org_name)
    except Exception as e:
        log.warning("ProPublica lookup failed for '%s': %s", org_name, e)
        propublica_data = {"ein": "", "revenue": "Error", "tax_year": ""}

    result.update(propublica_data)

    try:
        append_output_row(result)
    except Exception as e:
        log.error("Could not append row for %s: %s", domain, e)
        return jsonify({"status": "error", "message": str(e)}), 500

    log.info("Done: %s (ads: %s, funding: %s)", domain, result["ads_running"], result["funding_type"])
    return jsonify({"status": "ok", "domain": domain, "ads_running": result["ads_running"], "funding_type": result["funding_type"]})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
