#!/usr/bin/env python3
"""
UW-Madison Astro-ph arXiv Digest (ADS Version)

Queries NASA ADS for astronomy papers with UW-Madison affiliated authors.

Note: ADS affiliation indexing lags arXiv submissions by 1-3 days.
This is unavoidable without maintaining a manual author list.
The script filters out old papers that get re-indexed when published.
"""

import requests
import smtplib
import ssl
import os
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from collections import defaultdict


ADS_API_URL = "https://api.adsabs.harvard.edu/v1/search/query"


# =============================================================================
# UW-MADISON AFFILIATION MATCHING
# =============================================================================

UW_MADISON_PATTERNS = [
    r"university of wisconsin[\s,\-\u2013\u2014]*madison",
    r"uw[\s\-\u2013\u2014]+madison",
    r"u\.?\s*of\s*w\.?[\s,\-\u2013\u2014]+madison",
    r"univ\.?\s*(of\s*)?wisconsin[\s,\-\u2013\u2014]*madison",
]

UW_MADISON_REGEX = re.compile("|".join(UW_MADISON_PATTERNS), re.IGNORECASE)

OTHER_UW_CAMPUSES = [
    "milwaukee", "green bay", "la crosse", "eau claire", "oshkosh", 
    "parkside", "platteville", "river falls", "stevens point", 
    "stout", "superior", "whitewater"
]


def is_uw_madison_affiliation(affiliation: str) -> bool:
    """Check if an affiliation string indicates UW-Madison."""
    if not affiliation:
        return False
    
    aff_lower = affiliation.lower()
    
    if "wisconsin" not in aff_lower:
        return False
    
    if any(campus in aff_lower for campus in OTHER_UW_CAMPUSES):
        return False
    
    if UW_MADISON_REGEX.search(affiliation):
        return True
    
    if "madison" in aff_lower:
        return True
    
    return False


# =============================================================================
# ARXIV DATE EXTRACTION (to filter old re-indexed papers)
# =============================================================================

def get_arxiv_id(paper: dict) -> str | None:
    """Extract arXiv ID from ADS paper record."""
    identifiers = paper.get("identifier", [])
    for ident in identifiers:
        if ident.startswith("arXiv:"):
            return ident.replace("arXiv:", "")
    return None


def get_arxiv_submission_month(paper: dict) -> tuple[int, int] | None:
    """
    Return (year, month) from arXiv ID, or None if not an arXiv paper.
    
    arXiv IDs use format YYMM.NNNNN (e.g., 2410.08313 = October 2024)
    """
    arxiv_id = get_arxiv_id(paper)
    if not arxiv_id:
        return None
    match = re.match(r'(\d{2})(\d{2})\.', arxiv_id)
    if match:
        return (2000 + int(match.group(1)), int(match.group(2)))
    return None


def is_recent_submission(paper: dict, max_months_old: int = 2) -> bool:
    """
    Check if paper's arXiv submission is recent.
    
    Returns True if:
    - Paper has no arXiv ID (journal-only, keep it)
    - Paper was submitted to arXiv within max_months_old
    
    Returns False if paper is an old arXiv submission that was
    just re-indexed (e.g., when journal version published).
    """
    sub = get_arxiv_submission_month(paper)
    if sub is None:
        return True
    
    year, month = sub
    now = datetime.now()
    months_ago = (now.year - year) * 12 + (now.month - month)
    return months_ago <= max_months_old


# =============================================================================
# ADS QUERY
# =============================================================================

def query_ads(api_key: str, days_back: int = 7, debug: bool = False) -> list:
    """
    Query ADS for recent astro-ph papers with UW-Madison affiliations.
    """
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    date_range = f"[{start_date.strftime('%Y-%m-%d')} TO {end_date.strftime('%Y-%m-%d')}]"
    
    # Query for Wisconsin affiliations indexed in the date range
    query = f'aff:Wisconsin entdate:{date_range}'
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    params = {
        "q": query,
        "fl": "title,author,aff,abstract,bibcode,identifier,keyword,pubdate,arxiv_class",
        "rows": 500,
        "sort": "date desc",
    }
    
    if debug:
        print(f"DEBUG: Query = {query}")
    
    response = requests.get(ADS_API_URL, headers=headers, params=params)
    response.raise_for_status()
    
    data = response.json()
    papers = data.get("response", {}).get("docs", [])
    
    if debug:
        print(f"DEBUG: Raw results from ADS: {len(papers)}")
    
    # Filter 1: Astronomy papers only
    astro_papers = []
    for paper in papers:
        arxiv_classes = paper.get("arxiv_class", [])
        is_astro = any(c.startswith("astro-ph") for c in arxiv_classes) if arxiv_classes else False
        
        bibcode = paper.get("bibcode", "")
        astro_journals = ["ApJ", "ApJL", "ApJS", "AJ", "MNRAS", "A&A", "PASP", 
                         "ARA&A", "Icar", "PSJ", "NatAs", "arXiv"]
        is_astro_journal = any(j in bibcode for j in astro_journals)
        
        if is_astro or is_astro_journal:
            astro_papers.append(paper)
    
    if debug:
        print(f"DEBUG: After astro filter: {len(astro_papers)}")
    
    # Filter 2: Confirmed UW-Madison affiliation (not other UW campuses)
    confirmed_papers = []
    for paper in astro_papers:
        uw_authors = get_uw_authors(paper)
        if uw_authors:
            confirmed_papers.append(paper)
    
    if debug:
        print(f"DEBUG: After UW-Madison filter: {len(confirmed_papers)}")
    
    # Filter 3: Recent arXiv submissions only (exclude old re-indexed papers)
    recent_papers = []
    for paper in confirmed_papers:
        if is_recent_submission(paper, max_months_old=2):
            recent_papers.append(paper)
        elif debug:
            title = paper.get("title", ["?"])[0][:50]
            sub = get_arxiv_submission_month(paper)
            print(f"DEBUG: Filtered old paper: {title}... (arXiv: {sub})")
    
    if debug:
        print(f"DEBUG: After recency filter: {len(recent_papers)}")
    
    return recent_papers


