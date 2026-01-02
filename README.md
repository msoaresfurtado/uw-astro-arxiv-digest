# Astro-ph arXiv Digests

Automated email digests of astronomy papers from arXiv/NASA ADS. This repo contains two independent digests:

1. **Weekly UW-Madison Digest** - All astro-ph papers with UW-Madison affiliated authors (Fridays)
2. **Daily Topic Digest** - Papers matching your research interests, with relevance scoring (Daily)

Both run automatically via GitHub Actions (free!) and share the same secrets.

## Features

### Weekly UW-Madison Digest (`arxiv_digest.py`)
- Searches NASA ADS for UW-Madison affiliated authors
- Grouped by arXiv category
- HTML formatted email with abstracts and links

### Daily Topic Digest (`topic_digest.py`)
- Searches all astro-ph.EP and astro-ph.SR papers plus keyword matches
- **Relevance scoring** with color-coded badges:
  - 🔴 **VERY RELEVANT** - Priority authors or multiple keyword matches
  - 🟠 **RELEVANT** - High-value keyword matches
  - 🟡 **SOMEWHAT RELEVANT** - Other keyword matches
  - ⚪ **GENERAL** - Category match only
- **Priority authors** - Papers by specified ORCIDs appear first
- **Full abstracts** (not truncated)
- **Silly welcome messages** - Rotating astronomy/gym encouragement
- **Hidden treasure** - Fun reward at the bottom for reading the whole email
- Subject line shows `3🔴 5🟠 12🟡 (47 total)` for quick inbox triage

## Setup Instructions

### 1. Fork or Clone This Repository

Click "Fork" on GitHub, or clone and push to your own repo:

```bash
git clone https://github.com/YOUR_USERNAME/uw-astro-arxiv-digest.git
cd uw-astro-arxiv-digest
git remote set-url origin https://github.com/YOUR_USERNAME/uw-astro-arxiv-digest.git
git push -u origin main
```

### 2. Get a NASA ADS API Key

1. Go to [ui.adsabs.harvard.edu](https://ui.adsabs.harvard.edu)
2. Create an account (or sign in with ORCID/Google)
3. Click your name > Settings > API Token
4. Generate and copy your token

### 3. Set Up Email Credentials

You'll need an email account to send from. Gmail with an App Password is recommended.

#### For Gmail:

1. Go to your Google Account settings
2. Navigate to Security > 2-Step Verification (enable if not already)
3. Go to Security > App passwords
4. Create a new app password for "Mail"
5. Copy the 16-character password

### 4. Add GitHub Secrets

In your GitHub repository:

1. Go to **Settings** > **Secrets and variables** > **Actions**
2. Add the following secrets:

| Secret Name | Value |
|------------|-------|
| `ADS_API_KEY` | Your NASA ADS API token |
| `SENDER_EMAIL` | Your Gmail address (e.g., `yourname@gmail.com`) |
| `SENDER_PASSWORD` | The 16-character app password |
| `RECIPIENT_EMAIL` | Where to send the digest (can be the same as sender) |
| `SMTP_SERVER` | `smtp.gmail.com` (for Gmail) |
| `SMTP_PORT` | `587` |

### 5. Enable GitHub Actions

1. Go to the **Actions** tab in your repository
2. Click "I understand my workflows, go ahead and enable them"

### 6. Test It

1. Go to **Actions**
2. Select either **Weekly Astro-ph Digest** or **Daily Topic Digest**
3. Click **Run workflow**
4. Optionally change "days_back" (e.g., use 7 to test with more papers)
5. Click the green **Run workflow** button
6. Check your email!

## Configuration

### Changing the Schedules

Edit the workflow files in `.github/workflows/`:

**Weekly UW Digest** (`weekly_digest.yml`):
```yaml
schedule:
  - cron: '0 16 * * 5'  # Fridays at 4pm UTC (10am CT)
```

**Daily Topic Digest** (`topic_digest.yml`):
```yaml
schedule:
  - cron: '0 16 * * *'  # Daily at 4pm UTC (10am CT)
```

Cron format: `minute hour day-of-month month day-of-week`

### Customizing the Topic Digest

Edit `topic_digest.py` to customize:

**Priority ORCIDs** - Papers by these authors appear first with a star badge:
```python
PRIORITY_ORCIDS = [
    "0000-0001-7493-7419",  # Your ORCID
    "0000-0001-7246-5438",  # Collaborator
    # Add more...
]
```

**Topic Keywords** - Used for searching and relevance scoring:
```python
TOPIC_KEYWORDS = [
    "gyrochronology",
    "stellar rotation",
    "exoplanet age",
    # Add your research interests...
]
```

**High-Value Keywords** - Extra relevance points for these:
```python
HIGH_VALUE_KEYWORDS = [
    "gyrochronology",
    "planetary engulfment",
    # Your most important topics...
]
```

### Modifying the UW Affiliation Search

Edit `arxiv_digest.py` and change the query:

```python
query = f'aff:"Department of Astronomy" aff:"Wisconsin" entdate:{date_range}'
```

To include Physics:
```python
query = f'(aff:"Department of Astronomy" OR aff:"Department of Physics") aff:"Wisconsin" entdate:{date_range}'
```

See [ADS search syntax](https://ui.adsabs.harvard.edu/help/search/search-syntax) for more options.

### Using a Different Email Provider

Update the `SMTP_SERVER` and `SMTP_PORT` secrets:

| Provider | Server | Port |
|----------|--------|------|
| Gmail | smtp.gmail.com | 587 |
| Outlook | smtp.office365.com | 587 |
| Yahoo | smtp.mail.yahoo.com | 587 |

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export ADS_API_KEY="your-ads-api-key"
export SENDER_EMAIL="your@email.com"
export SENDER_PASSWORD="your-app-password"
export RECIPIENT_EMAIL="recipient@email.com"
export SMTP_SERVER="smtp.gmail.com"
export SMTP_PORT="587"
export DAYS_BACK="7"  # Optional, defaults to 7 for weekly, 1 for daily

# Run either digest
python arxiv_digest.py      # UW-Madison digest
python topic_digest.py      # Topic digest
```

Or run without email (prints to console):

```bash
export ADS_API_KEY="your-ads-api-key"
python topic_digest.py
```

## File Structure

```
├── .github/workflows/
│   ├── weekly_digest.yml    # UW-Madison digest schedule
│   └── topic_digest.yml     # Topic digest schedule
├── arxiv_digest.py          # UW-Madison digest script
├── topic_digest.py          # Topic digest script
├── requirements.txt         # Python dependencies
└── README.md
```

## License

MIT License - feel free to adapt for your own institution or interests!
