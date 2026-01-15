#!/usr/bin/env python3
"""
Daily Topic-Based Astro-ph Digest

Queries NASA ADS for astronomy papers matching research interests,
with priority sorting for specific authors by ORCID.
"""

import requests
import smtplib
import ssl
import os
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta


# ADS API configuration
ADS_API_URL = "https://api.adsabs.harvard.edu/v1/search/query"

# Priority ORCIDs - papers by these authors appear at the top
PRIORITY_ORCIDS = [
    "0000-0001-7493-7419",  # Melinda Soares-Furtado
    "0009-0001-1360-8547", #Julia Sheffler
]

# Topic keywords to search for (also used for relevance scoring)
TOPIC_KEYWORDS = [
    "gyrochronology",
    "stellar rotation",
    "exoplanet age",
    "planetary engulfment",
    "free-floating planet",
    "planet engulfment",
    "engulfment",
    "young stars",
    "TESS photometry",
    "stellar age",
    "rotational evolution",
    "starspot",
    "chromospheric activity",
    "lithium depletion",
    "lithium abundance",
    "lithium",
    "stellar pollution",
    "chemical abundance",
    "convective zone",
    "convective envelope",
]

# High-value keywords (extra relevance points)
HIGH_VALUE_KEYWORDS = [
    "gyrochronology",
    "planetary engulfment",
    "planet engulfment",
    "engulfment",
    "lithium depletion",
    "lithium abundance",
    "stellar age",
    "young planet",
    "stellar pollution",
]


# Silly encouraging welcome messages
WELCOME_MESSAGES = [
    "🏃‍♀️ Step by step, paper by paper. You're literally ascending while reading about the cosmos. Iconic.",
    "⭐ Here you are, staying up-to-date on your literature review. Nice work!",
    "🚀 Cardio + astro-ph = an insane form of multitasking. You're a rockstar.",
    "🌟 Fun fact: reading papers on a stepmill burns mass, just like a star. You're basically a main sequence queen.",
    "💪 Other people scroll Instagram at the gym. You read about stellar evolution. We are not the same.",
    "🔭 Your heart rate is up, your knowledge is expanding. The universe is proud of you.",
    "✨ Every step you take is one step closer to tenure and one step up the stepmill. Synergy!",
    "🌙 The Moon's escape velocity is 2.38 km/s. Your's must be higher because NOTHING can stop you.",
    "⚡ You're generating more power than a brown dwarf right now. Keep climbing!",
    "🍕 You could be eating pizza in bed. But no. You're on the stepmill. Reading about LITHIUM DEPLETION.",
    "🌠 Somewhere, a committee is meeting without you. But you? You're ASCENDING the stepmill.",
    "💫 Hot take: the stepmill is just a really boring rocket. You're training for space.",
    "🏔️ Sir Edmund Hillary climbed Everest. You're climbing a stepmill in Wisconsin. Both required questionable judgment and excellent cardiovascular fitness.",
    "🔥 Your VO2 max called. It said 'thank you for the gains and the gyrochronology.'",
    "🎢 This is the only acceptable way to read about rotational evolution.",
    "🎪 Welcome to the circus: you're a tenure-track professor reading arXiv on a stepmill at 6am. The clown makeup is optional.",
    "🔭 In the time it takes you to finish this stepmill session, light from the Sun will have traveled about 2.4 AU. You will have traveled about 40 floors. Both are valid units of progress.",
    "💪 Sisyphus pushed a boulder up a hill for eternity, but did he do it while reading astro-ph?",
    "☕ You could be drinking hot cocoa and relaxing. Instead you're sweating and reading about chromospheric activity. Your choices are questionable.",
    "🧗 The stepmill has no summit. The literature has no end. Your dedication has no explanation. We climb anyway.",
    "🎰 Every paper is a slot machine. Will it be relevant? Will it scoop you? Will it cite you? Spin the wheel. Read the abstract. Feel something.",
    "🚿 You will forget 80% of these abstracts by the time you shower. This is not a personal failing. This is the human condition. We read anyway.",
    "🔬 Studies show that reading papers on a stepmill increases comprehension by 0%. But it does make you feel like a high-achieving weirdo, and honestly that's worth something.",
    "🌙 Tonight's forecast: 85% chance of you lying awake thinking about that one weird result in paper #3. But that's future you's problem."
]

