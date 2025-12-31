#!/usr/bin/env python3
"""
UW-Madison Astro-ph arXiv Digest

Queries arXiv for astronomy papers from the past week and filters
for papers with UW-Madison affiliated authors.
"""

import arxiv
import smtplib
import ssl
import os
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from collections import defaultdict


# Configuration
UW_PATTERNS = [
    r"university of wisconsin.*madison",
    r"uw[- ]?madison",
    r"u\.?w\.?[- ]?madison",
    r"madison.*wi.*53706",
    r"475 n\.? charter",  # Astronomy dept address
    r"1150 university ave.*madison",  # Physics dept address
]

ASTRO_CATEGORIES = [
    "astro-ph.GA",  # Galaxies
    "astro-ph.CO",  # Cosmology
    "astro-ph.EP",  # Earth and Planetary
    "astro-ph.HE",  # High Energy
    "astro-ph.IM",  # Instrumentation
    "astro-ph.SR",  # Solar and Stellar
]


def is_uw_madison_affiliated(author_string: str) -> bool:
    """Check if an author affiliation string matches UW-Madison patterns."""
    text = author_string.lower()
    return any(re.search(pattern, text) for pattern in UW_PATTERNS)


def get_recent_astro_papers(days_back: int = 7, max_results: int = 2000) -> list:
    """Fetch recent astro-ph papers from arXiv."""
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    # Build query for all astro-ph categories
    category_query = " OR ".join(f"cat:{cat}" for cat in ASTRO_CATEGORIES)
    
    # Search arXiv
    client = arxiv.Client()
    search = arxiv.Search(
        query=category_query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )
    
    papers = []
    for result in client.results(search):
        # Filter by date
        if result.published.replace(tzinfo=None) < start_date:
            break
        papers.append(result)
    
    return papers


def find_uw_madison_papers(papers: list) -> list:
    """Filter papers for those with UW-Madison affiliated authors."""
    
    uw_papers = []
    
    for paper in papers:
        # Check each author's name (affiliations are sometimes in the name field)
        # arXiv API doesn't always provide clean affiliation data, so we check
        # the paper's comment field and author names
        
        paper_text = " ".join([
            str(paper.comment or ""),
            str(paper.summary or ""),
            " ".join(str(a) for a in paper.authors),
        ])
        
        if is_uw_madison_affiliated(paper_text):
            uw_papers.append(paper)
            continue
            
        # Also check if any author names contain affiliation hints
        for author in paper.authors:
            author_str = str(author)
            if is_uw_madison_affiliated(author_str):
                uw_papers.append(paper)
                break
    
    return uw_papers


def format_paper_html(paper) -> str:
    """Format a single paper as HTML."""
    
    authors = ", ".join(str(a) for a in paper.authors[:10])
    if len(paper.authors) > 10:
        authors += f" et al. ({len(paper.authors)} authors)"
    
    categories = ", ".join(paper.categories)
    
    return f"""
    <div style="margin-bottom: 20px; padding: 15px; border-left: 3px solid #c5050c; background-color: #f9f9f9;">
        <h3 style="margin: 0 0 8px 0;">
            <a href="{paper.entry_id}" style="color: #0479a8; text-decoration: none;">{paper.title}</a>
        </h3>
        <p style="margin: 0 0 8px 0; color: #666; font-size: 14px;">
            <strong>Authors:</strong> {authors}
        </p>
        <p style="margin: 0 0 8px 0; color: #666; font-size: 14px;">
            <strong>Categories:</strong> {categories}
        </p>
        <p style="margin: 0; font-size: 14px; line-height: 1.5;">
            {paper.summary[:500]}{"..." if len(paper.summary) > 500 else ""}
        </p>
    </div>
    """


def format_paper_text(paper) -> str:
    """Format a single paper as plain text."""
    
    authors = ", ".join(str(a) for a in paper.authors[:10])
    if len(paper.authors) > 10:
        authors += f" et al. ({len(paper.authors)} authors)"
    
    return f"""
{paper.title}
{'-' * len(paper.title)}
Authors: {authors}
Categories: {", ".join(paper.categories)}
Link: {paper.entry_id}

{paper.summary[:500]}{"..." if len(paper.summary) > 500 else ""}

"""


def create_email_content(papers: list, days_back: int) -> tuple[str, str]:
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
    
    # Group papers by primary category
    by_category = defaultdict(list)
    for paper in papers:
        primary_cat = paper.primary_category
        by_category[primary_cat].append(paper)
    
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
            This digest is automatically generated. 
            <a href="https://github.com/YOUR_USERNAME/uw-astro-arxiv-digest">View source</a>
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
    
    # Get credentials from environment
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    sender_email = os.environ["SENDER_EMAIL"]
    sender_password = os.environ["SENDER_PASSWORD"]
    recipient_email = os.environ["RECIPIENT_EMAIL"]
    
    # Create message
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = sender_email
    message["To"] = recipient_email
    
    # Attach both plain text and HTML versions
    message.attach(MIMEText(text_content, "plain"))
    message.attach(MIMEText(html_content, "html"))
    
    # Send email
    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls(context=context)
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, message.as_string())
    
    print(f"Email sent successfully to {recipient_email}")


def main():
    """Main function to run the digest."""
    
    days_back = int(os.environ.get("DAYS_BACK", "7"))
    
    print(f"Fetching astro-ph papers from the last {days_back} days...")
    papers = get_recent_astro_papers(days_back=days_back)
    print(f"Found {len(papers)} total astro-ph papers")
    
    print("Filtering for UW-Madison affiliations...")
    uw_papers = find_uw_madison_papers(papers)
    print(f"Found {len(uw_papers)} papers with UW-Madison authors")
    
    # Print to console
    for paper in uw_papers:
        print(f"  - {paper.title[:80]}...")
    
    subject, html, text = create_email_content(uw_papers, days_back)
    
    # Only send email if credentials are configured
    if os.environ.get("SENDER_EMAIL"):
        send_email(subject, html, text)
    else:
        print("\nEmail credentials not configured. Email content:")
        print(text)


if __name__ == "__main__":
    main()