# =============================================================================
# PAPER FORMATTING
# =============================================================================

def get_uw_authors(paper: dict) -> list:
    """Extract UW-Madison affiliated authors from a paper."""
    authors = paper.get("author", [])
    affiliations = paper.get("aff", [])
    
    uw_authors = []
    for i, author in enumerate(authors):
        if i < len(affiliations):
            aff = affiliations[i]
            if is_uw_madison_affiliation(aff):
                uw_authors.append(author)
    
    return uw_authors


def get_arxiv_url(paper: dict) -> str:
    """Get arXiv or ADS URL for a paper."""
    arxiv_id = get_arxiv_id(paper)
    if arxiv_id:
        return f"https://arxiv.org/abs/{arxiv_id}"
    bibcode = paper.get("bibcode", "")
    return f"https://ui.adsabs.harvard.edu/abs/{bibcode}"


def get_arxiv_category(paper: dict) -> str:
    """Get primary arXiv category."""
    classes = paper.get("arxiv_class", [])
    return classes[0] if classes else "astro-ph"


def format_paper_html(paper: dict) -> str:
    """Format a single paper as HTML."""
    
    title = paper.get("title", ["Untitled"])[0]
    authors = paper.get("author", [])
    abstract = paper.get("abstract", "No abstract available.")
    url = get_arxiv_url(paper)
    category = get_arxiv_category(paper)
    uw_authors = get_uw_authors(paper)
    
    if len(authors) > 10:
        author_str = ", ".join(authors[:10]) + f" et al. ({len(authors)} authors)"
    else:
        author_str = ", ".join(authors)
    
    uw_str = ", ".join(uw_authors) if uw_authors else "Unknown"
    
    if len(abstract) > 500:
        abstract = abstract[:500] + "..."
    
    return f"""
    <div style="margin-bottom: 20px; padding: 15px; border-left: 3px solid #c5050c; background-color: #f9f9f9;">
        <h3 style="margin: 0 0 8px 0;">
            <a href="{url}" style="color: #0479a8; text-decoration: none;">{title}</a>
        </h3>
        <p style="margin: 0 0 8px 0; color: #c5050c; font-size: 14px;">
            <strong>UW-Madison:</strong> {uw_str}
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


def format_paper_text(paper: dict) -> str:
    """Format a single paper as plain text."""
    
    title = paper.get("title", ["Untitled"])[0]
    authors = paper.get("author", [])
    abstract = paper.get("abstract", "No abstract available.")
    url = get_arxiv_url(paper)
    category = get_arxiv_category(paper)
    uw_authors = get_uw_authors(paper)
    
    if len(authors) > 10:
        author_str = ", ".join(authors[:10]) + f" et al. ({len(authors)} authors)"
    else:
        author_str = ", ".join(authors)
    
    uw_str = ", ".join(uw_authors) if uw_authors else "Unknown"
    
    if len(abstract) > 500:
        abstract = abstract[:500] + "..."
    
    return f"""
{title}
{'-' * min(len(title), 80)}
UW-Madison: {uw_str}
All Authors: {author_str}
Category: {category}
Link: {url}

{abstract}

