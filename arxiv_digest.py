#!/usr/bin/env python3
"""
UW-Madison Astro-ph arXiv Digest (ADS Version)

Queries NASA ADS for astronomy papers from the past week with
UW-Madison affiliated authors.
"""

import requests
import smtplib
import ssl
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from collections import defaultdict


# ADS API configuration
ADS_API_URL = "https://api.adsabs.harvard.edu/v1/search/query"


def query_ads(api_key: str, days_back: int = 7, rows: int = 200) -> list:
    """
    Query ADS for recent astro-ph papers with UW-Madison affiliations.
    """
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    date_range = f"[{start_date.strftime('%Y-%m-%d')} TO {end_date.strftime('%Y-%m-%d')}]"
    
    # ADS query:
    # - bibstem:arXiv = arXiv papers
    # - aff:"University of Wisconsin" = affiliation search
    # - entdate:[] = entry date range (when it appeared in ADS)
    # - collection:astronomy = astronomy papers
    query = f'aff:"University of Wisconsin Madison" entdate:{date_range} collection:astronomy bibstem:arXiv'
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    params = {
        "q": query,
        "fl": "title,author,aff,abstract,bibcode,identifier,keyword,pubdate,arxiv_class",
        "rows": rows,
        "sort": "date desc",
    }
    
    response = requests.get(ADS_API_URL, headers=headers, params=params)
    response.raise_for_status()
    
    data = response.json()
    return data.get("response", {}).get("docs", [])


def get_arxiv_id(paper: dict) -> str:
    """Extract arXiv ID from ADS paper record."""
    identifiers = paper.get("identifier", [])
    for ident in identifiers:
        if ident.startswith("arXiv:"):
            return ident.replace("arXiv:", "")
    return None


def get_arxiv_url(paper: dict) -> str:
    """Get arXiv URL for a paper."""
    arxiv_id = get_arxiv_id(paper)
    if arxiv_id:
        return f"https://arxiv.org/abs/{arxiv_id}"
    # Fallback to ADS URL
    bibcode = paper.get("bibcode", "")
    return f"https://ui.adsabs.harvard.edu/abs/{bibcode}"


def get_arxiv_category(paper: dict) -> str:
    """Get primary arXiv category."""
    classes = paper.get("arxiv_class", [])
    if classes:
        return classes[0]
    return "astro-ph"


def format_paper_html(paper: dict) -> str:
    """Format a single paper as HTML."""
    
    title = paper.get("title", ["Untitled"])[0]
    authors = paper.get("author", [])
    abstract = paper.get("abstract", "No abstract available.")
    url = get_arxiv_url(paper)
    category = get_arxiv_category(paper)
    
    # Format authors
    if len(authors) > 10:
        author_str = ", ".join(authors[:10]) + f" et al. ({len(authors)} authors)"
    else:
        author_str = ", ".join(authors)
    
    # Truncate abstract
    if len(abstract) > 500:
        abstract = abstract[:500] + "..."
    
    return f"""
    <div style="margin-bottom: 20px; padding: 15px; border-left: 3px solid #c5050c; background-color: #f9f9f9;">
        <h3 style="margin: 0 0 8px 0;">
            <a href="{url}" style="color: #0479a8; text-decoration: none;">{title}</a>
        </h3>
        <p style="margin: 0 0 8px 0; color: #666; font-size: 14px;">
            <strong>Authors:</strong> {author_str}
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
    
    # Format authors
    if len(authors) > 10:
        author_str = ", ".join(authors[:10]) + f" et al. ({len(authors)} authors)"
    else:
        author_str = ", ".join(authors)
    
    # Truncate abstract
    if len(abstract) > 500:
        abstract = abstract[:500] + "..."
    
    return f"""
{title}
{'-' * min(len(title), 80)}
Authors: {author_str}
Category: {category}
Link: {url}

{abstract}

"""


def create_email_content(papers: list, days_back: int) -> tuple:
    """Create HTML and plain text email content."""
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    date_range = f"{start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')}"
    
    if not papers:
        subject = f"UW-Madison Astro-ph Digest: No papers this week"
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
    
    # Group papers by category
    by_category = defaultdict(list)
    for paper in papers:
        category = get_arxiv_category(paper)
        by_category[category].append(paper)
    
    # Build HTML content
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
        </p>
    </body>
    </html>
    """
    
    # Build plain text content
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


def main():
    """Main function to run the digest."""
    
    api_key = os.environ.get("ADS_API_KEY")
    if not api_key:
        raise ValueError("ADS_API_KEY environment variable is required")
    
    days_back = int(os.environ.get("DAYS_BACK", "7"))
    
    print(f"Querying ADS for UW-Madison astro-ph papers from the last {days_back} days...")
    papers = query_ads(api_key, days_back=days_back)
    print(f"Found {len(papers)} papers with UW-Madison affiliations")
    
    for paper in papers:
        title = paper.get("title", ["Untitled"])[0]
        print(f"  - {title[:80]}...")
    
    subject, html, text = create_email_content(papers, days_back)
    
    if os.environ.get("SENDER_EMAIL"):
        send_email(subject, html, text)
    else:
        print("\nEmail credentials not configured. Email content:")
        print(text)


if __name__ == "__main__":
    main()
