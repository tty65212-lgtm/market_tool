import streamlit as st
import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import requests
import matplotlib.dates as mdates
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Crypto Market Tool", layout="wide")

st.markdown("""
<h1 style="
font-size:60px;
margin-bottom:10px;
">
市場數據
</h1>
""", unsafe_allow_html=True)

symbol = "BTC-USD"
binance_symbol = "BTCUSDT"

oi_url = "https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT"
oi_data = requests.get(oi_url, timeout=10).json()
open_interest = float(oi_data["openInterest"])
# ======== OI HISTORY =========

oi_history_url = "https://fapi.binance.com/futures/data/openInterestHist"

oi_params = {
    "symbol": binance_symbol,
    "period": "1d",
    "limit": 180
}

oi_history = requests.get(
    oi_history_url,
    params=oi_params,
    timeout=10
).json()

oi_df = pd.DataFrame(oi_history)

oi_df["timestamp"] = pd.to_datetime(oi_df["timestamp"], unit="ms")
oi_df["sumOpenInterest"] = oi_df["sumOpenInterest"].astype(float)

oi_average = oi_df["sumOpenInterest"].mean()

oi_max = float(oi_df["sumOpenInterest"].max())
oi_min = float(oi_df["sumOpenInterest"].min())

oi_vs_max = open_interest / oi_max
oi_vs_min = open_interest / oi_min

latest_oi_history = oi_df["sumOpenInterest"].iloc[-1]

oi_ratio = latest_oi_history / oi_average

# ======== OI EXTREME STATUS ========

if oi_vs_max > 0.95:
    oi_extreme_status = "🔴 極度狂熱"

elif oi_vs_max > 0.85:
    oi_extreme_status = "🟡 OI偏高"

elif oi_vs_min < 1.15:
    oi_extreme_status = "🔵 極度冷清"

else:
    oi_extreme_status = "⚪ 市場中性"

# ======== OI STATUS =========

if oi_ratio > 1.2:
    oi_status = "OI 高於 6 個月平均，槓桿偏擁擠。"
elif oi_ratio < 0.85:
    oi_status = "OI 低於 6 個月平均，槓桿相對乾淨。"
else:
    oi_status = "OI 接近 6 個月平均，槓桿水位中性。"

# ======== MARKET DATA =========

data = yf.download(symbol, period="6mo", interval="1d")

close = data["Close"]

latest_price = float(close.iloc[-1].iloc[0])

st.markdown(f"""
<div style="margin-top:20px;">

<div style="
font-size:28px;
color:black;
">
BTC Price
</div>

<div style="
font-size:36px;
font-weight:700;
">
{latest_price:,.2f} USD
</div>

</div>
""", unsafe_allow_html=True)

# ========== FUNDING RATE ==========

funding_url = "https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT"
funding_data = requests.get(funding_url, timeout=10).json()
funding_rate = float(funding_data["lastFundingRate"]) * 100

# ========== OPEN INTEREST ==========
oi_url = "https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT"
oi_data = requests.get(oi_url, timeout=10).json()
open_interest = float(oi_data["openInterest"])

# ===== OI HISTORY =====

oi_history_url = "https://fapi.binance.com/futures/data/openInterestHist"

oi_params = {
    "symbol": "BTCUSDT",
    "period": "1d",
    "limit": 180
}

oi_history = requests.get(
    oi_history_url,
    params=oi_params,
    timeout=10
).json()

oi_df = pd.DataFrame(oi_history)
oi_df["timestamp"] = pd.to_datetime(oi_df["timestamp"], unit="ms")
oi_df["sumOpenInterest"] = oi_df["sumOpenInterest"].astype(float)

oi_average = oi_df["sumOpenInterest"].mean()
latest_oi_history = oi_df["sumOpenInterest"].iloc[-1]
oi_ratio = latest_oi_history / oi_average

# ========== LONG SHORT RATIO ==========
ls_url = "https://fapi.binance.com/futures/data/globalLongShortAccountRatio"
ls_params = {
    "symbol": binance_symbol,
    "period": "1h",
    "limit": 30
}
ls_data = requests.get(ls_url, params=ls_params, timeout=10).json()
ls_df = pd.DataFrame(ls_data)

