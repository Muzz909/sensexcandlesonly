import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, time
import pytz
import time as time_module
from candle_engine import (
    fetch_sensex_data,
    detect_patterns,
    get_overall_verdict,
    TIMEFRAMES,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Sensex Candle Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

IST = pytz.timezone("Asia/Kolkata")

# ── Helpers ───────────────────────────────────────────────────────────────────
def is_market_open() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5:          # Saturday / Sunday
        return False
    market_open  = time(9, 15)
    market_close = time(15, 30)
    return market_open <= now.time() <= market_close

def now_ist_str() -> str:
    return datetime.now(IST).strftime("%d %b %Y  %H:%M:%S IST")

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ─── global ─────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* remove top padding */
.block-container { padding-top: 1rem !important; }

/* ─── verdict badge ──────────────────────────────────────── */
.verdict-card {
    border-radius: 16px;
    padding: 1.2rem 1.6rem;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 1rem;
}
.verdict-bull  { background: linear-gradient(135deg,#0d4f23,#145e2b); color:#7fffa8; }
.verdict-bear  { background: linear-gradient(135deg,#4f0d0d,#6b1515); color:#ffaaaa; }
.verdict-neut  { background: linear-gradient(135deg,#1e1e2e,#2a2a3e); color:#aab2cc; }
.verdict-icon  { font-size: 2.4rem; line-height:1; }
.verdict-text  { flex: 1; }
.verdict-title { font-size: 1.25rem; font-weight: 600; margin-bottom: .2rem; }
.verdict-sub   { font-size: .85rem; opacity: .85; }

/* ─── confluence dots ────────────────────────────────────── */
.conf-row { display: flex; gap: 6px; margin-top: .5rem; }
.cdot {
    width: 12px; height: 12px; border-radius: 50%;
    background: rgba(255,255,255,.15);
}
.cdot.bull { background: #22c55e; }
.cdot.bear { background: #ef4444; }

/* ─── pattern chip ───────────────────────────────────────── */
.chip-row  { display: flex; flex-wrap: wrap; gap: 6px; margin: .4rem 0; }
.chip {
    font-size: .75rem; font-weight: 500;
    padding: 3px 10px; border-radius: 20px;
    border: 1px solid rgba(255,255,255,.12);
}
.chip-bull { background:#0a3d1f; color:#86efac; border-color:#166534; }
.chip-bear { background:#3d0a0a; color:#fca5a5; border-color:#7f1d1d; }
.chip-neut { background:#1e293b; color:#94a3b8; border-color:#334155; }

/* ─── TF badge ───────────────────────────────────────────── */
.tf-header {
    font-size:.75rem; font-weight:600; letter-spacing:.08em;
    text-transform:uppercase; color:#64748b; margin-bottom:.2rem;
}
.tf-signal {
    font-size:.8rem; font-weight:600;
    padding: 2px 10px; border-radius: 20px;
    display: inline-block; margin-top: 4px;
}
.sig-bull { background:#0a3d1f; color:#86efac; }
.sig-bear { background:#3d0a0a; color:#fca5a5; }
.sig-neut { background:#1e293b; color:#94a3b8; }

/* ─── status pill ────────────────────────────────────────── */
.status-pill {
    display:inline-flex; align-items:center; gap:6px;
    font-size:.8rem; font-weight:500;
    padding: 4px 12px; border-radius: 20px;
}
.pill-live   { background:#0a3d1f; color:#86efac; }
.pill-closed { background:#1e293b; color:#94a3b8; }
.pill-dot    { width:7px; height:7px; border-radius:50%; }
.dot-live    { background:#22c55e; animation: pulse 1.4s infinite; }
.dot-closed  { background:#64748b; }
@keyframes pulse {
  0%,100% { opacity:1; } 50% { opacity:.4; }
}

/* ─── instruction box ────────────────────────────────────── */
.instr-box {
    background:#0f172a; border:1px solid #1e293b;
    border-radius:12px; padding:1rem 1.2rem;
    font-size:.82rem; color:#94a3b8; line-height:1.7;
}
.instr-box h4 { color:#cbd5e1; font-size:.9rem; margin-bottom:.4rem; }
.instr-box b  { color:#e2e8f0; }

/* ─── mobile ─────────────────────────────────────────────── */
@media (max-width: 640px) {
    .verdict-title { font-size: 1rem; }
    .block-container { padding: .5rem !important; }
}
</style>
""", unsafe_allow_html=True)

# ── Session state init ────────────────────────────────────────────────────────
if "auto_refresh"    not in st.session_state: st.session_state.auto_refresh = True
if "last_refresh"    not in st.session_state: st.session_state.last_refresh = None
if "data_cache"      not in st.session_state: st.session_state.data_cache = {}
if "fetch_errors"    not in st.session_state: st.session_state.fetch_errors = {}
if "active_tf_tab"   not in st.session_state: st.session_state.active_tf_tab = "1m"

# ── Build candle chart ────────────────────────────────────────────────────────
def build_candle_chart(df: pd.DataFrame, tf_label: str, signal: str) -> go.Figure:
    if df is None or df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available", x=0.5, y=0.5,
                           xref="paper", yref="paper", showarrow=False,
                           font=dict(size=14, color="#64748b"))
        fig.update_layout(paper_bgcolor="#0f172a", plot_bgcolor="#0f172a",
                          height=340, margin=dict(l=4,r=4,t=32,b=4))
        return fig

    color_up   = "#22c55e"
    color_down = "#ef4444"
    wick_up    = "#16a34a"
    wick_down  = "#dc2626"

    colors = [color_up if row.Close >= row.Open else color_down
              for _, row in df.iterrows()]
    wick_colors = [wick_up if row.Close >= row.Open else wick_down
                   for _, row in df.iterrows()]

    fig = go.Figure()

    # Wicks
    for i, (_, row) in enumerate(df.iterrows()):
        fig.add_shape(type="line",
            x0=i, x1=i, y0=row.Low, y1=row.High,
            line=dict(color=wick_colors[i], width=1.5))

    # Bodies
    for i, (_, row) in enumerate(df.iterrows()):
        o, c = row.Open, row.Close
        fig.add_shape(type="rect",
            x0=i - 0.35, x1=i + 0.35,
            y0=min(o, c), y1=max(o, c) if abs(o - c) > 0.01 else o + 0.5,
            fillcolor=colors[i], line=dict(color=colors[i], width=0),
            opacity=0.92)

    # Volume bars (mini)
    if "Volume" in df.columns:
        vol = df["Volume"].fillna(0)
        maxv = vol.max() if vol.max() > 0 else 1
        price_range = df.High.max() - df.Low.min()
        vol_scale = price_range * 0.18
        y_base = df.Low.min() - price_range * 0.05
        for i, (_, row) in enumerate(df.iterrows()):
            bar_h = (row.Volume / maxv) * vol_scale
            fig.add_shape(type="rect",
                x0=i - 0.35, x1=i + 0.35,
                y0=y_base, y1=y_base + bar_h,
                fillcolor=colors[i], opacity=0.25,
                line=dict(width=0))

    # X labels
    tick_every = max(1, len(df) // 8)
    tick_vals  = list(range(0, len(df), tick_every))
    tick_text  = []
    for tv in tick_vals:
        ts = df.index[tv]
        if hasattr(ts, "strftime"):
            tick_text.append(ts.strftime("%H:%M"))
        else:
            tick_text.append(str(tv))

    # Layout
    signal_color = {"bull": "#22c55e", "bear": "#ef4444", "neut": "#64748b"}.get(signal, "#64748b")
    fig.update_layout(
        height=340,
        paper_bgcolor="#0a0f1e",
        plot_bgcolor="#0a0f1e",
        margin=dict(l=6, r=6, t=36, b=6),
        title=dict(
            text=f"<b>{tf_label}</b>",
            font=dict(size=13, color=signal_color),
            x=0.01, xanchor="left", y=0.97,
        ),
        xaxis=dict(
            tickvals=tick_vals, ticktext=tick_text,
            tickfont=dict(size=10, color="#64748b"),
            gridcolor="#1e293b", gridwidth=0.5,
            zeroline=False, showline=False,
            rangeslider=dict(visible=False),
        ),
        yaxis=dict(
            tickfont=dict(size=10, color="#64748b"),
            gridcolor="#1e293b", gridwidth=0.5,
            zeroline=False, showline=False,
            side="right",
        ),
        dragmode="pan",
        showlegend=False,
        hoverlabel=dict(bgcolor="#1e293b", font_size=12,
                        font_family="Inter", bordercolor="#334155"),
        newshape=dict(line_color="#94a3b8"),
    )

    # Hover
    fig.add_trace(go.Scatter(
        x=list(range(len(df))),
        y=df.Close.tolist(),
        mode="markers",
        marker=dict(size=0, opacity=0),
        customdata=np.stack([df.Open, df.High, df.Low, df.Close,
                             df.Volume if "Volume" in df.columns
                             else np.zeros(len(df))], axis=-1),
        hovertemplate=(
            "<b>%{x}</b><br>"
            "O: %{customdata[0]:.1f}  H: %{customdata[1]:.1f}<br>"
            "L: %{customdata[2]:.1f}  C: %{customdata[3]:.1f}<br>"
            "Vol: %{customdata[4]:,.0f}<extra></extra>"
        ),
        showlegend=False,
    ))

    fig.update_xaxes(range=[-0.5, len(df) - 0.5])
    return fig

# ── Render verdict ────────────────────────────────────────────────────────────
def render_verdict(verdict: dict):
    v = verdict["direction"]
    css = {"bull": "verdict-bull", "bear": "verdict-bear", "neut": "verdict-neut"}[v]
    icon = {"bull": "↑", "bear": "↓", "neut": "—"}[v]
    dot_css = {"bull": "bull", "bear": "bear", "neut": ""}[v]
    conf = verdict["confluence"]
    dots = "".join(
        f'<div class="cdot {dot_css if i < conf else ""}"></div>'
        for i in range(4)
    )
    st.markdown(f"""
    <div class="verdict-card {css}">
      <div class="verdict-icon">{icon}</div>
      <div class="verdict-text">
        <div class="verdict-title">{verdict['title']}</div>
        <div class="verdict-sub">{verdict['subtitle']}</div>
        <div class="conf-row">{dots}</div>
      </div>
    </div>""", unsafe_allow_html=True)

# ── Render TF signal row ──────────────────────────────────────────────────────
def render_tf_signals(tf_results: dict):
    cols = st.columns(4)
    for i, (tf, info) in enumerate(tf_results.items()):
        with cols[i % 4]:
            sig = info.get("signal", "neut")
            css = {"bull": "sig-bull", "bear": "sig-bear", "neut": "sig-neut"}[sig]
            label = {"bull": "Bullish", "bear": "Bearish", "neut": "Neutral"}[sig]
            patterns = info.get("patterns", [])
            chips = "".join(
                f'<span class="chip chip-{sig}">{p}</span>'
                for p in patterns
            )
            st.markdown(f"""
            <div style="background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:.7rem .9rem;margin-bottom:.5rem;">
              <div class="tf-header">{tf}</div>
              <span class="tf-signal {css}">{label}</span>
              <div class="chip-row" style="margin-top:.4rem;">{chips}</div>
            </div>""", unsafe_allow_html=True)

# ── Instructions ──────────────────────────────────────────────────────────────
def render_instructions():
    with st.expander("📖 How to use this chart — tap to read", expanded=False):
        st.markdown("""
<div class="instr-box">
<h4>📱 On Mobile</h4>
<b>Pan:</b> Single finger drag left/right to scroll the chart timeline.<br>
<b>Zoom in:</b> Pinch inward with two fingers on the chart area.<br>
<b>Zoom out:</b> Pinch outward with two fingers.<br>
<b>Reset view:</b> Double-tap on the chart to reset to full view.<br>
<b>Candle detail:</b> Tap any candle to see OHLC values in a tooltip.<br><br>
<h4>🖥️ On Desktop</h4>
<b>Pan:</b> Click and drag to move the chart.<br>
<b>Zoom:</b> Scroll wheel up/down, or click+drag on the X/Y axis.<br>
<b>Box zoom:</b> Click the zoom icon (top-right) then drag a box.<br>
<b>Reset:</b> Double-click anywhere on the chart, or click the home icon.<br>
<b>Candle detail:</b> Hover over any candle for OHLC values.<br><br>
<h4>📊 Reading the Signals</h4>
<b>Confluence dots (●●●●):</b> Each dot = 1 timeframe agreeing with the verdict. 4/4 = highest conviction.<br>
<b>Green candle:</b> Close > Open — buyers in control.<br>
<b>Red candle:</b> Close < Open — sellers in control.<br>
<b>Wick length:</b> Long upper wick = rejection at high (bearish). Long lower wick = rejection at low (bullish).<br>
<b>Candle body size:</b> Large body = strong momentum. Small body = indecision.<br><br>
<h4>⏱️ Timeframe Tabs</h4>
Switch between <b>1m / 3m / 5m / 15m</b> tabs to zoom into each timeframe's candle view. Each tab auto-fits the last N candles for that timeframe so you see the clearest picture.
</div>""", unsafe_allow_html=True)

# ── Main refresh logic ────────────────────────────────────────────────────────
def do_refresh():
    with st.spinner("Fetching latest candle data…"):
        data = {}
        errors = {}
        for tf in TIMEFRAMES:
            df, err = fetch_sensex_data(tf["interval"], tf["period"])
            if df is not None and not df.empty:
                data[tf["label"]] = {
                    "df": df,
                    "result": detect_patterns(df, tf["label"]),
                }
            else:
                errors[tf["label"]] = err or "Unknown error"
        st.session_state.data_cache   = data
        st.session_state.fetch_errors = errors
        st.session_state.last_refresh = now_ist_str()

# ── App layout ────────────────────────────────────────────────────────────────
def main():
    market_open = is_market_open()

    # ── Header ─────────────────────────────────────────────────────────────
    col_title, col_status, col_toggle, col_refresh = st.columns([3, 2, 2, 1.4])

    with col_title:
        st.markdown("### 📊 Sensex Candle Analyzer")

    with col_status:
        if market_open:
            st.markdown('<div style="padding-top:.45rem"><span class="status-pill pill-live">'
                        '<span class="pill-dot dot-live"></span>Market Open</span></div>',
                        unsafe_allow_html=True)
        else:
            st.markdown('<div style="padding-top:.45rem"><span class="status-pill pill-closed">'
                        '<span class="pill-dot dot-closed"></span>Market Closed</span></div>',
                        unsafe_allow_html=True)

    with col_toggle:
        auto = st.toggle("Auto refresh (30s)", value=st.session_state.auto_refresh,
                         disabled=not market_open,
                         help="Only active during market hours 9:15–15:30 IST")
        st.session_state.auto_refresh = auto and market_open

    with col_refresh:
        if st.button("⟳ Refresh", use_container_width=True):
            do_refresh()

    # Last refresh timestamp
    if st.session_state.last_refresh:
        st.caption(f"Last updated: {st.session_state.last_refresh}")
    else:
        st.caption("Press Refresh or wait for auto-load.")

    st.markdown("---")

    # ── Initial load ────────────────────────────────────────────────────────
    if not st.session_state.data_cache:
        do_refresh()

    data = st.session_state.data_cache
    if not data:
        st.warning("Could not fetch Sensex data. Check your internet connection or try again.")
        return

    # ── Build tf_results for signals ─────────────────────────────────────
    tf_results = {}
    for tf in TIMEFRAMES:
        lbl = tf["label"]
        if lbl in data:
            tf_results[lbl] = data[lbl]["result"]

    # ── Verdict ─────────────────────────────────────────────────────────────
    verdict = get_overall_verdict(tf_results)
    render_verdict(verdict)

    # ── TF signal row ────────────────────────────────────────────────────────
    render_tf_signals(tf_results)

    st.markdown("---")

    # ── Candle chart tabs ────────────────────────────────────────────────────
    tab_labels = [tf["label"] for tf in TIMEFRAMES]
    tabs = st.tabs(tab_labels)

    for tab, tf in zip(tabs, TIMEFRAMES):
        lbl = tf["label"]
        with tab:
            if lbl not in data:
                reason = st.session_state.fetch_errors.get(lbl)
                st.info(f"No data for {lbl}" + (f" — {reason}" if reason else ""))
                continue
            df     = data[lbl]["df"]
            result = data[lbl]["result"]
            sig    = result.get("signal", "neut")

            # Zoom: last N candles for this TF
            zoom_n = tf.get("zoom_candles", 30)
            df_zoom = df.tail(zoom_n)

            fig = build_candle_chart(df_zoom, lbl, sig)
            st.plotly_chart(fig, use_container_width=True,
                            config=dict(
                                scrollZoom=True,
                                displayModeBar=True,
                                modeBarButtonsToRemove=["autoScale2d","lasso2d","select2d"],
                                displaylogo=False,
                                responsive=True,
                            ))

            # Pattern detail for this TF
            patterns = result.get("patterns", [])
            analysis = result.get("analysis", "")
            action   = result.get("action", "")

            c1, c2 = st.columns([3, 2])
            with c1:
                if patterns:
                    chips = "".join(
                        f'<span class="chip chip-{sig}">{p}</span>'
                        for p in patterns
                    )
                    st.markdown(f'<div class="chip-row">{chips}</div>',
                                unsafe_allow_html=True)
                if analysis:
                    st.markdown(f"<span style='font-size:.88rem;color:#94a3b8'>{analysis}</span>",
                                unsafe_allow_html=True)
            with c2:
                if action:
                    action_color = {"bull": "#22c55e", "bear": "#ef4444"}.get(sig, "#94a3b8")
                    bg_color     = {"bull": "#0a3d1f", "bear": "#3d0a0a"}.get(sig, "#1e293b")
                    st.markdown(
                        f'<div style="background:{bg_color};border-radius:10px;padding:.7rem 1rem;'
                        f'text-align:center;color:{action_color};font-weight:600;font-size:.95rem;">'
                        f'{action}</div>',
                        unsafe_allow_html=True,
                    )

    # ── Instructions ─────────────────────────────────────────────────────────
    st.markdown("---")
    render_instructions()

    # ── Auto-refresh ──────────────────────────────────────────────────────────
    if st.session_state.auto_refresh and market_open:
        time_module.sleep(30)
        do_refresh()
        st.rerun()

if __name__ == "__main__":
    main()