# Bottom treasures (rewards for reading to the end)
BOTTOM_TREASURES = [
    ("🗓️ CALENDAR INVITE", "Event: Read arXiv digest on stepmill. When: Tomorrow. And the next day. Recurring: Forever. Attendees: Just you. Location: The void (the gym). RSVP: You already did."),
    ("🪐 COSMIC PERSPECTIVE", "In 5 billion years, the Sun will expand and engulf the Earth. None of these papers will matter. But you read them anyway. That's either beautiful or stupid. Probably both."),
    ("🏁 FINISH LINE", "You crossed it. There's no medal. There's no ceremony. There's just the quiet satisfaction of knowing you read an entire digest while climbing to nowhere."),
    ("🗺️ YOU ARE HERE", "Congratulations. You've reached the bottom of an email, the peak of a fake mountain, and probably the limit of your quads' patience. Plant your flag. You earned it."),
    ("🎉 YOU MADE IT!", "Congratulations! You scrolled through the whole digest. Your dedication to the literature is matched only by your cardiovascular endurance. Gold star for you: ⭐"),
    ("🔮 FORTUNE COOKIE", "Your astronomy fortune: 'A paper you cite today will cite you back within 5 years.' Lucky numbers: 42, 3.14, 6.67×10⁻¹¹"),
    ("🦖 PALEO-ASTRONOMY FACT", "65 million years ago, a T-Rex could have looked up and seen different constellations. The Big Dipper didn't exist yet. Anyway, great job finishing this email!"),
    ("🎵 STUCK IN YOUR HEAD", "🎵 We didn't start the fire / It was always burning since the stellar core was churning 🎵 You're welcome. And congrats on finishing!"),
    ("🏆 ACHIEVEMENT UNLOCKED", "'+1 Literature Awareness' - You have gained 50 XP in the skill 'Keeping Up With The Field.' Only 9,950 more XP until you feel caught up!"),
    ("🌶️ HOT TAKE ZONE", "Controversial opinion: log(g) should be called 'surface gravity vibe check.' Thank you for coming to my TED talk at the bottom of this email."),
    ("🎲 D&D STATS UPDATE", "Your literature review stats this week: STR +1 (from stepmill), INT +3 (from papers), WIS +2 (knowing to combine them). Roll for initiative on your next paper."),
    ("🐛 BUG REPORT", "ERROR 418: You have reached the bottom of the email. This is not a bug, it's a feature. Status: Proud of you."),
    ("📊 FAKE STATISTICS", "Studies show that 94% of astronomers who read digests on stepmills publish 3x more papers. (Source: I made it up. But you DID finish this email.)"),
    ("🎬 MOVIE PITCH", "STEPMILL ASTRONOMER: One woman. One machine. 47 abstracts. Coming this summer. Starring you. You're the hero of this story."),
    ("🧪 EXPERIMENT RESULTS", "Hypothesis: You would read this whole email. Method: Sent email. Results: You're reading this. Conclusion: Hypothesis confirmed. P-value: very significant."),
    ("🌈 WHOLESOME MOMENT", "Hey. Genuinely. It's hard to keep up with the literature while doing everything else. The fact that you're trying means a lot. You're doing great. 💜"),
    ("🎰 SLOT MACHINE", "🍒🍒🍒 JACKPOT! You won: the knowledge from all these abstracts, leg strength, and this nice message. Cash out anytime (close email)."),
    ("📧 META MOMENT: You're reading a silly message at the bottom of an automated email you built yourself. You engineered your own dopamine hit. That's either genius or a cry for help. Probably both."),
    ("🛸 ALIEN MESSAGE", "GREETINGS HUMAN. WE HAVE OBSERVED YOUR DEDICATION TO BOTH PHYSICAL AND INTELLECTUAL PURSUITS. YOU WILL BE SPARED DURING THE INVASION. jk great job reading!"),
]


