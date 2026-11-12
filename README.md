# Agency Intelligence — Public Demo V2.1

This is a **synthetic-data-only** public showcase adapted from the V1.3.1 project. The original `campaign_intelligence.py` rule engine is unchanged. The `app.py` interface and report generator have been revised for public demonstration; this is **not** a production SaaS service.

## Run on Windows

1. Extract this ZIP and open its folder in VS Code.
2. Open PowerShell terminal and run:

```powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

3. Test all six tabs, switch among three fictional clients, change screening thresholds, and download the PDF.

## Deploy to Streamlit Community Cloud

1. Create a new **public** GitHub repository such as `agency-intelligence-demo`.
2. Push **only** the files in this ZIP. Do not add `.env`, `secrets.toml`, any SQLite database, real customer data or your private V1.3.1 app.
3. Open https://share.streamlit.io and deploy from branch `main`, entrypoint `app.py`. Select Python 3.12 if prompted.
4. Test the public URL in an incognito browser, including all client selectors, controls, and PDF generation.

## Security and accuracy

- No uploads, authentication, database writes, persistent storage or external AI requests.
- All three client datasets are fictional and embedded in source.
- The Intelligence Brief is **deterministic**, not live AI output.
- Agency name and report-preparer inputs are used to generate a PDF in memory; do not enter personal or confidential information.
- Platform-attributed conversion value can overlap; blended reported ROAS is not deduplicated revenue or profit.
- Screening results are hypotheses for review, not guaranteed waste, profitability or automatic budget decisions.

## Files

- `app.py`: Streamlit dashboard, reporting and PDF generator
- `campaign_intelligence.py`: original V1.3.1 rule engine
- `requirements.txt`: dependencies
- `.gitignore`: excludes secrets, local database files and caches