"""


# =============================================================================
# EMAIL
# =============================================================================

def create_email_content(papers: list, days_back: int) -> tuple:
    """Create HTML and plain text email content."""
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    date_range = f"{start_date.strftime('%B %d')} to {end_date.strftime('%B %d, %Y')}"
    
    if not papers:
        subject = "UW-Madison Astro-ph Digest: No papers this week"
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #c5050c; border-bottom: 2px solid #c5050c; padding-bottom: 10px;">
                UW-Madison Astro-ph Digest
            </h1>
            <p style="color: #666;">Papers from {date_range}</p>
            <p>No papers with UW-Madison affiliated authors were found on astro-ph this week.</p>
        </body>
        </html>
        """
        text = f"UW-Madison Astro-ph Digest\n{date_range}\n\nNo papers found this week."
        return subject, html, text
    
    subject = f"UW-Madison Astro-ph Digest: {len(papers)} paper{'s' if len(papers) != 1 else ''} this week"
    
    by_category = defaultdict(list)
    for paper in papers:
        category = get_arxiv_category(paper)
        by_category[category].append(paper)
    
    html_papers = ""
    for cat in sorted(by_category.keys()):
        cat_papers = by_category[cat]
        html_papers += f'<h2 style="color: #333; margin-top: 30px;">{cat} ({len(cat_papers)})</h2>'
        for paper in cat_papers:
            html_papers += format_paper_html(paper)
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
        <h1 style="color: #c5050c; border-bottom: 2px solid #c5050c; padding-bottom: 10px;">
            UW-Madison Astro-ph Digest
        </h1>
        <p style="color: #666;">Papers from {date_range}</p>
        <p style="font-size: 18px;"><strong>{len(papers)}</strong> paper{"s" if len(papers) != 1 else ""} with UW-Madison affiliated authors</p>
        {html_papers}
        <hr style="margin-top: 40px; border: none; border-top: 1px solid #ddd;">
        <p style="color: #999; font-size: 12px;">
            This digest is automatically generated using NASA ADS.
            New papers may take 1-3 days to appear due to ADS indexing.
        </p>
    </body>
    </html>
    """
    
    text_papers = ""
    for cat in sorted(by_category.keys()):
        cat_papers = by_category[cat]
        text_papers += f"\n{'=' * 60}\n{cat} ({len(cat_papers)})\n{'=' * 60}\n"
        for paper in cat_papers:
            text_papers += format_paper_text(paper)
    
    text = f"""UW-Madison Astro-ph Digest
{date_range}

{len(papers)} paper{"s" if len(papers) != 1 else ""} with UW-Madison affiliated authors
{text_papers}
---
Note: New papers may take 1-3 days to appear due to ADS indexing.
"""
    
    return subject, html, text


def send_email(subject: str, html_content: str, text_content: str):
    """Send the digest email."""
    
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


# =============================================================================
# DEBUG / TEST
# =============================================================================

def test_paper_lookup(api_key: str, bibcode: str):
    """Debug function to look up a specific paper."""
    
    query = f'bibcode:{bibcode}'
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    params = {
        "q": query,
        "fl": "title,author,aff,abstract,bibcode,identifier,keyword,pubdate,arxiv_class,entdate",
        "rows": 1,
    }
    
    print(f"Looking up paper: {bibcode}")
    response = requests.get(ADS_API_URL, headers=headers, params=params)
    response.raise_for_status()
    
    data = response.json()
    papers = data.get("response", {}).get("docs", [])
    
    if not papers:
        print("Paper not found in ADS!")
        return
    
    paper = papers[0]
    print(f"\nTitle: {paper.get('title', ['?'])[0]}")
    print(f"Bibcode: {paper.get('bibcode')}")
    print(f"Pubdate: {paper.get('pubdate')}")
    print(f"Entdate: {paper.get('entdate')}")
    print(f"arXiv ID: {get_arxiv_id(paper)}")
    print(f"arXiv submission: {get_arxiv_submission_month(paper)}")
    print(f"Would pass recency filter: {is_recent_submission(paper)}")
    print(f"arXiv class: {paper.get('arxiv_class', [])}")
    print(f"\nAuthors and affiliations:")
    authors = paper.get("author", [])
    affs = paper.get("aff", [])
    for i, author in enumerate(authors):
        aff = affs[i] if i < len(affs) else "N/A"
        is_uw = is_uw_madison_affiliation(aff)
        marker = " [UW-MADISON]" if is_uw else ""
        print(f"  {author}{marker}")
        print(f"    -> {aff[:100]}{'...' if len(aff) > 100 else ''}")


def main():
    """Main function to run the digest."""
    
    api_key = os.environ.get("ADS_API_KEY")
    if not api_key:
        raise ValueError("ADS_API_KEY environment variable is required")
    
    test_bibcode = os.environ.get("TEST_BIBCODE")
    if test_bibcode:
        test_paper_lookup(api_key, test_bibcode)
        return
    
    days_back = int(os.environ.get("DAYS_BACK", "7"))
    debug = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")
    
    print(f"Querying ADS for UW-Madison astro-ph papers from the last {days_back} days...")
    
    papers = query_ads(api_key, days_back=days_back, debug=debug)
    print(f"Found {len(papers)} papers with UW-Madison affiliations")
    
    for paper in papers:
        title = paper.get("title", ["Untitled"])[0]
        uw_authors = get_uw_authors(paper)
        arxiv_sub = get_arxiv_submission_month(paper)
        sub_str = f" (arXiv: {arxiv_sub[0]}-{arxiv_sub[1]:02d})" if arxiv_sub else ""
        print(f"  - {title[:70]}...{sub_str}")
        print(f"    UW authors: {', '.join(uw_authors)}")
    
    subject, html, text = create_email_content(papers, days_back)
    
    if os.environ.get("SENDER_EMAIL"):
        send_email(subject, html, text)
    else:
        print("\nEmail credentials not configured. Preview:")
        print(text)


if __name__ == "__main__":
    main()
