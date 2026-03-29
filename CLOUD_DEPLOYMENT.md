# Maersk Digital Twin — Free Cloud Deployment Guide

## Option 1: Streamlit Community Cloud (RECOMMENDED — 100% Free)

### What it gives you
- Your dashboard live at `https://yourname-maersk-twin.streamlit.app`
- Runs 24/7 automatically
- Auto-restarts if it crashes
- No credit card needed
- 1GB RAM, 1 CPU — enough for this project

### Step-by-step deployment

**Step 1: Create a GitHub account (free)**
Go to github.com/signup

**Step 2: Create a new repository**
- Click "New repository"
- Name it: `maersk-digital-twin`
- Set to Private (important — your API key will be here)
- Click "Create repository"

**Step 3: Upload your files**
Upload all 5 files:
- config.py
- data_collection.py
- auto_updater.py
- shock_engine.py
- dashboard.py
- requirements.txt

**Step 4: Create requirements.txt with these exact contents:**
```
finnhub-python==2.4.20
apscheduler==3.10.4
requests==2.31.0
pandas==2.2.2
numpy==1.26.4
plotly==5.22.0
streamlit==1.35.0
```

**Step 5: Handle the API key securely (CRITICAL)**
Do NOT put your real API key in config.py on GitHub.
Instead, change config.py line to:
```python
import os
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")
```

**Step 6: Deploy on Streamlit Cloud**
- Go to share.streamlit.io
- Sign in with GitHub
- Click "New app"
- Select your repository: `maersk-digital-twin`
- Main file path: `dashboard.py`
- Click "Advanced settings"
- Under "Secrets", add:
  ```
  FINNHUB_API_KEY = "your_actual_key_here"
  ```
- Click "Deploy"

**Step 7: Done!**
Your dashboard is live in 2-3 minutes.

---

## Option 2: Render.com (Free — better for persistent database)

Streamlit Cloud resets the SQLite database every time it restarts.
If you want your 30-day market history to persist, use Render.

### Step-by-step

**Step 1:** Create account at render.com (free)

**Step 2:** Add a file called `render.yaml` to your GitHub repo:
```yaml
services:
  - type: web
    name: maersk-digital-twin
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: streamlit run dashboard.py --server.port $PORT --server.address 0.0.0.0
    envVars:
      - key: FINNHUB_API_KEY
        sync: false
```

**Step 3:** Connect your GitHub repo on Render dashboard
**Step 4:** Add FINNHUB_API_KEY as an environment variable
**Step 5:** Deploy

Your dashboard will be at: `https://maersk-digital-twin.onrender.com`

**Note:** Free tier on Render spins down after 15 minutes of inactivity.
To keep it alive 24/7, add this to dashboard.py:
```python
import threading, requests, time

def keep_alive():
    while True:
        try:
            requests.get("https://maersk-digital-twin.onrender.com")
        except:
            pass
        time.sleep(600)  # ping every 10 minutes

threading.Thread(target=keep_alive, daemon=True).start()
```

---

## Option 3: GitHub Codespaces (Free 60 hours/month)

For development and testing only (not 24/7):
- Open your GitHub repo
- Click "Code" → "Codespaces" → "New codespace"
- In the terminal: `streamlit run dashboard.py`
- Click the link to view in browser

---

## Option 4: Hugging Face Spaces (Free — good for demos)

- Create account at huggingface.co
- New Space → Streamlit
- Upload files
- Add FINNHUB_API_KEY as a secret
- Free, always-on, good for sharing with supervisors

---

## Fixing the SQLite problem for cloud

The main issue with cloud deployment: SQLite is a local file.
Every restart wipes your price history.

**Free solution: Supabase (free PostgreSQL database)**

1. Create free account at supabase.com
2. Create new project
3. Get connection string from Settings → Database
4. Install: `pip install psycopg2-binary`
5. Replace SQLite connection in data_collection.py:

```python
import psycopg2
import os

def get_db_conn():
    # Use environment variable for security
    return psycopg2.connect(os.environ.get("DATABASE_URL"))

# Replace: conn = sqlite3.connect(DB_PATH)
# With:    conn = get_db_conn()
```

Add to your cloud environment variables:
```
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

This gives you a persistent database that survives restarts — free up to 500MB.

---

## Optimisation Suggestions for the Digital Twin

### Code Optimisations

**1. Caching with st.cache_data (already possible today)**
Add this decorator to expensive functions to avoid rerunning them on every page interaction:
```python
@st.cache_data(ttl=300)  # cache for 5 minutes
def get_expensive_computation(scenario_key):
    engine = MonteCarloEngine()
    return engine.run_single(scenario_key, "do_nothing")
