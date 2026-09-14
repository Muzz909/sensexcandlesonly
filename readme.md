# 📊 Sensex Candle Analyzer

A real-time candlestick pattern analyzer for the BSE Sensex — built with Streamlit.  
No indicators. Pure candle reading across 1m, 3m, 5m, and 15m timeframes.

---

## Features

- **Live OHLCV candles** from Yahoo Finance (BSESN) — no API key needed
- **Auto-refresh every 30 seconds** — only when market is open (9:15–15:30 IST, Mon–Fri)
- **Auto-refresh toggle** — turn it on/off from the UI anytime
- **Manual force refresh** button always available
- **Multi-timeframe analysis**: 1m · 3m · 5m · 15m — each with zoomed candle chart
- **Confluence verdict**: weighted signal across all 4 timeframes
- **Pattern detection**: Engulfing, Doji, Hammer, Shooting Star, Pin Bar, Marubozu, Morning/Evening Star, 3 White Soldiers, 3 Black Crows, and more
- **Mobile-friendly** with touch pan/pinch-zoom on charts
- **Dark, clean UI** optimized for trading

---

## Quickstart (local)

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/sensex-candle-analyzer.git
cd sensex-candle-analyzer

# 2. Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
streamlit run app.py
```

Open your browser at **http://localhost:8501**

---

## Deploy to Streamlit Cloud (free)

1. Push this folder to a **public GitHub repo**
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
3. Click **New app** → select your repo → set `app.py` as the main file
4. Click **Deploy** — done. You get a public URL in ~2 minutes.

No secrets or API keys needed — yfinance is free and open.

---

## Project structure

```
sensex-candle-analyzer/
├── app.py              # Streamlit UI — layout, charts, auto-refresh
├── candle_engine.py    # Data fetching + candlestick pattern detection
├── requirements.txt    # Python dependencies
└── README.md
```

---

## How the signals work

### Timeframe weights
| TF  | Weight |
|-----|--------|
| 1m  | 1      |
| 3m  | 2      |
| 5m  | 3      |
| 15m | 4      |

The overall verdict is a weighted vote. If 70%+ of the score is bullish → **Strong Call signal**.  
If 70%+ is bearish → **Strong Put signal**. Otherwise → **Wait**.

### Confluence dots
Four dots below the verdict = one per timeframe. Filled dots = timeframes that agree with the verdict.  
**4/4 = highest conviction. 2/4 or less = don't trade.**

### Pattern logic (brief)

| Pattern | Signal |
|---|---|
| Bullish engulfing | Bull |
| Bearish engulfing | Bear |
| Doji / Spinning top | Neutral |
| Hammer (with bullish body) | Bull |
| Hanging Man | Bear |
| Shooting Star | Bear |
| Bullish Pin Bar | Bull |
| Bearish Pin Bar | Bear |
| Bullish Marubozu | Bull |
| Bearish Marubozu | Bear |
| Morning Star (3-candle) | Bull |
| Evening Star (3-candle) | Bear |
| 3 White Soldiers | Bull |
| 3 Black Crows | Bear |

---

## Important disclaimer

This tool is for **informational and educational purposes only**.  
It is **not financial advice**. Options trading involves significant risk.  
Always do your own analysis and use proper risk management.

---

## Tips for Sensex options trading with this tool

- **Never trade on 1m signal alone** — always check 5m and 15m alignment
- **4/4 confluence = high confidence entry**, 3/4 = reasonable, 2/4 or less = skip
- **Entry timing**: Wait for the candle to fully close before acting on a signal
- **Use this as confirmation**, not as the sole decision-making tool
- **Morning (9:15–10:30) and afternoon (14:00–15:00) sessions** tend to have cleaner candle patterns
- **Avoid trading 15 mins before and after major events** (RBI policy, budget, US Fed)
