import difflib
import logging
import requests

log = logging.getLogger(__name__)

MATCH_THRESHOLD = 0.5


def find_ein(org_name: str) -> str:
    """
    Search ProPublica by org name and return the best-match EIN.
    Free, no API key required.
    """
    url = "https://projects.propublica.org/nonprofits/api/v2/search.json"
    response = requests.get(url, params={"q": org_name})
    data = response.json()

    orgs = data.get("organizations", [])
    if not orgs:
        log.warning("ProPublica: no results for '%s'", org_name)
        return ""

    scored = [
        (difflib.SequenceMatcher(None, org_name.lower(), (o.get("name") or "").lower()).ratio(), o)
        for o in orgs
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    log.info("ProPublica: all results for '%s':", org_name)
    for rank_score, o in scored:
        log.info("  %.2f  EIN %-12s  %s", rank_score, o.get("ein", ""), o.get("name", ""))

    score, best = scored[0]
    ein = best.get("ein", "")
    name = best.get("name", "")
    log.info("ProPublica: selected '%s' (EIN %s, score %.2f)", name, ein, score)

    if score < MATCH_THRESHOLD:
        log.warning("ProPublica: score %.2f below threshold — rejecting match '%s'", score, name)
        return ""

    return ein


def get_org_data(ein: str) -> dict:
    """Fetch revenue and 990 viewer URL from the ProPublica organization endpoint."""
    url = f"https://projects.propublica.org/nonprofits/api/v2/organizations/{ein}.json"
    response = requests.get(url)
    data = response.json()

    org = data.get("organization", {})
    latest_object_id = org.get("latest_object_id", "")

    filings = data.get("filings_with_data", [])
    if not filings:
        log.warning("ProPublica: no filings found for EIN %s", ein)
        return {"revenue": "Not found", "tax_year": "", "form_990_url": ""}

    latest = max(filings, key=lambda f: f.get("tax_prd_yr", 0))
    revenue = latest.get("totrevenue", "")
    tax_year = latest.get("tax_prd_yr", "")

    form_990_url = ""
    if latest_object_id:
        form_990_url = f"https://projects.propublica.org/nonprofits/organizations/{ein}/{latest_object_id}/IRS990"

    log.info("ProPublica: EIN %s — revenue=%s tax_year=%s", ein, revenue, tax_year)
    return {"revenue": revenue, "tax_year": tax_year, "form_990_url": form_990_url}


def lookup_org(org_name: str) -> dict:
    """Full pipeline: name → EIN → revenue + 990 URL. Returns empty fields if org_name is blank."""
    if not org_name.strip():
        log.info("ProPublica: skipping lookup — no org name provided")
        return {"ein": "", "revenue": "", "tax_year": "", "form_990_url": ""}
    ein = find_ein(org_name)
    if not ein:
        return {"ein": "", "revenue": "Not found", "tax_year": "", "form_990_url": ""}
    org_data = get_org_data(ein)
    return {"ein": ein, **org_data}
