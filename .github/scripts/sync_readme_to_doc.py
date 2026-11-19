"""
Copy README.md into a Google Doc, replacing the Doc's contents.

Run by .github/workflows/sync-readme.yml whenever README.md changes on main,
so people who never open GitHub can read the README in Drive. The README stays
the source of truth: the Doc says so at the top, and anything edited in the Doc
is overwritten on the next sync.

Environment:
  GOOGLE_ACCESS_TOKEN  OAuth token with the drive scope, for an account that
                       is an Editor on the Doc (in Actions: readme-sync@…,
                       via workload identity federation — no stored key)
  DOC_ID               The Google Doc to overwrite
  GITHUB_REPOSITORY    owner/name — set by Actions; used to turn relative
                       links into GitHub links and to label the Doc
  GITHUB_SHA           Commit being synced — set by Actions (optional locally)

Same file in websiteAnalyzer and npm_ads_checker; keep them identical.
"""

import html
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[2]


def absolutize_links(md: str, repo: str) -> str:
    """
    Point relative links at GitHub. In the Doc, "apps-script/Menu.gs" means
    nothing; "https://github.com/<repo>/blob/main/apps-script/Menu.gs" works.
    Absolute URLs, in-page anchors and mailto: links are left alone.
    """
    def fix(match):
        text, target = match.group(1), match.group(2)
        if re.match(r"^(https?:|mailto:|#)", target):
            return match.group(0)
        return f"[{text}](https://github.com/{repo}/blob/main/{target.removeprefix('./')})"

    return re.sub(r"\[([^\]]*)\]\(([^)\s]+)\)", fix, md)


def flatten_code_blocks(body: str) -> str:
    """
    Turn each <pre><code> block into a monospace paragraph with <br> line
    breaks. Drive's HTML-to-Doc conversion returns a bare 500 on longer <pre>
    blocks (a 29-line shell block in the Website Analyzer README failed every
    time, any 16 lines of it passed), and the paragraph form converts reliably.
    """
    def repl(match):
        lines = match.group(1).rstrip("\n").split("\n")
        # Keep indentation: leading spaces collapse in HTML, so make them hard.
        lines = [re.sub(r"^ +", lambda m: "&nbsp;" * len(m.group(0)), line) for line in lines]
        return (
            '<p style="font-family:\'Roboto Mono\',monospace;font-size:9pt;'
            'background-color:#f6f8fa">' + "<br>".join(lines) + "</p>"
        )

    return re.sub(r"<pre><code[^>]*>(.*?)</code></pre>", repl, body, flags=re.S)


def render(md: str, repo: str, sha: str) -> str:
    body = flatten_code_blocks(markdown.markdown(
        absolutize_links(md, repo),
        extensions=["tables", "fenced_code", "sane_lists"],
    ))
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    source = f"https://github.com/{repo}/blob/main/README.md"
    commit = f" (commit {html.escape(sha[:7])})" if sha else ""
    notice = (
        f'<p style="color:#666666"><i>Copied automatically from '
        f'<a href="{source}">README.md in {html.escape(repo)}</a>{commit} '
        f"on {stamp}. Edit the README there — changes made in this document "
        f"are overwritten on the next update.</i></p><hr>"
    )
    # Docs' HTML import gives tables no borders and code no font unless asked.
    style = (
        "<style>"
        "table{border-collapse:collapse} td,th{border:1px solid #bbbbbb;padding:4px 6px;vertical-align:top}"
        "th{background:#f1f3f4} code{font-family:'Roboto Mono',monospace;font-size:9pt}"
        "</style>"
    )
    return f"<html><head><meta charset='utf-8'>{style}</head><body>{notice}{body}</body></html>"


def upload(doc_id: str, token: str, html_doc: str) -> None:
    """Replace the Doc's contents. Uploading HTML to an existing Doc converts it."""
    req = urllib.request.Request(
        f"https://www.googleapis.com/upload/drive/v3/files/{doc_id}"
        "?uploadType=media&supportsAllDrives=true&fields=id,name,modifiedTime",
        data=html_doc.encode("utf-8"),
        method="PATCH",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "text/html; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            print(f"Updated Doc: {resp.read().decode()}")
    except urllib.error.HTTPError as e:
        # 404 here usually means the account isn't an Editor on the Doc.
        sys.exit(f"Drive API returned {e.code}: {e.read().decode(errors='replace')}")


def main() -> None:
    token = os.environ.get("GOOGLE_ACCESS_TOKEN", "")
    if not token:
        sys.exit("GOOGLE_ACCESS_TOKEN is empty — the Google auth step didn't produce a token.")
    doc_id = os.environ["DOC_ID"]
    repo = os.environ["GITHUB_REPOSITORY"]
    sha = os.environ.get("GITHUB_SHA", "")
    md = (ROOT / "README.md").read_text(encoding="utf-8")
    upload(doc_id, token, render(md, repo, sha))


if __name__ == "__main__":
    main()