def build_query(days_back: int = 7) -> str:
    """Build the ADS query string."""
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    date_range = f"[{start_date.strftime('%Y-%m-%d')} TO {end_date.strftime('%Y-%m-%d')}]"
    
    # Build keyword clauses
    keyword_clauses = " OR ".join([f'abs:"{kw}"' for kw in TOPIC_KEYWORDS])
    
    EXCLUDE_CATEGORIES = [
        "hep-ph", "hep-th", "hep-lat", "gr-qc", "quant-ph", "cs.SY",
        "cond-mat.mtrl-sci", "cond-mat.mes-hall", "cond-mat.soft", 
        "cond-mat.stat-mech", "cond-mat.str-el", "cond-mat.supr-con",
        "astro-ph.GA", "astro-ph.CO", "astro-ph.HE", "physics.app-ph",
        "physics.flu-dyn", "physics.ins-det", "physics.plasm-ph", "math.QA",
        
    ]    
    
    exclusions = " ".join([f'-arxiv_class:"{cat}"' for cat in EXCLUDE_CATEGORIES])
    query = (
        f'(arxiv_class:"astro-ph.EP" OR arxiv_class:"astro-ph.SR" OR {keyword_clauses}) '
        f'AND entdate:{date_range} '
        f'{exclusions}'
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


def calculate_relevance_score(paper: dict) -> int:
    """
    Calculate a relevance score for the paper.
    Higher = more relevant to your interests.
    """
    score = 0
    
    title = paper.get("title", [""])[0].lower()
    abstract = paper.get("abstract", "").lower()
    text = title + " " + abstract
    
    # Priority author: big bonus
    if has_priority_author(paper):
        score += 50
    
    # High-value keyword matches (in title = extra points)
    for kw in HIGH_VALUE_KEYWORDS:
        if kw.lower() in title:
            score += 15
        elif kw.lower() in abstract:
            score += 8
    
    # Regular keyword matches
    for kw in TOPIC_KEYWORDS:
        if kw.lower() not in [k.lower() for k in HIGH_VALUE_KEYWORDS]:
            if kw.lower() in title:
                score += 5
            elif kw.lower() in abstract:
                score += 2
    
    return score


def get_relevance_tier(score: int) -> tuple:
    """
    Get relevance tier based on score.
    Returns (emoji, color, label, bg_color)
    """
    if score >= 50:
        return ("🔴", "#c5050c", "VERY RELEVANT", "#fff0f0")
    elif score >= 20:
        return ("🟠", "#e67e00", "RELEVANT", "#fff8f0")
    elif score >= 8:
        return ("🟡", "#d4a017", "SOMEWHAT RELEVANT", "#fffef0")
    else:
        return ("⚪", "#888888", "GENERAL", "#f9f9f9")


def sort_papers(papers: list) -> list:
    """Sort papers by relevance score (highest first)."""
    scored = [(p, calculate_relevance_score(p)) for p in papers]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [p for p, s in scored]


def format_paper_html(paper: dict) -> str:
    """Format a single paper as HTML with truncated abstract."""
    
    title = paper.get("title", ["Untitled"])[0]
    authors = paper.get("author", [])
    abstract = paper.get("abstract", "No abstract available.")
    url = get_arxiv_url(paper)
    category = get_arxiv_category(paper)
    priority_authors = get_priority_authors(paper)
    
    score = calculate_relevance_score(paper)
    emoji, color, label, bg_color = get_relevance_tier(score)
    
    # Format authors - first 3 only
    if len(authors) > 3:
        author_str = ", ".join(authors[:3]) + f" + {len(authors) - 3} more"
    else:
        author_str = ", ".join(authors)
    
    # Truncate abstract
    if len(abstract) > 150:
        truncated_abstract = abstract[:150].rsplit(' ', 1)[0] + "..."
    else:
        truncated_abstract = abstract
    
    # Priority author badge
    priority_badge = ""
    if priority_authors:
        priority_badge = f"""
            <p style="margin: 0 0 8px 0; color: #c5050c; font-weight: bold; font-size: 14px;">
                ⭐ {", ".join(priority_authors)}
            </p>
        """
    
    return f"""
    <div style="margin-bottom: 25px; padding: 15px; border-left: 6px solid {color}; background-color: {bg_color};">
        <div style="margin-bottom: 10px;">
            <span style="font-size: 24px; margin-right: 10px;">{emoji}</span>
            <span style="background-color: {color}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold;">
                {label}
            </span>
            <span style="color: #888; font-size: 12px; margin-left: 10px;">{category}</span>
        </div>
        <h3 style="margin: 0 0 8px 0;">
            <a href="{url}" style="color: #0479a8; text-decoration: none;">{title}</a>
        </h3>
        {priority_badge}
        <p style="margin: 0 0 10px 0; color: #666; font-size: 14px;">
            {author_str}
        </p>
        <p style="margin: 0; font-size: 14px; line-height: 1.5; color: #444;">
            {truncated_abstract} <a href="{url}" style="color: #0479a8; text-decoration: none;">[read more]</a>
        </p>
    </div>
    """
def format_paper_text(paper: dict) -> str:
    """Format a single paper as plain text with full abstract."""
    
    title = paper.get("title", ["Untitled"])[0]
    authors = paper.get("author", [])
    abstract = paper.get("abstract", "No abstract available.")
    url = get_arxiv_url(paper)
    category = get_arxiv_category(paper)
    priority_authors = get_priority_authors(paper)
    
    score = calculate_relevance_score(paper)
    emoji, _, label, _ = get_relevance_tier(score)
    
    # Format authors
    if len(authors) > 15:
        author_str = ", ".join(authors[:15]) + f" et al. ({len(authors)} authors)"
    else:
        author_str = ", ".join(authors)
    
    priority_line = ""
    if priority_authors:
        priority_line = f"⭐ PRIORITY AUTHOR: {', '.join(priority_authors)}\n"
    
    return f"""
{emoji} [{label}]
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
    
    # Sort papers by relevance
    sorted_papers = sort_papers(papers)
    
    # Count by tier
    tier_counts = {"🔴": 0, "🟠": 0, "🟡": 0, "⚪": 0}
    for paper in papers:
        score = calculate_relevance_score(paper)
        emoji, _, _, _ = get_relevance_tier(score)
        tier_counts[emoji] += 1
    
    # Random welcome message
    welcome = random.choice(WELCOME_MESSAGES)
    
    # Random bottom treasure
    treasure_title, treasure_content = random.choice(BOTTOM_TREASURES)
    
    if not papers:
        subject = f"Astro-ph Topic Digest: No papers today"
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #0479a8; border-bottom: 2px solid #0479a8; padding-bottom: 10px;">
                Daily Astro-ph Topic Digest
            </h1>
            <div style="background-color: #f0f8ff; padding: 15px; border-radius: 10px; margin-bottom: 20px; font-size: 16px;">
                {welcome}
            </div>
            <p style="color: #666;">Papers from {date_range}</p>
            <p>No papers matching your interests were found today. Rest day for your brain! 🧘</p>
        </body>
        </html>
        """
        text = f"Daily Astro-ph Topic Digest\n{date_range}\n\n{welcome}\n\nNo papers found today."
        return subject, html, text
    
    subject = f"Astro-ph Digest: {tier_counts['🔴']}🔴 {tier_counts['🟠']}🟠 {tier_counts['🟡']}🟡 ({len(papers)} total)"
    
    # Build HTML content
    html_papers = ""
    for paper in sorted_papers:
        html_papers += format_paper_html(paper)
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
        <h1 style="color: #0479a8; border-bottom: 2px solid #0479a8; padding-bottom: 10px;">
            Daily Astro-ph Topic Digest
        </h1>
        
        <div style="background-color: #f0f8ff; padding: 15px; border-radius: 10px; margin-bottom: 20px; font-size: 16px; line-height: 1.5;">
            {welcome}
        </div>
        
        <p style="color: #666;">Papers from {date_range}</p>
        
        <div style="background-color: #f5f5f5; padding: 15px; border-radius: 10px; margin-bottom: 25px;">
            <p style="margin: 0; font-size: 18px;">
                <strong>{len(papers)} papers</strong> today:
                <span style="margin-left: 15px;">🔴 {tier_counts['🔴']} must-read</span>
                <span style="margin-left: 10px;">🟠 {tier_counts['🟠']} relevant</span>
                <span style="margin-left: 10px;">🟡 {tier_counts['🟡']} interesting</span>
                <span style="margin-left: 10px;">⚪ {tier_counts['⚪']} general</span>
            </p>
        </div>
        
        {html_papers}
        
        <div style="margin-top: 50px; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; color: white; text-align: center;">
            <h2 style="margin: 0 0 10px 0;">{treasure_title}</h2>
            <p style="margin: 0; font-size: 14px; line-height: 1.6;">
                {treasure_content}
            </p>
        </div>
        
        <hr style="margin-top: 40px; border: none; border-top: 1px solid #ddd;">
        <p style="color: #999; font-size: 12px;">
            This digest is automatically generated using NASA ADS. Keep climbing! 🏔️
        </p>
    </body>
    </html>
    """
    
    # Build plain text content
    text_papers = ""
    for paper in sorted_papers:
        text_papers += format_paper_text(paper)
    
    text = f"""Daily Astro-ph Topic Digest
{date_range}

{welcome}

{len(papers)} papers today:
  🔴 {tier_counts['🔴']} must-read
  🟠 {tier_counts['🟠']} relevant  
  🟡 {tier_counts['🟡']} interesting
  ⚪ {tier_counts['⚪']} general

{'=' * 60}
{text_papers}

{'=' * 60}
{treasure_title}
{'=' * 60}
{treasure_content}
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
    
    days_back = int(os.environ.get("DAYS_BACK", "1"))
    
    print(f"Querying ADS for topic-relevant papers from the last {days_back} days...")
    print(f"Priority ORCIDs: {PRIORITY_ORCIDS}")
    
    papers = query_ads(api_key, days_back=days_back)
    print(f"Found {len(papers)} papers")
    
    # Count by tier
    tier_counts = {"🔴": 0, "🟠": 0, "🟡": 0, "⚪": 0}
    for paper in papers:
        score = calculate_relevance_score(paper)
        emoji, _, _, _ = get_relevance_tier(score)
        tier_counts[emoji] += 1
    
    print(f"  🔴 {tier_counts['🔴']} must-read")
    print(f"  🟠 {tier_counts['🟠']} relevant")
    print(f"  🟡 {tier_counts['🟡']} interesting")
    print(f"  ⚪ {tier_counts['⚪']} general")
    
    subject, html, text = create_email_content(papers, days_back)
    
    if os.environ.get("SENDER_EMAIL"):
        send_email(subject, html, text)
    else:
        print("\nEmail credentials not configured. Email content:")
        print(text)


if __name__ == "__main__":
    main()
