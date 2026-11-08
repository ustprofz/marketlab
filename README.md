# Market Lab

A finance, data analytics, and statistics website for high school students and teachers.

**Creator:** Jiang (Will) Zhang ([LinkedIn](https://www.linkedin.com/in/jiang-will-zhang/))  
Assistant Professor of Finance, Opus College of Business, University of St. Thomas

University of St. Thomas · Opus College of Business · The Opus Way of Teaching · VIBE Lab (Ventures in Business Engineering)

For educational use only; not financial, investment, or legal advice.

## What is included

- Company/ticker search, starter companies, price charts, six time windows, a raw data table, and CSV export.
- Actual Yahoo data retrieved with Python/yfinance, with optional 60-second polling and explicit market-observation/retrieval times.
- Close versus Adjusted Close selection; price changes, mean returns, sample standard deviation, and a price-only $100 illustration.
- Indexed comparison, return correlation, a return histogram, and a return scatterplot.
- Clearly labelled, reproducible simulated practice data; a local CSV import; student investigation notes and share links.
- Three classroom activities, a printable teacher guide, a downloadable activity sheet, glossary, and a suggested assessment rubric.

**GitHub Pages cannot run Python.** The website has two pieces: a static front end in `docs/` and a small Python web service in `backend/`. GitHub Pages works immediately in practice mode. Deploy the separate Python service and set its URL to enable Yahoo data for everyone.

## 1. Publish the website with GitHub Pages

1. Unzip this package on your computer. Create a new public GitHub repository, for example `market-lab`.
2. In that repository, select **Add file → Upload files**. Upload the extracted contents so `docs/`, `backend/`, `render.yaml`, and this README are at the repository's top level. Do not upload only the ZIP or add an extra enclosing folder.
3. Commit the files to `main`.
4. Open **Settings → Pages**. Under **Build and deployment**, choose **Deploy from a branch**, select branch **main** and folder **/docs**, then **Save**.
5. Wait for the Pages deployment to succeed. Your URL will usually be `https://YOUR-USERNAME.github.io/market-lab/`. Open the published link shown in Settings → Pages.

The front end uses relative asset paths, so project repositories and a `USERNAME.github.io` repository both work. No Node build or GitHub Actions workflow is needed. `docs/.nojekyll` disables Jekyll processing.

At this stage you can use all practice activities and local CSV exploration. The site labels these sources explicitly.

## 2. Enable actual Yahoo data with a Python service

The included `render.yaml` is an optional Render Blueprint. A manual Render deployment is also straightforward. Hosting plans and menus can change; consult [Render's FastAPI guide](https://render.com/docs/deploy-fastapi) and [free-service limitations](https://render.com/docs/free).

### Option A: Render Blueprint

1. Sign in to Render and choose **New → Blueprint**.
2. Connect the GitHub repository containing this project. Review the proposed `opus-market-lab-api` web service before creating it.
3. The supplied blueprint requests a free Python web service. Free services may sleep when idle and are best suited to a classroom prototype. If a free plan is unavailable, choose a suitable plan yourself before proceeding.
4. When deployment completes, copy its public service URL, for example `https://opus-market-lab-api-xxxx.onrender.com`.

### Option B: Manual Render web service

1. Choose **New → Web Service**, connect the repository, and select the Python runtime. Keep the repository root directory blank.
2. Use build command `pip install -r backend/requirements.txt`.
3. Use start command `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.
4. Set `PYTHON_VERSION` to `3.12.14`; choose a hosting plan and deploy. Set health-check path to `/api/health` if that setting is available.

### Connect the public website

1. Visit `https://YOUR-SERVICE.onrender.com/api/health`. It should return JSON with `status: "ok"`. This confirms the web service is up; it does not guarantee Yahoo availability.
2. In GitHub, edit **`docs/config.js`**. Replace its empty `apiBase` with your service URL:

   ```js
   window.MARKET_LAB_CONFIG = {
     apiBase: "https://YOUR-SERVICE.onrender.com",
     refreshMs: 60000
   };
   ```

   Use the base service URL, without `/api` or a trailing endpoint.
3. Commit the edit. Wait for the GitHub Pages deployment, reload the public website, and choose **Yahoo data** if it is not already selected.
4. Select AAPL and a time window. Confirm the banner says Yahoo Finance via yfinance and inspect the market observation timestamp. Download a CSV and verify its source fields.

The website's **Data connection** dialog can test a service URL without editing GitHub, but that setting only applies to the current browser. Editing `docs/config.js` makes it the default for every visitor.

No Yahoo login or API key is needed by this implementation. Never put passwords or private credentials in `docs/` or any public repository.

### CORS and classroom operation

The backend allows credential-free GET requests from any origin by default. To restrict browser origins, set Render environment variable `ALLOWED_ORIGINS=https://YOUR-USERNAME.github.io`. For multiple sites, use comma-separated origins. An origin has no repository path, so do not append `/market-lab/`. CORS is a browser policy, not authentication or a guarantee against other clients.

The service uses in-memory caching, bounded upstream concurrency, a short error cooldown, and a basic per-IP rate limit (120 requests/minute). Several students can share one school IP, so adjust that limit for larger deployments. Each worker has its own cache and limits; this first version is intended as a small educational prototype, not an exchange-grade data service.

Free hosts can sleep after inactivity. The first request may take longer or time out; retry after the service starts. Yahoo may also throttle or refuse a request. The website displays an error and offers practice mode rather than labelling synthetic data as actual data. For a scheduled lesson, open the site before class and keep a downloaded CSV available.

## What “up to date” means here

- This is **not a guaranteed real-time exchange feed**. Yahoo may supply delayed, incomplete, cached, or unavailable data. Availability differs by instrument and market.
- Auto-refresh requests every 60 seconds while the page is visible. The server caches intraday windows for 60 seconds and daily windows for five minutes.
- The banner distinguishes market observation time, server retrieval time, and cache age. A quote may be newer than a chart bar, so each has its own label. Outside market hours, an earlier session is expected.
- Intraday charts request regular trading hours. The fixed mappings are: 1D → 1-minute bars; 5D → 15-minute bars; 1M/6M/1Y/5Y → daily bars. Provider-specific history limits still apply.
- CSVs retain raw Close, Adj Close, OHLC, volume, dividends/splits when supplied, timestamps, source, retrieval time, and source mode. A blank value is missing, not zero.

## Data-use rights

yfinance is an independent open-source library, not affiliated with Yahoo. Its project documentation describes research/educational use and notes that the Yahoo Finance API is intended for personal use. Permission to use the Python package is not permission to redistribute market data. **Before operating a public Yahoo-backed website, review the applicable Yahoo terms and data rights for your intended audience and use.** Practice mode can demonstrate the platform without redistributing provider prices; the adapter can be replaced with a suitably licensed provider if needed.

Primary documentation:

- [GitHub Pages publishing](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site)
- [yfinance project and data-use notice](https://github.com/ranaroussi/yfinance)
- [yfinance history API](https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html)
- [Render FastAPI deployment](https://render.com/docs/deploy-fastapi)
- [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/)

## Calculation and source conventions

- Returns are `selected_price[t] / selected_price[t-1] - 1`. Analytics use positive finite selected prices. The interface shows exclusions; the raw export retains available rows and missing fields.
- The backend explicitly requests `auto_adjust=False`. Close and Adj Close remain separate; a missing adjusted value is never filled with Close.
- The quoted price is a provider market quote when accompanied by a valid observation timestamp, otherwise the last returned Close with that fallback labelled.
- Mean return is arithmetic. Sample SD uses `n - 1` and is not annualized. Matched-step periods may span gaps.
- Comparison intersects timestamps before calculating returns. Correlation is Pearson's r for matched returns, not price levels; it is undefined for a constant series. Scatterplots show up to 300 evenly selected points for readability, while statistics use all matched pairs.
- Indexed prices start at 100 on the first common observation. Comparisons may involve different currencies; no FX conversion is performed.
- The $100 illustration always uses historical Close price change and omits dividends, fees, and taxes. It is not a backtest, forecast, or complete investment return.
- Practice series are deterministic synthetic data ending in 2025, use an illustrative weekday calendar, and are marked SIMULATED throughout the interface and export. They do not reproduce actual company prices.
- Local CSV import stays in the browser, requires Date/Timestamp and Close, rejects duplicate timestamps, and accepts up to 6,000 rows and 2 MB. It is always labelled user-imported. Pairwise comparison of imported files is not included in this version.
- Student notes remain in the current page until downloaded or lost on navigation. Share links contain settings, not notes, backend URLs, or frozen market data. This project does not include accounts, portfolios, order placement, or student tracking.

## Run locally or test

Install Python 3.12 and run these commands from the extracted project directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

On Windows, activate with `.venv\Scripts\activate` instead. Open `http://127.0.0.1:8000`. The backend also serves the front end and automatically connects it to its own API. To test GitHub-style static practice mode, serve only `docs/`, for example with `python3 -m http.server 8001 --directory docs` from a second terminal.

Tests (Node 18+ for the pure JavaScript checks; Python dependencies above for backend tests):

```sh
node tests/analytics.mjs
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

The tests cover known calculations, matched return correlation, missing values, CSV/provenance, deterministic practice data, input validation, cache timing, provider failure, read-only CORS, and static configuration. Backend tests use labelled fixtures and do not require Yahoo availability. Actual Yahoo history retrieval was separately checked during development; that is not a promise of future provider availability. The website has not been deployed to your GitHub or hosting account.

`package.json` supplies an optional managed-preview development command for the authoring environment; it is not needed by GitHub Pages or Render.

## Files to edit later

| Change | File |
| --- | --- |
| Connect live data for all visitors | `docs/config.js` |
| Creator, brands, landing text, classroom activities | `docs/index.html` |
| Printable lesson guide | `docs/teacher-guide.html` |
| Colors and layout | `docs/assets/site.css` |
| App interactions and chart drawing | `docs/assets/app.js` |
| Calculations and CSV handling | `docs/assets/math.js` |
| Simulated data | `docs/assets/practice.js` |
| Yahoo retrieval and API | `backend/main.py` |
| Deployment | `render.yaml`, `backend/requirements.txt` |

After editing a file, commit it to the publishing branch. Static changes appear after the next successful Pages deployment; backend changes redeploy through the connected host. Use a hard refresh if an older asset remains cached.

See `ROADMAP.md` for classroom engagement ideas and sensible next features.
