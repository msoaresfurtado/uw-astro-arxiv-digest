#!/usr/bin/env python3
"""
UW–Madison Astronomy astro-ph Digest (ADS Version)

What this does:
- Scrapes UW Astronomy faculty names from the department directory page
- Queries NASA ADS for *astro-ph arXiv e-prints* in the last N days
- Filters results to papers authored by one or more UW Astronomy faculty

Key fixes vs your old version:
- Uses ADS `date:` range instead of `entdate:` (prevents "old papers" due to late ingest)
- Requires doctype:eprint AND arxiv_class:astro-ph* (true arXiv-style astro-ph)
- Matches by faculty author list (department-specific), not UW-wide affiliation strings
"""

import os
import re
import ssl
import smtplib
import requests
from itertools import islice
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from html import unescape


ADS_API_URL = "https://api.adsabs.harvard.edu/v1/search/query"
FACULTY_URL = "https://www.astro.wisc.edu/people/faculty/filter/faculty/"


# -----------------------------
# Faculty scraping
# -----------------------------

NAME_LINE_RE = re.compile(
    r"^\s*([A-Z][A-Za-z\u00C0-\u017F'\-\. ]+),\s*([A-Z][A-Za-z\u00C0-\u017F'\-\. ]+)\s*$"
)

def scrape_faculty_names(url: str, debug: bool = False) -> list[str]:
    """
    Scrape faculty names from the UW Astronomy directory page.

    The UW site may block some automated requests depending on headers/network.
    We set a browser-ish User-Agent and accept compression.
    If scraping fails, you can provide FACULTY_NAMES in env as a fallback.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        if debug:
            print(f"DEBUG: Faculty scrape failed: {e}")
        return []

    # Crude HTML→text: enough to find "Last, First" lines in the directory
    text = unescape(html)
    text = re.sub(r"<script\b[^<]*(?:(?!</script>)<[^<]*)*</script>", " ", text, flags=re.I)
    text = re.sub(r"<style\b[^<]*(?:(?!</style>)<[^<]*)*</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)

    names = []
    for line in text.splitlines():
        m = NAME_LINE_RE.match(line.strip())
        if m:
            last, first = m.group(1).strip(), m.group(2).strip()
            # avoid obvious non-person lines
            if len(last) >= 2 and len(first) >= 2:
                names.append(f"{last}, {first}")

    # Deduplicate while preserving order
    seen = set()
    out = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)

    if debug:
        print(f"DEBUG: Scraped {len(out)} faculty names")
        print("DEBUG: First 10 names:", out[:10])

    return out


def get_faculty_names(debug: bool = False) -> list[str]:
    """
    Primary: scrape from FACULTY_URL
    Fallback: FACULTY_NAMES env var (semicolon-separated "Last, First; Last, First; ...")
    """
    names = scrape_faculty_names(FACULTY_URL, debug=debug)
    if names:
        return names

    # Fallback for when the site blocks scraping from your environment
    env = os.environ.get("FACULTY_NAMES", "").strip()
    if env:
        fallback = [x.strip() for x in env.split(";") if x.strip()]
        if debug:
            print(f"DEBUG: Using FACULTY_NAMES fallback with {len(fallback)} names")
        return fallback

    raise RuntimeError(
        "Could not scrape faculty names and no FACULTY_NAMES fallback was provided.\n"
        "Set FACULTY_NAMES like:\n"
        "  export FACULTY_NAMES='Barger, Amy; Becker, Juliette; ...'\n"
    )


# -----------------------------
# ADS querying
# -----------------------------

def chunked(iterable, n):
    it = iter(iterable)
    while True:
        chunk = list(islice(it, n))
        if not chunk:
            break
        yield chunk


def iso_utc(dt: datetime) -> str:
    """Return RFC3339-ish UTC timestamp string used by ADS `date:` field."""
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def query_ads_for_faculty(
    api_key: str,
    faculty_names: list[str],
    days_back: int = 7,
    rows_per_query: int = 200,
    author_chunk_size: int = 10,
    debug: bool = False,
) -> list[dict]:
    """
    Query ADS for astro-ph eprints in a date range authored by UW Astro faculty.

    Critical choices:
    - date:[start TO end] uses ADS machine-readable pubdate (not entdate). :contentReference[oaicite:1]{index=1}
    - doctype:eprint + arxiv_class:astro-ph* => arXiv-style astro-ph eprints
    - Authors are OR'ed, chunked to avoid oversized query strings
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_back)

    # Use end-of-day inclusive window in UTC
    start_s = iso_utc(start.replace(hour=0, minute=0, second=0, microsecond=0))
    end_s = iso_utc(end.replace(hour=23, minute=59, second=59, microsecond=0))

    date_clause = f'date:[{start_s} TO {end_s}]'
    base_clause = 'doctype:eprint AND arxiv_class:"astro-ph*"'

    headers = {"Authorization": f"Bearer {api_key}"}

    all_docs = []
    seen_bibcodes = set()

    for group in chunked(faculty_names, author_chunk_size):
        # Build author:(... OR ... OR ...) group
        # Using full "Last, First" improves precision in ADS author matching.
        author_terms = " OR ".join([f'author:"{name}"' for name in group])
        q = f"({base_clause}) AND ({date_clause}) AND ({author_terms})"

        params = {
            "q": q,
            "fl": "title,author,abstract,bibcode,identifier,keyword,pubdate,date,arxiv_class",
            "rows": rows_per_query,
            "sort": "date desc",
        }

        if debug:
            print("\nDEBUG: ADS query chunk:")
            print(q)

        resp = requests.get(ADS_API_URL, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        docs = resp.json().get("response", {}).get("docs", []) or []

        if debug:
            print(f"DEBUG: Returned {len(docs)} docs for this chunk")

        for d in docs:
            bib = d.get("bibcode")
            if bib and bib not in seen_bibcodes:
                seen_bibcodes.add(bib)
                all_docs.append(d)

    # Sort final unique list by ADS `date` desc
    all_docs.sort(key=lambda x: x.get("date", ""), reverse=True)
    return all_docs


def get_arxiv_id(paper: dict) -> str | None:
    identifiers = paper.get("identifier", []) or []
    for ident in identifiers:
        if isinstance(ident, str) and ident.startswith("arXiv:"):
            return ident.replace("arXiv:", "")
    return None


def get_arxiv_url(paper: dict) -> str:
    arxiv_id = get_arxiv_id(paper)
    if arxiv_id:
        return f"https://arxiv.org/abs/{arxiv_id}"
    bibcode = paper.get("bibcode", "")
    return f"https://ui.adsabs.harvard.edu/abs/{bibcode}"


def get_primary_category(paper: dict) -> str:
    classes = paper.get("arxiv_class", []) or []
    return classes[0] if classes else "astro-ph"


def faculty_hits(paper: dict, faculty_names: list[str]) -> list[str]:
    """
    Identify which faculty appear in the ADS author list.

    Note: ADS author strings are usually "Last, F." etc.
    We match on last name + first initial to be robust.
    """
    authors = paper.get("author", []) or []
    author_join = " | ".join(authors).lower()

    hits = []
    for full in faculty_names:
        last, first = [x.strip() for x in full.split(",", 1)]
        key = f"{last}, {first[0]}".lower()
        if key in author_join:
            hits.append(full)

    # If nothing matched by initial, fallback to last-name-only (can create rare false positives)
    if not hits:
        for full in faculty_names:
            last = full.split(",", 1)[0].strip().lower()
            if re.search(rf"\b{re.escape(last)}\b", author_join):
                hits.append(full)

    # Dedup
    seen = set()
    out = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


# -----------------------------
# Email formatting (kept close to your original)
# -----------------------------

def format_paper_html(paper: dict, hits: list[str]) -> str:
    title = (paper.get("title") or ["Untitled"])[0]
    authors = paper.get("author", []) or []
    abstract = paper.get("abstract", "No abstract available.")
    url = get_arxiv_url(paper)
    category = get_primary_category(paper)

    author_str = ", ".join(authors[:10]) + (f" et al. ({len(authors)} authors)" if len(authors) > 10 else "")
    hit_str = ", ".join(hits) if hits else "Unknown"

    if len(abstract) > 500:
        abstract = abstract[:500] + "..."

    return f"""
    <div style="margin-bottom: 20px; padding: 15px; border-left: 3px solid #c5050c; background-color: #f9f9f9;">
        <h3 style="margin: 0 0 8px 0;">
            <a href="{url}" style="color: #0479a8; text-decoration: none;">{title}</a>
        </h3>
        <p style="margin: 0 0 8px 0; color: #c5050c; font-size: 14px;">
            <strong>UW Astro faculty:</strong> {hit_str}
        </p>
        <p style="margin: 0 0 8px 0; color: #666; font-size: 14px;">
            <strong>All Authors:</strong> {author_str}
        </p>
        <p style="margin: 0 0 8px 0; color: #666; font-size: 14px;">
            <strong>Category:</strong> {category}
        </p>
        <p style="margin: 0; font-size: 14px; line-height: 1.5;">
            {abstract}
        </p>
    </div>
    """


def format_paper_text(paper: dict, hits: list[str]) -> str:
    title = (paper.get("title") or ["Untitled"])[0]
    authors = paper.get("author", []) or []
    abstract = paper.get("abstract", "No abstract available.")
    url = get_arxiv_url(paper)
    category = get_primary_category(paper)

    author_str = ", ".join(authors[:10]) + (f" et al. ({len(authors)} authors)" if len(authors) > 10 else "")
    hit_str = ", ".join(hits) if hits else "Unknown"

    if len(abstract) > 500:
        abstract = abstract[:500] + "..."

    return f"""
{title}
{'-' * min(len(title), 80)}
UW Astro faculty: {hit_str}
All Authors: {author_str}
Category: {category}
Link: {url}

{abstract}

"""


def create_email_content(papers_with_hits: list[tuple[dict, list[str]]], days_back: int) -> tuple[str, str, str]:
    end = datetime.now()
    start = end - timedelta(days=days_back)
    date_range = f"{start.strftime('%B %d')} to {end.strftime('%B %d, %Y')}"

    if not papers_with_hits:
        subject = "UW Astronomy astro-ph Digest: No papers this week"
        html = f"""
        <html><body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
          <h1 style="color: #c5050c; border-bottom: 2px solid #c5050c; padding-bottom: 10px;">UW Astronomy astro-ph Digest</h1>
          <p style="color: #666;">Papers from {date_range}</p>
          <p>No astro-ph arXiv e-prints from UW Astronomy faculty were found in this window.</p>
        </body></html>
        """
        text = f"UW Astronomy astro-ph Digest\n{date_range}\n\nNo papers found this week."
        return subject, html, text

    subject = f"UW Astronomy astro-ph Digest: {len(papers_with_hits)} paper{'s' if len(papers_with_hits) != 1 else ''} this week"

    by_category = defaultdict(list)
    for paper, hits in papers_with_hits:
        by_category[get_primary_category(paper)].append((paper, hits))

    html_papers = ""
    for cat in sorted(by_category.keys()):
        cat_papers = by_category[cat]
        html_papers += f'<h2 style="color: #333; margin-top: 30px;">{cat} ({len(cat_papers)})</h2>'
        for paper, hits in cat_papers:
            html_papers += format_paper_html(paper, hits)

    html = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
      <h1 style="color: #c5050c; border-bottom: 2px solid #c5050c; padding-bottom: 10px;">UW Astronomy astro-ph Digest</h1>
      <p style="color: #666;">Papers from {date_range}</p>
      <p style="font-size: 18px;"><strong>{len(papers_with_hits)}</strong> astro-ph e-print{"s" if len(papers_with_hits) != 1 else ""} with UW Astronomy faculty authors</p>
      {html_papers}
      <hr style="margin-top: 40px; border: none; border-top: 1px solid #ddd;">
      <p style="color: #999; font-size: 12px;">Automatically generated using NASA ADS.</p>
    </body></html>
    """

    text_papers = ""
    for cat in sorted(by_category.keys()):
        cat_papers = by_category[cat]
        text_papers += f"\n{'=' * 60}\n{cat} ({len(cat_papers)})\n{'=' * 60}\n"
        for paper, hits in cat_papers:
            text_papers += format_paper_text(paper, hits)

    text = f"""UW Astronomy astro-ph Digest
{date_range}

{len(papers_with_hits)} astro-ph e-print{"s" if len(papers_with_hits) != 1 else ""} with UW Astronomy faculty authors
{text_papers}
"""
    return subject, html, text


def send_email(subject: str, html_content: str, text_content: str):
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    sender_email = os.environ["SENDER_EMAIL"]
    sender_password = os.environ["SENDER_PASSWORD"]
    recipient_email = os.environ["RECIPIENT_EMAIL"]

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = sender_email
    message["To"] = recipient_email

    message.attach(MIMEText(text_content, "plain"))
    message.attach(MIMEText(html_content, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls(context=context)
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, message.as_string())

    print(f"Email sent successfully to {recipient_email}")


def main():
    api_key = os.environ.get("ADS_API_KEY")
    if not api_key:
        raise ValueError("ADS_API_KEY environment variable is required")

    days_back = int(os.environ.get("DAYS_BACK", "7"))
    debug = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")

    print("Fetching UW Astronomy faculty names...")
    faculty = get_faculty_names(debug=debug)
    print(f"Faculty names loaded: {len(faculty)}")

    print(f"Querying ADS for astro-ph eprints from last {days_back} days...")
    papers = query_ads_for_faculty(
        api_key=api_key,
        faculty_names=faculty,
        days_back=days_back,
        debug=debug,
    )

    # Attach which faculty hit each paper (for display)
    papers_with_hits = []
    for p in papers:
        hits = faculty_hits(p, faculty)
        papers_with_hits.append((p, hits))

    print(f"Found {len(papers_with_hits)} astro-ph eprints with UW Astronomy faculty authors")
    for paper, hits in papers_with_hits[:25]:
        title = (paper.get("title") or ["Untitled"])[0]
        print(f"  - {title[:80]}")
        print(f"    Faculty: {', '.join(hits) if hits else 'Unknown'}")

    subject, html, text = create_email_content(papers_with_hits, days_back)

    if os.environ.get("SENDER_EMAIL"):
        send_email(subject, html, text)
    else:
        print("\nEmail credentials not configured. Email content:\n")
        print(text)


if __name__ == "__main__":
    main()