```

**2. Vectorised EBITDA calculation**
The current EBITDA loop can be 40% faster with pre-computed arrays:
```python
# Instead of computing per-quarter in a loop, pre-compute decay array:
decay_array = np.array([0.5*(1+np.cos(np.pi*q/duration)) if q<duration else 0
                        for q in range(duration+2)])
# Then multiply entire arrays at once
```

**3. Parallel scenario runs**
Run all scenarios simultaneously instead of sequentially:
```python
from concurrent.futures import ProcessPoolExecutor
with ProcessPoolExecutor(max_workers=4) as executor:
    futures = {key: executor.submit(engine.run_single, key, "do_nothing")
               for key in SHOCK_SCENARIOS}
    results = {key: f.result() for key, f in futures.items()}
```

**4. Pre-computed scenario cache**
Run all scenarios at startup and cache results. Only rerun when baseline changes:
```python
import hashlib, pickle

def get_or_compute_results(baseline):
    state_hash = hashlib.md5(json.dumps(baseline, sort_keys=True).encode()).hexdigest()
    cache_file = f"results/cache_{state_hash}.pkl"
    if os.path.exists(cache_file):
        return pickle.load(open(cache_file, "rb"))
    engine  = MonteCarloEngine(baseline)
    results = engine.run_all()
    pickle.dump(results, open(cache_file, "wb"))
    return results
```

### Model Optimisations

**5. Correlated shock draws (biggest academic improvement)**
Currently vol, rate, and fuel shocks are drawn independently.
In reality they are correlated — fuel spikes tend to happen when demand is low.
Add correlation matrix:
```python
# Correlation matrix for demand collapse scenario:
# vol ↔ rate: 0.75 (both fall together in recessions)
# vol ↔ fuel: -0.40 (lower demand = lower oil price)
# rate ↔ fuel: -0.35
corr_matrix = np.array([[1.00, 0.75, -0.40],
                        [0.75, 1.00, -0.35],
                        [-0.40,-0.35, 1.00]])

# Use Cholesky decomposition to generate correlated samples:
L = np.linalg.cholesky(corr_matrix)
uncorrelated = rng.standard_normal((3, n))
correlated   = L @ uncorrelated  # now vol, rate, fuel are correlated
```

**6. Time-varying volatility (GARCH)**
Currently volatility is constant. In reality it clusters — high vol follows high vol.
Add GARCH(1,1) to the stock predictor for more realistic price paths.

**7. Scenario correlation scoring**
The market intelligence signal weights are currently static.
Make them dynamic — update weights based on how well each signal predicted past scenarios.

**8. AIS vessel tracking integration**
Add real vessel position data from MarineTraffic API (free tier: 100 requests/day).
This lets the twin know exactly how many Maersk vessels are currently rerouting
around Africa due to Hormuz/Red Sea — a direct operational input.

### Data Optimisations

**9. Freightos FBX via CSV download**
Freightos provides free weekly FBX CSV downloads.
Add a weekly job to download and parse the CSV instead of scraping the website.

**10. Maersk IR page scraper**
Maersk publishes quarterly results on investor.maersk.com.
Add a scraper that detects when new results are published and automatically
triggers an auto_updater cycle.

**11. News sentiment signal**
Add a news sentiment score to the market intelligence engine:
```python
# Free: NewsAPI.org (100 requests/day free tier)
import requests

def get_shipping_sentiment():
    url = "https://newsapi.org/v2/everything"
    params = {"q": "Maersk OR shipping OR freight",
              "sortBy": "publishedAt", "pageSize": 10,
              "apiKey": os.environ.get("NEWS_API_KEY")}
    articles = requests.get(url, params=params).json().get("articles", [])
    # Simple keyword scoring: crisis/collapse/fall = negative
    # recovery/growth/demand = positive
    neg_words = ["crisis","collapse","fall","disruption","closure","strike"]
    pos_words = ["recovery","growth","demand","increase","record","strong"]
    score = 0
    for a in articles:
        text = (a.get("title","") + " " + a.get("description","")).lower()
        score -= sum(1 for w in neg_words if w in text)
        score += sum(1 for w in pos_words if w in text)
    return score  # negative = bearish, positive = bullish
```
