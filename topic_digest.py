#!/usr/bin/env python3
"""
Weekly Topic-Based Astro-ph Digest

Queries NASA ADS for astronomy papers matching research interests,
with priority sorting for specific authors by ORCID.
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

# Priority ORCIDs - papers by these authors appear at the top
PRIORITY_ORCIDS = [
    "0000-0001-7493-7419",  # Melinda Soares-Furtado
    "0000-0001-7246-5438",  # Andrew
    "0000-0003-2558-3102",  # Enrico
    "0000-0003-0381-1039",  # Ricardo Yarza
]

# Topic keywords to search for
TOPIC_KEYWORDS = [
    "gyrochronology",
    "stellar rotation",
    "exoplanet age",
    "planetary engulfment",
    "young stars",
    "TESS photometry",
    "stellar age",
    "rotational evolution",
    "starspot",
    "chromospheric activity",
    "lithium depletion",
]


def build_query(days_back: int = 7) -> str:
    """Build the ADS query string."""
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    date_range = f"[{start_date.strftime('%Y-%m-%d')} TO {end_date.strftime('%Y-%m-%d')}]"
    
    # Build keyword clauses
    keyword_clauses = " OR ".join([f'abs:"{kw}"' for kw in TOPIC_KEYWORDS])
    
    # Query: (astro-ph.EP OR astro-ph.SR OR keyword matches) AND recent
    query = (
        f'(arxiv_class:"astro-ph.EP" OR arxiv_class:"astro-ph.SR" OR {keyword_clauses}) '
        f'AND entdate:{date_range}'
    )
    
    return query


def query_ads(api_key: str, days_back: int = 7, rows: int = 500) -> list:
    """Query ADS for recent papers matching our interests."""
    
    query = build_query(days_back)
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    params = {
        "q": query,
        "fl": "title,author,aff,abstract,bibcode,identifier,keyword,pubdate,arxiv_class,orcid_pub,orcid_user,orcid_other",
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
    bibcode = paper.get("bibcode", "")
    return f"https://ui.adsabs.harvard.edu/abs/{bibcode}"


def get_arxiv_category(paper: dict) -> str:
    """Get primary arXiv category."""
    classes = paper.get("arxiv_class", [])
    if classes:
        return classes[0]
    return "astro-ph"


def get_paper_orcids(paper: dict) -> set:
    """Get all ORCIDs associated with a paper."""
    orcids = set()
    for field in ["orcid_pub", "orcid_user", "orcid_other"]:
        values = paper.get(field, [])
        if values:
            for orcid in values:
                if orcid and orcid != "-":
                    orcids.add(orcid)
    return orcids


def has_priority_author(paper: dict) -> bool:
    """Check if paper has any priority ORCID authors."""
    paper_orcids = get_paper_orcids(paper)
    return bool(paper_orcids.intersection(PRIORITY_ORCIDS))


def get_priority_authors(paper: dict) -> list:
    """Get names of priority authors on this paper."""
    authors = paper.get("author", [])
    orcid_fields = ["orcid_pub", "orcid_user", "orcid_other"]
    
    priority_authors = []
    
    for field in orcid_fields:
        orcids = paper.get(field, [])
        if orcids:
            for i, orcid in enumerate(orcids):
                if orcid in PRIORITY_ORCIDS and i < len(authors):
                    if authors[i] not in priority_authors:
                        priority_authors.append(authors[i])
    
    return priority_authors


def sort_papers(papers: list) -> list:
    """Sort papers with priority authors first, then by date."""
    priority_papers = []
    other_papers = []
    
    for paper in papers:
        if has_priority_author(paper):
            priority_papers.append(paper)
        else:
            other_papers.append(paper)
    
    return priority_papers + other_papers


def format_paper_html(paper: dict, is_priority: bool = False) -> str:
    """Format a single paper as HTML with full abstract."""
    
    title = paper.get("title", ["Untitled"])[0]
    authors = paper.get("author", [])
    abstract = paper.get("abstract", "No abstract available.")
    url = get_arxiv_url(paper)
    category = get_arxiv_category(paper)
    priority_authors = get_priority_authors(paper)
    
    # Format authors
    if len(authors) > 15:
        author_str = ", ".join(authors[:15]) + f" et al. ({len(authors)} authors)"
    else:
        author_str = ", ".join(authors)
    
    # Priority styling
    if is_priority:
        border_color = "#c5050c"  # UW red for priority
        bg_color = "#fff5f5"
        priority_badge = f"""
            <p style="margin: 0 0 8px 0; color: #c5050c; font-weight: bold; font-size: 14px;">
                ⭐ Priority Author: {", ".join(priority_authors)}
            </p>
        """
    else:
        border_color = "#0479a8"  # Blue for regular
        bg_color = "#f9f9f9"
        priority_badge = ""
    
    return f"""
    <div style="margin-bottom: 25px; padding: 15px; border-left: 4px solid {border_color}; background-color: {bg_color};">
        <h3 style="margin: 0 0 10px 0;">
            <a href="{url}" style="color: #0479a8; text-decoration: none;">{title}</a>
        </h3>
        {priority_badge}
        <p style="margin: 0 0 8px 0; color: #666; font-size: 14px;">
            <strong>Authors:</strong> {author_str}
        </p>
        <p style="margin: 0 0 12px 0; color: #666; font-size: 14px;">
            <strong>Category:</strong> {category}
        </p>
        <p style="margin: 0; font-size: 14px; line-height: 1.6; text-align: justify;">
            {abstract}
        </p>
    </div>
    """


def format_paper_text(paper: dict, is_priority: bool = False) -> str:
    """Format a single paper as plain text with full abstract."""
    
    title = paper.get("title", ["Untitled"])[0]
    authors = paper.get("author", [])
    abstract = paper.get("abstract", "No abstract available.")
    url = get_arxiv_url(paper)
    category = get_arxiv_category(paper)
    priority_authors = get_priority_authors(paper)
    
    # Format authors
    if len(authors) > 15:
        author_str = ", ".join(authors[:15]) + f" et al. ({len(authors)} authors)"
    else:
        author_str = ", ".join(authors)
    
    priority_line = ""
    if is_priority:
        priority_line = f"⭐ PRIORITY AUTHOR: {', '.join(priority_authors)}\n"
    
    return f"""
{title}
{'-' * min(len(title), 80)}
{priority_line}Authors: {author_str}
Category: {category}
Link: {url}

