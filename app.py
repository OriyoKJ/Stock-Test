import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import plotly.graph_objects as go

st.set_page_config(page_title="Stock Academy Pro", layout="wide")
st.title("📈 Stock Academy Pro – Sentiment + Live Insights")

st.warning("Educational only. Not financial advice. Markets are unpredictable.")

# VADER Setup
analyzer = SentimentIntensityAnalyzer()

tabs = st.tabs(["Live Analysis + Sentiment", "Watchlist & Alerts", "High Probability Ideas", "Risk Tools"])

# ---------- Tab 1: Live Analysis + Sentiment ----------
with tabs[0]:
    ticker = st.text_input("Ticker", "AAPL").upper()
    if st.button("Run Full Analysis"):
        try:
            data = yf.download(ticker, period="5d", interval="5m", progress=False)

            # yfinance can return MultiIndex columns depending on version; flatten defensively
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            if data.empty:
                st.error(f"No price data returned for '{ticker}'. Check the symbol, or try again "
                         f"later (markets closed / rate limited).")
            else:
                current_price = data['Close'].iloc[-1]
                st.metric("Current Price", f"${current_price:.2f}")

                # VADER News Sentiment
                stock = yf.Ticker(ticker)
                news = stock.news or []
                sentiments = []
                for item in news[:8]:
                    # yfinance's news payload shape has changed across versions
                    # (flat "title" vs nested under "content") — handle both
                    title = item.get('title') or item.get('content', {}).get('title', '')
                    if not title:
                        continue
                    score = analyzer.polarity_scores(title)
                    compound = score['compound']
                    sentiment_label = (
                        "Strongly Positive" if compound > 0.5 else
                        "Positive" if compound > 0.1 else
                        "Neutral" if compound > -0.1 else
                        "Negative"
                    )
                    sentiments.append({"Title": title[:80], "Sentiment": sentiment_label, "Score": round(compound, 3)})

                sent_df = pd.DataFrame(sentiments)
                avg_sentiment = sent_df["Score"].mean() if not sent_df.empty else 0

                st.subheader("VADER Sentiment Analysis")
                if sent_df.empty:
                    st.info("No recent news headlines available for this ticker.")
                else:
                    st.dataframe(sent_df, use_container_width=True)

                st.metric(
                    "Overall News Sentiment",
                    f"{avg_sentiment:.2f}",
                    "Positive" if avg_sentiment > 0.1 else "Negative" if avg_sentiment < -0.1 else "Neutral"
                )

                # Probability scale (heuristic)
                prob_positive = max(30, min(75, 50 + int(avg_sentiment * 30)))
                st.metric("Estimated Probability of Positive Short-term Move", f"{prob_positive}%")
        except Exception as e:
            st.error(f"Couldn't complete analysis for '{ticker}': {e}")

# ---------- Tab 2: Watchlist & Alerts (previously empty — no content existed for this tab) ----------
with tabs[1]:
    st.subheader("Watchlist & Alerts")
    watch_input = st.text_input("Tickers (comma-separated)", "AAPL, MSFT, NVDA")
    alert_pct = st.slider("Alert me if daily move exceeds (%)", 1, 15, 5)
    watch_list = [t.strip().upper() for t in watch_input.split(",") if t.strip()]

    if st.button("Check Watchlist"):
        rows = []
        for t in watch_list:
            try:
                hist = yf.Ticker(t).history(period="2d")
                if len(hist) < 2:
                    continue
                prev_close = hist['Close'].iloc[-2]
                last = hist['Close'].iloc[-1]
                pct_change = (last - prev_close) / prev_close * 100
                rows.append({
                    "Ticker": t,
                    "Last Price": round(last, 2),
                    "% Change": round(pct_change, 2),
                    "Alert": "🔔" if abs(pct_change) >= alert_pct else ""
                })
            except Exception:
                continue

        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
            st.caption(f"Checked as of {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            st.info("No data returned. Check your tickers.")

# ---------- Tab 3: High Probability Ideas ----------
with tabs[2]:
    st.subheader("High Probability Ideas (Educational)")
    candidates = ["AAPL", "MSFT", "NVDA", "JNJ", "PG", "KO", "ABBV"]  # Mix growth + dividend
    ideas = []
    for t in candidates:
        try:
            info = yf.Ticker(t).info
            raw_yield = info.get('dividendYield') or 0
            # NOTE: Yahoo's dividendYield units have changed between yfinance
            # versions (sometimes a decimal fraction like 0.006, sometimes
            # already a percent like 0.6). Confirm against a known ticker
            # before trusting this in production.
            div_yield = raw_yield * 100 if raw_yield < 1 else raw_yield
            ideas.append({
                "Ticker": t,
                "Type": "Growth" if "tech" in str(info.get('sector', '')).lower() else "Dividend",
                "Dividend Yield": f"{div_yield:.2f}%",
                "Forward PE": info.get('forwardPE', 'N/A'),
                "Notes": "Strong dividend history" if div_yield > 2 else "Growth potential"
            })
        except Exception:
            continue  # was a bare `except: pass` — now at least scoped to Exception
    st.dataframe(pd.DataFrame(ideas), use_container_width=True)

# ---------- Tab 4: Risk Tools (previously empty — no content existed for this tab) ----------
with tabs[3]:
    st.subheader("Position Size & Risk Calculator")
    col1, col2 = st.columns(2)
    with col1:
        account_size = st.number_input("Account size ($)", min_value=0.0, value=10000.0, step=500.0)
        risk_pct = st.slider("Risk per trade (%)", 0.5, 5.0, 1.0, step=0.5)
    with col2:
        entry_price = st.number_input("Entry price ($)", min_value=0.01, value=100.0, step=1.0)
        stop_price = st.number_input("Stop-loss price ($)", min_value=0.01, value=95.0, step=1.0)

    risk_per_share = abs(entry_price - stop_price)
    dollar_risk = account_size * (risk_pct / 100)

    if risk_per_share > 0:
        shares = int(dollar_risk / risk_per_share)
        st.metric("Suggested Position Size", f"{shares} shares")
        st.metric("Dollar Risk", f"${dollar_risk:,.2f}")

        fig = go.Figure(go.Bar(
            x=["Entry", "Stop-Loss"],
            y=[entry_price, stop_price],
            marker_color=["#2ca02c", "#d62728"]
        ))
        fig.update_layout(title="Entry vs. Stop-Loss", height=300)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Entry and stop-loss can't be equal.")

st.caption("VADER analyzes news tone. Combine with technicals and risk management.")