latest_ls_ratio = float(ls_df.iloc[-1]["longShortRatio"])
latest_long = float(ls_df.iloc[-1]["longAccount"]) * 100
latest_short = float(ls_df.iloc[-1]["shortAccount"]) * 100

# ======== LEVERAGE HEAT SCORE =========

heat_score = 50

# OI 偏離平均值
heat_score += (oi_ratio - 1) * 50

# Funding 修正
if funding_rate > 0.03:
    heat_score += 15
elif funding_rate < -0.01:
    heat_score += 10

# 多空比修正
if latest_ls_ratio > 1.3:
    heat_score += 10
elif latest_ls_ratio < 0.8:
    heat_score += 10

# 限制在 0～100
heat_score = max(0, min(100, heat_score))

if heat_score >= 80:
    heat_status = "高風險：槓桿明顯擁擠。"
elif heat_score >= 60:
    heat_status = "偏熱：市場槓桿開始升溫。"
elif heat_score >= 30:
    heat_status = "中性：槓桿水位正常。"
else:
    heat_status = "乾淨：槓桿相對低。"


# ======== LEVERAGE DASHBOARD =========

st.subheader("BTC市場數據")

main_col, detail_col = st.columns([0.1, 1])

with main_col:

    st.markdown(f"""
    <div style="font-size:24px;color:black;">資金費率</div>
    <div style="font-size:36px;font-weight:700;">{funding_rate:.4f}%</div>

    <br>

    <div style="font-size:24px;color:black;">OI</div>
    <div style="font-size:36px;font-weight:700;">{open_interest:,.0f} BTC</div>

    <br>

    <div style="font-size:24px;color:black;">OI倍率</div>
    <div style="font-size:36px;font-weight:700;">{oi_ratio:.2f}倍</div>

    <br>

    <div style="font-size:24px;color:black;">多/空 比</div>
    <div style="font-size:36px;font-weight:700;">{latest_ls_ratio:.2f}</div>
    """, unsafe_allow_html=True)

with detail_col:

    st.markdown(f"""
    <div style="margin-top:90px;color:gray;line-height:2.5;">
    當前OI：{open_interest:,.0f} BTC<br>
    6M平均OI：{oi_average:,.0f} BTC<br>
    歷史OI高點：{oi_max:,.0f} BTC<br>
    歷史OI低點：{oi_min:,.0f} BTC<br>
    OI高點比：{oi_vs_max:.2f}倍<br>
    OI低點比：{oi_vs_min:.2f}倍<br>
    多頭：{latest_long:.2f}%<br>
    空頭：{latest_short:.2f}%    </div>
    """, unsafe_allow_html=True)

# ======== HEAT LIGHT ========

if oi_ratio > 1.2:
    heat_emoji = "🔴"
    heat_text = "市場過熱"

elif oi_ratio < 0.85:
    heat_emoji = "🔵"
    heat_text = "市場冷清"

else:
    heat_emoji = "🟡"
    heat_text = "市場偏熱"

st.markdown(f"""
<div style="
padding:12px;
border-radius:10px;
background-color:#f8f8e8;
font-size:22px;
font-weight:600;
">
{heat_emoji} 綜合：{heat_text}　｜　{oi_extreme_status}
</div>
""", unsafe_allow_html=True)

# ======== BTC PRICE VS OI CHART =========

