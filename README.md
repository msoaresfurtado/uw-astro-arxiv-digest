# UW-Madison Astro-ph arXiv Digest

Automated weekly digest of astronomy papers on arXiv with UW-Madison affiliated authors.

Every Friday, this tool queries arXiv for all `astro-ph.*` papers from the past week, filters for those with University of Wisconsin-Madison affiliations, and emails you a formatted digest.

## Features

- Searches all astro-ph subcategories (GA, CO, EP, HE, IM, SR)
- Detects UW-Madison affiliations using multiple patterns
- Nicely formatted HTML email with paper titles, authors, abstracts, and links
- Grouped by arXiv category
- Runs automatically via GitHub Actions (free!)
- Manual trigger option for testing

## Setup Instructions

### 1. Fork or Clone This Repository

Click "Fork" on GitHub, or clone and push to your own repo:

```bash
git clone https://github.com/YOUR_USERNAME/uw-astro-arxiv-digest.git
cd uw-astro-arxiv-digest
git remote set-url origin https://github.com/YOUR_USERNAME/uw-astro-arxiv-digest.git
git push -u origin main
```

### 2. Set Up Email Credentials

You'll need an email account to send from. **Gmail with an App Password is recommended.**

#### For Gmail:

1. Go to your Google Account settings
2. Navigate to Security > 2-Step Verification (enable if not already)
3. Go to Security > App passwords
4. Create a new app password for "Mail"
5. Copy the 16-character password

### 3. Add GitHub Secrets

In your GitHub repository:

1. Go to **Settings** > **Secrets and variables** > **Actions**
2. Add the following secrets:

| Secret Name | Value |
|------------|-------|
| `SENDER_EMAIL` | Your Gmail address (e.g., `yourname@gmail.com`) |
| `SENDER_PASSWORD` | The 16-character app password from step 2 |
| `RECIPIENT_EMAIL` | Where to send the digest (can be the same as sender) |
| `SMTP_SERVER` | `smtp.gmail.com` (for Gmail) |
| `SMTP_PORT` | `587` |

### 4. Enable GitHub Actions

1. Go to the **Actions** tab in your repository
2. Click "I understand my workflows, go ahead and enable them"

### 5. Test It

1. Go to **Actions** > **Weekly Astro-ph Digest**
2. Click **Run workflow**
3. Optionally change "days_back" (e.g., use 30 to test with more papers)
4. Click the green **Run workflow** button
5. Check your email!

## Configuration

### Changing the Schedule

Edit `.github/workflows/weekly_digest.yml` and modify the cron expression:

```yaml
schedule:
  - cron: '0 16 * * 5'  # Current: Fridays at 4pm UTC (10am CT)
```

Cron format: `minute hour day-of-month month day-of-week`

Examples:
- `'0 14 * * 5'` - Fridays at 2pm UTC
- `'0 16 * * 1'` - Mondays at 4pm UTC
- `'0 16 * * 1,5'` - Mondays and Fridays at 4pm UTC

### Modifying Affiliation Detection

Edit `arxiv_digest.py` to add or modify the `UW_PATTERNS` list:

```python
UW_PATTERNS = [
    r"university of wisconsin.*madison",
    r"uw[- ]?madison",
    # Add more patterns here
]
```

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
export SENDER_EMAIL="your@email.com"
export SENDER_PASSWORD="your-app-password"
export RECIPIENT_EMAIL="recipient@email.com"
export SMTP_SERVER="smtp.gmail.com"
export SMTP_PORT="587"

# Run
python arxiv_digest.py
```

Or run without email (just prints to console):

```bash
python arxiv_digest.py
```

## Limitations

- arXiv API doesn't always provide clean affiliation data, so detection relies on patterns in author names, comments, and abstracts
- Some papers may be missed if authors don't include their affiliation
- Rate limited to arXiv API guidelines

## Example Output

The email includes:

- Paper count summary
- Papers grouped by category (astro-ph.SR, astro-ph.EP, etc.)
- For each paper:
  - Title (linked to arXiv)
  - Authors
  - Categories
  - Abstract snippet

## License

MIT License - feel free to adapt for your own institution!
