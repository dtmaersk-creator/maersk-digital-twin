# TwinBridge — Streamlit Deployment Guide

## Step-by-Step Instructions

---

### STEP 1: Install Python (if not installed)

Download Python 3.10 or newer from https://python.org/downloads
- ✅ Check "Add Python to PATH" during installation (Windows)
- Verify: open terminal and type `python --version`

---

### STEP 2: Create a Project Folder

```bash
mkdir twinbridge
cd twinbridge
```

Copy `app.py` and `requirements.txt` into this folder.

---

### STEP 3: Create a Virtual Environment (Recommended)

```bash
# Create environment
python -m venv venv

# Activate it:
# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate
```

---

### STEP 4: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs: streamlit, numpy, pandas, plotly, scipy

---

### STEP 5: Run Locally

```bash
streamlit run app.py
```

Your browser will open automatically at: **http://localhost:8501**

---

### STEP 6: Deploy to Streamlit Cloud (Free)

1. **Push to GitHub:**
   - Create a GitHub account at https://github.com
   - Create a new repository (e.g., `twinbridge`)
   - Upload `app.py` and `requirements.txt`

2. **Deploy on Streamlit Cloud:**
   - Go to https://share.streamlit.io
   - Sign in with your GitHub account
   - Click "New app"
   - Select your repository, branch (main), and file (`app.py`)
   - Click "Deploy!"

3. **Your app will be live at:**
   `https://your-username-twinbridge-app-xxxxx.streamlit.app`

---

### STEP 7 (Optional): Deploy to Heroku

```bash
# Install Heroku CLI, then:
heroku create twinbridge-app
git push heroku main
```

Create a `Procfile`:
```
web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```

---

## File Structure

```
twinbridge/
├── app.py              ← Main application (all code)
├── requirements.txt    ← Python dependencies
└── DEPLOY.md           ← This guide
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` |
| Port already in use | Run `streamlit run app.py --server.port 8502` |
| Slow simulation | Reduce "Monte Carlo Paths" slider in sidebar |
| Blank charts | Refresh browser (F5) |

---

## Performance Notes

- **10,000 paths:** ~2-5 seconds per simulation (default)
- **50,000 paths:** ~15-25 seconds (high accuracy mode)
- **1,000 paths:** <1 second (fast preview mode)
- RAM usage: ~200-400 MB
- No GPU required

---

## Key Features Summary

| Tab | Feature |
|-----|---------|
| 📊 Dashboard | Live MIS gauge, FSS scores, active scenario status |
| 🎯 Scenario Explorer | Select any of 30 scenarios, run Monte Carlo, view distributions |
| ⚡ Strategy Optimizer | Compare all 11 strategies, NPV ranking, risk-return map |
| 📈 Revenue Predictor | Historical backtest + forward fan chart 2020–2028 |
| 🔮 Decision Interface | Input your choice → DT evaluates and recommends |
| 📐 Scoring Metrics | Interactive CNLI, FSS, MIS, SES calculators |
| 🔍 Validation | Q1 2026 live validation, FY2024 backtest |
| 🧪 Stress Testing | Reverse stress test, correlation sensitivity, heat maps |