{abstract}

"""


def create_email_content(papers: list, days_back: int) -> tuple:
    """Create HTML and plain text email content."""
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    date_range = f"{start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')}"
    
    # Sort papers (priority authors first)
    sorted_papers = sort_papers(papers)
    
    # Count priority vs regular
    priority_count = sum(1 for p in papers if has_priority_author(p))
    
    if not papers:
        subject = f"Astro-ph Topic Digest: No papers this week"
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #0479a8; border-bottom: 2px solid #0479a8; padding-bottom: 10px;">
                Weekly Astro-ph Topic Digest
            </h1>
            <p style="color: #666;">Papers from {date_range}</p>
            <p>No papers matching your interests were found this week.</p>
        </body>
        </html>
        """
        text = f"Weekly Astro-ph Topic Digest\n{date_range}\n\nNo papers found this week."
        return subject, html, text
    
    subject = f"Astro-ph Topic Digest: {len(papers)} papers ({priority_count} priority)"
    
    # Build HTML content
    html_priority = ""
    html_other = ""
    
    for paper in sorted_papers:
        is_priority = has_priority_author(paper)
        if is_priority:
            html_priority += format_paper_html(paper, is_priority=True)
        else:
            html_other += format_paper_html(paper, is_priority=False)
    
    # Sections
    priority_section = ""
    if priority_count > 0:
        priority_section = f"""
        <h2 style="color: #c5050c; margin-top: 30px; border-bottom: 1px solid #c5050c; padding-bottom: 5px;">
            ⭐ Priority Authors ({priority_count})
        </h2>
        {html_priority}
        """
    
    other_section = ""
    other_count = len(papers) - priority_count
    if other_count > 0:
        other_section = f"""
        <h2 style="color: #333; margin-top: 30px; border-bottom: 1px solid #ddd; padding-bottom: 5px;">
            Other Papers ({other_count})
        </h2>
        {html_other}
        """
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
        <h1 style="color: #0479a8; border-bottom: 2px solid #0479a8; padding-bottom: 10px;">
            Weekly Astro-ph Topic Digest
        </h1>
        <p style="color: #666;">Papers from {date_range}</p>
        <p style="font-size: 16px;">
            <strong>{len(papers)}</strong> papers matching your interests
            ({priority_count} from priority authors)
        </p>
        <p style="font-size: 14px; color: #666;">
            <strong>Topics:</strong> astro-ph.EP, astro-ph.SR, gyrochronology, stellar rotation, 
            exoplanet age, planetary engulfment, young stars, TESS, stellar age, starspots, 
            chromospheric activity, lithium depletion
        </p>
        {priority_section}
        {other_section}
        <hr style="margin-top: 40px; border: none; border-top: 1px solid #ddd;">
        <p style="color: #999; font-size: 12px;">
            This digest is automatically generated using NASA ADS.
        </p>
    </body>
    </html>
    """
    
    # Build plain text content
    text_priority = ""
    text_other = ""
    
    for paper in sorted_papers:
        is_priority = has_priority_author(paper)
        if is_priority:
            text_priority += format_paper_text(paper, is_priority=True)
        else:
            text_other += format_paper_text(paper, is_priority=False)
    
    text = f"""Weekly Astro-ph Topic Digest
{date_range}

{len(papers)} papers matching your interests ({priority_count} from priority authors)

Topics: astro-ph.EP, astro-ph.SR, gyrochronology, stellar rotation, exoplanet age, 
planetary engulfment, young stars, TESS, stellar age, starspots, chromospheric activity, 
lithium depletion
"""
    
    if priority_count > 0:
        text += f"\n{'=' * 60}\nPRIORITY AUTHORS ({priority_count})\n{'=' * 60}\n{text_priority}"
    
    if other_count > 0:
        text += f"\n{'=' * 60}\nOTHER PAPERS ({other_count})\n{'=' * 60}\n{text_other}"
    
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
    
    print(f"Querying ADS for topic-relevant papers from the last {days_back} days...")
    print(f"Priority ORCIDs: {PRIORITY_ORCIDS}")
    
    papers = query_ads(api_key, days_back=days_back)
    print(f"Found {len(papers)} papers")
    
    priority_count = sum(1 for p in papers if has_priority_author(p))
    print(f"  - {priority_count} from priority authors")
    print(f"  - {len(papers) - priority_count} other papers")
    
    subject, html, text = create_email_content(papers, days_back)
    
    if os.environ.get("SENDER_EMAIL"):
        send_email(subject, html, text)
    else:
        print("\nEmail credentials not configured. Email content:")
        print(text)


if __name__ == "__main__":
    main()