with st.expander("BTC Price vs Open Interest", expanded=False):

    price_for_oi = data.loc[
        (data.index >= oi_df["timestamp"].min()) &
        (data.index <= oi_df["timestamp"].max())
    ]

    close_for_oi = price_for_oi["Close"].squeeze()

    fig_oi = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.7, 0.3],
        subplot_titles=("BTC Price", "Open Interest")
    )

    fig_oi.add_trace(
        go.Scatter(
            x=price_for_oi.index,
            y=close_for_oi,
            mode="lines",
            name="BTC Price",
            line=dict(color="orange", width=3)
        ),
        row=1,
        col=1
    )

    fig_oi.add_trace(
        go.Scatter(
            x=oi_df["timestamp"],
            y=oi_df["sumOpenInterest"],
            mode="lines",
            name="Open Interest",
            line=dict(color="deepskyblue", width=3)
        ),
        row=2,
        col=1
    )

    fig_oi.add_trace(
        go.Scatter(
            x=oi_df["timestamp"],
            y=[oi_average] * len(oi_df),
            mode="lines",
            name="6M OI Average",
            line=dict(color="gray", width=2, dash="dash")
        ),
        row=2,
        col=1
    )

    fig_oi.update_layout(
    title="BTC Price vs Open Interest",
    height=700,
    width=1100,
    hovermode="x unified",
    showlegend=True,
)

    fig_oi.update_xaxes(
    tickformat="%m/%d",
    showspikes=True,
    spikemode="across+toaxis",
    spikesnap="cursor",
    spikecolor="gray",
    spikethickness=1
)

    fig_oi.update_yaxes(
        title_text="BTC Price USD",
        row=1,
        col=1
    )

    fig_oi.update_yaxes(
        title_text="O/I BTC",
        row=2,
        col=1
    )

    st.plotly_chart(fig_oi, use_container_width=False)
    
# ======== EMA SIGNAL ========

ema150 = close.ewm(span=150).mean()
ema200 = close.ewm(span=200).mean()

latest_ema150 = float(ema150.iloc[-1].iloc[0])
latest_ema200 = float(ema200.iloc[-1].iloc[0])

st.subheader("EMA")

st.write(f"EMA150 : ${latest_ema150:,.2f}")
st.write(f"EMA200 : ${latest_ema200:,.2f}")

if latest_price > latest_ema200:
    ema_signal = "🟢 目前價格高於 EMA200"
    st.success(ema_signal)
else:
    ema_signal = "🔴 目前價格低於 EMA200"
    st.error(ema_signal)

# ========== FUNDING HISTORY ==========
with st.expander("Funding Rate History", expanded=False):

    funding_history_url = "https://fapi.binance.com/fapi/v1/fundingRate"
    funding_history_params = {
    "symbol": binance_symbol,
    "limit": 100
}

    funding_history = requests.get(
    funding_history_url,
    params=funding_history_params,
    timeout=10
    ).json()

    funding_df = pd.DataFrame(funding_history)
    funding_df["fundingTime"] = pd.to_datetime(funding_df["fundingTime"], unit="ms")
    funding_df["fundingRate"] = funding_df["fundingRate"].astype(float) * 100

    funding_start = funding_df["fundingTime"].min()
    funding_end = funding_df["fundingTime"].max()

    price_for_funding = data.loc[
    (data.index >= funding_start) & (data.index <= funding_end)
    ]

    close_for_funding = price_for_funding["Close"].squeeze()

    fig2 = make_subplots(
    rows=2,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.05,
    row_heights=[0.7, 0.3],
    )

    fig2.add_trace(
    go.Scatter(
        x=price_for_funding.index,
        y=close_for_funding,
        mode="lines",
        name="BTC Price"
    ),
    row=1,
    col=1
    )

    funding_colors = [
    "green" if x >= 0 else "red"
    for x in funding_df["fundingRate"]
    ]

    fig2.add_trace(
    go.Bar(
        x=funding_df["fundingTime"],
        y=funding_df["fundingRate"],
        name="Funding Rate",
        marker_color=funding_colors
    ),
    row=2,
    col=1
    )

    fig2.update_layout(
    title="BTC Price vs Funding Rate",
    height=650,
    width=1100,
    hovermode="x unified",
    showlegend=True
)

    fig2.update_xaxes(
    tickformat="%m/%d",
    showspikes=True,
    spikemode="across",
    spikesnap="cursor",
    spikecolor="gray",
    spikethickness=1
    )

    fig2.update_yaxes(
    title_text="BTC Price USD",
    row=1,
    col=1
    )

    fig2.update_yaxes(
    title_text="Funding %",
    row=2,
    col=1
    )

    st.plotly_chart(fig2, use_container_width=False
    )