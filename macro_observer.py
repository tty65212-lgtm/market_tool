from __future__ import annotations

import math
from datetime import datetime, time
from zoneinfo import ZoneInfo

import base64
from pathlib import Path

from matplotlib.pylab import size
import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

from urllib.parse import quote
st.set_page_config(page_title="美股市場觀察工具", page_icon="📈", layout="wide")

MARKET_QUOTES = [
    {
        "quote": "華爾街沒有新鮮事，投機如山嶽般古老。",
        "author": "傑西・利弗莫爾",
        "image": "assets/bg_01.png",
    },
    {
        "quote": "如果你不打算持有一支股票十年，那麼連十分鐘都不要持有。",
        "author": "沃倫・巴菲特",
        "image": "assets/bg_02.png",
    },
    {
        "quote": "如果市場證明你的交易方向正確，就應該持續持有，不要過早獲利了結。",
        "author": "幽靈",
        "image": "assets/bg_03.png",
    },
]

def get_base64_image(image_path: str):
    path = Path(image_path)
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


today_index = datetime.now().day % len(MARKET_QUOTES)
selected_quote = MARKET_QUOTES[today_index]
bg_base64 = get_base64_image(selected_quote["image"])

# ========= 基本設定 =========
INDEX_SYMBOLS = {
    "S&P 500": "^GSPC",
    "NASDAQ": "^IXIC",
    "DOW": "^DJI",
    "SOX": "^SOX",
    "QQQ": "QQQ",
}

MACRO_SYMBOLS = {
    "國際原油 WTI": "CL=F",
    "美元指數 DXY": "DX-Y.NYB",
    "10Y 美債殖利率": "^TNX",
    "30Y 美債殖利率": "^TYX",
}

FRED_SERIES = {
    "CPI": "CPIAUCSL",
    "Core CPI": "CPILFESL",
    "PPI": "PPIACO",
    "非農": "PAYEMS",
    "Fed 利率": "FEDFUNDS",
    "巴菲特指標": "DDDM01USA156NWDB",
}

# 預期值較難從免費穩定 API 取得，先做成可手動填入欄位，後面再接資料源。
EXPECTATIONS = {
    "CPI": None,
    "Core CPI": None,
    "PPI": None,
    "非農": None,
    "Fed 利率": None,
}

ECON_CALENDAR = {
    "下次 CPI": "2026-05-13",
    "下次 PPI": "2026-05-15",
    "下次 非農": "2026-05-02",
    "下次 Fed 會議": "2026-06-17",
}

BUFFETT_INDICATOR = {
    "date": "26/5",
    "value": 229.6,
    "prev": 229.5,
    "yoy": "N/A"
}

def get_expectation(name: str):
    """
    預期值接口
    之後可改接外部 API
    """
    try:
        return EXPECTATIONS.get(name, None)
    except Exception:
        return None

def market_session() -> tuple[str, bool]:
    """Return US market session text and whether regular market is open."""
    now_et = datetime.now(ZoneInfo("America/New_York"))
    weekday = now_et.weekday()  # 0 Mon, 6 Sun
    regular_open = time(9, 30)
    regular_close = time(16, 0)

    if weekday >= 5:
        return "美股休市｜顯示最近收盤價", False
    if regular_open <= now_et.time() <= regular_close:
        return "美股開盤中｜顯示即時/延遲價格", True
    return "美股閉盤｜顯示收盤價", False


@st.cache_data(ttl=60)
def fetch_yf_history(symbol: str, period: str = "5d", interval: str = "1d") -> pd.DataFrame:
    if yf is None:
        return pd.DataFrame()
    data = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=False)
    if data is None or data.empty:
        return pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data.dropna(how="all")


@st.cache_data(ttl=1800)
def fetch_fred(series_id: str) -> pd.DataFrame:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        df = pd.read_csv(url)
        df.columns = ["date", "value"]
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna()
    except Exception:
        return pd.DataFrame(columns=["date", "value"])


def latest_price_info(symbol: str) -> dict:
    # 用 5 天日線，穩定取得最近收盤與前收；開盤中仍以 yfinance 可拿到的最新 close 顯示。
    hist = fetch_yf_history(symbol, period="5d", interval="1d")
    if hist.empty or "Close" not in hist:
        return {"price": math.nan, "change_pct": math.nan, "prev": math.nan}

    closes = hist["Close"].dropna()
    if len(closes) == 0:
        return {"price": math.nan, "change_pct": math.nan, "prev": math.nan}

    price = float(closes.iloc[-1])
    prev = float(closes.iloc[-2]) if len(closes) >= 2 else price
    change_pct = (price / prev - 1) * 100 if prev else math.nan
    return {"price": price, "change_pct": change_pct, "prev": prev}


def fmt_num(x: float, digits: int = 2) -> str:
    if pd.isna(x):
        return "N/A"
    return f"{x:,.{digits}f}"


def fmt_pct(x: float) -> str:
    if pd.isna(x):
        return "N/A"
    sign = "+" if x >= 0 else ""
    return f"{sign}{x:.2f}%"


def color_for_change(x: float) -> str:
    if pd.isna(x):
        return "#9ca3af"
    return "#16a34a" if x >= 0 else "#dc2626"


def price_color(is_open: bool) -> str:
    # 使用者指定：開盤中價格綠色；閉盤/休市收盤價紅色。
    return "#16a34a" if is_open else "#b80223"

TV_LINKS = {
    "S&P 500": "https://www.tradingview.com/symbols/SPX/",
    "NASDAQ": "https://www.tradingview.com/symbols/NASDAQ-IXIC/",
    "DOW": "https://www.tradingview.com/symbols/DJ-DJI/",
    "SOX": "https://www.tradingview.com/symbols/NASDAQ-SOX/",
    "QQQ": "https://www.tradingview.com/symbols/NASDAQ-QQQ/",
}

def index_card(name: str, symbol: str, is_open: bool):
    info = latest_price_info(symbol)
    p_color = price_color(is_open)
    c_color = color_for_change(info["change_pct"])
    link = TV_LINKS.get(name, "#")

    st.markdown(
        f"""<a href="{link}" target="_blank" class="card-link">
<div class="card">
{"<div class='sleep-icon'>💤</div>" if not is_open else ""}
<div class="card-title">{name}</div>
<div class="price" style="color:{p_color};">{fmt_num(info['price'])}</div>
<div class="change" style="color:{c_color};">{fmt_pct(info['change_pct'])}</div>
</div>
</a>""",
        unsafe_allow_html=True,
    )


def latest_yf_value(symbol: str, digits: int = 2, multiplier: float = 1.0) -> str:
    hist = fetch_yf_history(symbol, period="5d", interval="1d")
    if hist.empty or "Close" not in hist:
        return "N/A"
    return fmt_num(float(hist["Close"].dropna().iloc[-1]) * multiplier, digits)

def latest_yf_info(symbol: str, multiplier: float = 1.0):
    try:
        hist = fetch_yf_history(symbol, period="5d", interval="1d")

        if hist.empty or "Close" not in hist.columns:
            return {"price": "N/A", "change_pct": "N/A"}

        closes = hist["Close"].dropna()

        if len(closes) < 2:
            return {
                "price": f"{closes.iloc[-1] * multiplier:.2f}",
                "change_pct": "N/A",
            }

        latest = closes.iloc[-1] * multiplier
        prev = closes.iloc[-2] * multiplier

        pct = ((latest - prev) / prev) * 100

        return {
            "price": f"{latest:.2f}",
            "change_pct": f"{pct:+.2f}%"
        }

    except Exception:
        return {
            "price": "N/A",
            "change_pct": "N/A"
        }

def macro_latest_table() -> pd.DataFrame:
    rows = []
    for name, sid in FRED_SERIES.items():

        if name == "巴菲特指標":
            rows.append([
                name,
                BUFFETT_INDICATOR["date"],
                f"{BUFFETT_INDICATOR['value']:.1f}%",
                f"{BUFFETT_INDICATOR['prev']:.1f}%",
                BUFFETT_INDICATOR["yoy"],
            ])
            continue
        
        df = fetch_fred(sid)
        if df.empty:
            rows.append([name, "N/A", "N/A", "-", "N/A"])
            continue
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else latest
        yoy = "N/A"
        if len(df) >= 13 and prev["value"] != 0:
            yoy = f"{((latest['value'] / df.iloc[-13]['value']) - 1) * 100:+.2f}%"

        rows.append([
    name,
    f"{latest['date'].year % 100}/{latest['date'].month}",
    f"{latest['value']:.2f}" if name == "巴菲特指標" else f"{latest['value']:.2f}",
    f"{prev['value']:.2f}%" if name == "巴菲特指標" else f"{prev['value']:.2f}",
    yoy,
    ])

    return pd.DataFrame(rows, columns=["數據", "更新日", "最新", "前期", "年增率"])


def write_market_summary(is_open: bool):
    # 第一版總評：不下買賣結論，只整理水位。
    spx = latest_price_info("^GSPC")
    qqq = latest_price_info("QQQ")
    sox = latest_price_info("^SOX")
    ten_y = latest_yf_value("^TNX", digits=2, multiplier=0.1)  # ^TNX 報價約為殖利率*10
    dxy = latest_yf_value("DX-Y.NYB", digits=2)
    oil = latest_yf_value("CL=F", digits=2)

    session_text = "市場仍在跳動" if is_open else "今日戰況已定"
    st.markdown(
        f"""
        <div class="summary-box">
            <b>總評骨架</b><br>
            {session_text}。目前先以價格結構為主：S&P 500 {fmt_pct(spx['change_pct'])}、QQQ {fmt_pct(qqq['change_pct'])}、SOX {fmt_pct(sox['change_pct'])}。
            旁邊觀察美元指數約 {dxy}、WTI 原油約 {oil}、10Y 美債殖利率約 {ten_y}%。
            後續等 CPI / PPI / 非農 / Fed 預期接好後，再生成「經濟水位」燈號作參考，不讓燈號反客為主。
        </div>
        """,
        unsafe_allow_html=True,
    )


st.markdown(
    """
    <style>
    [data-testid='stAppViewContainer'] {
    background: #f7f8fa;
}
    background-size: 100% 360px;
    background-position: top center;
    background-repeat: no-repeat;
    background-attachment: scroll;
}

[data-testid="stHeader"] {
    background: transparent;
}

[data-testid="stMainBlockContainer"] {
    padding-top: 2rem;
}

.card {
    border: 1px solid rgba(255,255,255,0.95);

    border-radius: 26px;

    padding: 22px 22px 18px 22px;

    background: rgba(255,255,255,0.98);

    box-shadow:
        0 2px 6px rgba(0,0,0,0.03),
        0 10px 24px rgba(0,0,0,0.06);

    transition: all 0.25s ease;

    min-height: 170px;
}

.card:hover {
    transform: translateY(-2px);
    box-shadow:
        0 8px 18px rgba(0,0,0,0.05),
        0 18px 38px rgba(0,0,0,0.08);
}

.card-link {
    text-decoration: none !important;
    color: inherit !important;
}

.card-link * {
    text-decoration: none !important;
}

.card-link:hover {
    text-decoration: none;
}

.card-title {
    color: #111827;
}

.symbol {
    color: #64748b;
}
.price {
    font-size: 2.2rem;

    font-weight: 550;

    margin-top: 20px;

    letter-spacing: -0.05em;

    line-height: 1.05;

    font-family:
        "Inter",
        "SF Pro Display",
        "Segoe UI",
        sans-serif;
}
    .change {
    font-size: 1rem;

    font-weight: 600;

    margin-top: 10px;

    letter-spacing: -0.02em;
}
    .summary-box {
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 18px;
        padding: 18px;
        background: rgba(255,255,255,0.055);
        color: #e5e7eb;
        line-height: 1.75;
    }
    .section-title { font-size: 1.25rem; font-weight: 800; margin-top: 10px; margin-bottom: 12px; }
    .stTabs [data-baseweb="tab"] {
    color: #9ca3af;
    font-weight: 500;
    font-size: 1rem;
}

.stTabs [aria-selected="true"] {
    color: #111827 !important;
    font-weight: 800 !important;
}

.quote-banner {
    min-height: 40px;
    display: flex;
    justify-content: flex-end;
    align-items: center;
    padding: 4px 28px 2px 28px;
    margin: 0 0 28px 0;
    background: transparent !important;
}

.quote-text {
    font-size: 1.5rem;

    font-weight: 700;

    font-family:
        "STKaiti",
        "KaiTi TC",
        "DFKai-SB",
        "KaiTi",
        serif;

    color: rgba(28, 37, 49, 0.72);

    line-height: 1.75;

    text-align: right;

    max-width: 760px;

    letter-spacing: 0.04em;

    text-shadow:
        0 1px 0 rgba(255,255,255,0.45),
        0 2px 8px rgba(0,0,0,0.05);
}

.quote-author {
    margin-top: 6px;

    font-size: 1rem;

    font-family:
        "STKaiti",
        "KaiTi TC",
        serif;

    font-weight: 400;

    color: rgba(71,85,105,0.55);

    text-align: right;

    letter-spacing: 0.08em;
}

    </style>
    """,
    unsafe_allow_html=True,
)

st.title("美股市場觀察")

if bg_base64:
    
    chart_svg = """
    <svg xmlns='http://www.w3.org/2000/svg'
        width='320'
        height='160'
        viewBox='0 0 320 160'>

    <defs>
        <linearGradient id='g' x1='0' y1='0' x2='0' y2='1'>
        <stop offset='0%' stop-color='#00a889' stop-opacity='0.08'/>
        <stop offset='100%' stop-color='#00a889' stop-opacity='0'/>
        </linearGradient>
    </defs>

    <path
        d='M0 120
            L25 110
            L40 118
            L58 98
            L74 116
            L96 108
            L118 44
            L132 76
            L148 90
            L168 72
            L190 80
            L212 92
            L232 88
            L254 96
            L280 84
            L320 104
            L320 160
            L0 160 Z'
        fill='url(#g)'/>

    <path
        d='M0 120
            L25 110
            L40 118
            L58 98
            L74 116
            L96 108
            L118 44
            L132 76
            L148 90
            L168 72
            L190 80
            L212 92
            L232 88
            L254 96
            L280 84
            L320 104'
        fill='none'
        stroke='#00a889'
        stroke-width='1.6'
        stroke-linecap='round'
        stroke-linejoin='round'
        opacity='0.22'/>
    </svg>
    """
    chart_svg_url = quote(chart_svg)

    st.markdown(
        f"""
<style>
[data-testid="stAppViewContainer"] {{
    background:
        linear-gradient(
            to bottom,
            rgba(247,248,250,0.00) 0%,
            rgba(247,248,250,0.18) 42%,
            rgba(247,248,250,0.70) 70%,
            #f7f8fa 100%
        ),
        url("data:image/png;base64,{bg_base64}");

    background-size: 100% 420px;
    background-position: top center;
    background-repeat: no-repeat;
}}

/* 指數卡片：淡淡價格走勢背景 */
.card {{
    position: relative;

    background:
        url("data:image/svg+xml;utf8,{chart_svg_url}"),
        linear-gradient(
            135deg,
            rgba(255,255,255,0.95),
            rgba(255,255,255,0.985)
        );

    background-repeat: no-repeat;
    background-position: center bottom;
    background-size: cover, cover;

    border-radius: 22px;
}}

.sleep-icon {{
    position: absolute;
    top: 12px;
    right: 14px;

    font-size: 20px;
    opacity: 0.42;

    filter: grayscale(20%);
    pointer-events: none;
}}

.market-mini-card {{
    background: rgba(255,255,255,0.86);
    border-radius: 20px;
    padding: 18px 18px 16px 18px;
    min-height: 118px;
    box-shadow: 0 6px 20px rgba(0,0,0,0.045);
}}

.market-mini-title {{
    font-size: 0.95rem;
    color: rgba(30,41,59,0.72);
    margin-bottom: 12px;
}}

.market-mini-value {{
    font-size: 1.45rem;
    font-weight: 650;
    color: #1f2937;
    margin-bottom: 8px;
}}

.market-mini-change {{
    font-size: 0.95rem;
    font-weight: 600;
    color: #059669;
}}

/* 基本面摘要 table */
[data-testid="stDataFrame"] table {{
    font-size: 20px !important;
}}

[data-testid="stDataFrame"] th {{
    font-size: 20px !important;
    font-weight: 600 !important;
}}

[data-testid="stDataFrame"] td {{
    font-size: 20px !important;
    padding: 10px 12px;
}}

[data-testid="stDataFrame"] table {{
    width: auto !important;
}}

</style>
""",
        unsafe_allow_html=True,
    )

if bg_base64:
    st.markdown(
    f"""
<div class="quote-banner">
    <div class="quote-content">
        <div class="quote-text">{selected_quote['quote']}</div>
        <div class="quote-author">—— {selected_quote['author']}</div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

else:
    st.info(f"「{selected_quote['quote']}」—— {selected_quote['author']}")

session_label, is_open = market_session()
st.caption(session_label)

tab_overview, tab_detail = st.tabs(["第一層｜總覽", "第二層｜細節對比"])

with tab_overview:
    st.markdown('<div class="section-title">大盤價格</div>', unsafe_allow_html=True)
    cols = st.columns(5)
    for col, (name, symbol) in zip(cols, INDEX_SYMBOLS.items()):
        with col:
            index_card(name, symbol, is_open)

    st.markdown("---")
    st.markdown('<div class="section-title">基本面摘要</div>', unsafe_allow_html=True)
    st.dataframe(macro_latest_table(), use_container_width=True, hide_index=True)
    st.caption(
        f"""
    下次 CPI：{ECON_CALENDAR['下次 CPI']} ｜ 
    PPI：{ECON_CALENDAR['下次 PPI']} ｜ 
    非農：{ECON_CALENDAR['下次 非農']} ｜ 
    Fed：{ECON_CALENDAR['下次 Fed 會議']}
    """
    )

    st.markdown('<div class="section-title">市場數據</div>', unsafe_allow_html=True)
    oil = latest_yf_info("CL=F")
    dxy = latest_yf_info("DX-Y.NYB")
    us10y = latest_yf_info("^TNX")
    us30y = latest_yf_info("^TYX")

    side_rows = [
        ["WTI 原油", oil["price"] + " USD/桶", oil["change_pct"]],
        ["美元指數 DXY", dxy["price"], dxy["change_pct"]],
        ["10Y 美債殖利率", us10y["price"] + "%", us10y["change_pct"]],
        ["30Y 美債殖利率", us30y["price"] + "%", us30y["change_pct"]],
    ]
    
    market_cols = st.columns(4)

    for col, row in zip(market_cols, side_rows):
        name, value, change = row

        with col:
            st.markdown(
                f"""
                <div class="market-mini-card">
                    <div class="market-mini-title">{name}</div>
                    <div class="market-mini-value">{value}</div>
                    <div class="market-mini-change">{change}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


with tab_detail:
    st.subheader("基本數據 × 大盤價格 合畫對比")
    c1, c2, c3 = st.columns(3)
    with c1:
        index_name = st.selectbox("選擇大盤", list(INDEX_SYMBOLS.keys()), index=0)
    with c2:
        macro_name = st.selectbox("選擇基本數據", list(FRED_SERIES.keys()), index=0)
    with c3:
        years = st.slider("回看年數", 1, 20, 5)

    idx_symbol = INDEX_SYMBOLS[index_name]
    idx = fetch_yf_history(idx_symbol, period=f"{years}y", interval="1mo")
    mac = fetch_fred(FRED_SERIES[macro_name])

    if idx.empty or mac.empty:
        st.warning("資料暫時讀取失敗。請確認網路、套件與資料源是否正常。")
    else:
        idx_plot = idx.reset_index()[[idx.reset_index().columns[0], "Close"]]
        idx_plot.columns = ["date", index_name]
        idx_plot["date"] = pd.to_datetime(idx_plot["date"]).dt.tz_localize(None)
        start_date = pd.Timestamp.today() - pd.DateOffset(years=years)
        mac_plot = mac[mac["date"] >= start_date].copy()
        idx_plot["date"] = pd.to_datetime(idx_plot["date"]).dt.tz_localize(None).astype("datetime64[ns]")
        mac_plot["date"] = pd.to_datetime(mac_plot["date"]).dt.tz_localize(None).astype("datetime64[ns]")

        merged = pd.merge_asof(
            idx_plot.sort_values("date"),
            mac_plot.sort_values("date"),
            on="date",
            direction="nearest",
        ).rename(columns={"value": macro_name})
        import plotly.graph_objects as go

    fig = go.Figure()

    # CPI 柱狀圖（右軸）
    # 基本數據改成年增率 YoY
    merged[f"{macro_name} YoY"] = merged[macro_name].pct_change(12) * 100

    fig.add_trace(
        go.Bar(
            x=merged["date"],
            y=merged[f"{macro_name} YoY"],
            name=f"{macro_name} YoY",
            yaxis="y2",
            opacity=0.25,
            marker=dict(color="rgba(120, 140, 255, 0.45)"),
            hovertemplate="%{x|%Y-%m}<br>" + f"{macro_name} YoY: " + "%{y:.2f}%<extra></extra>"
        )
    )

    # 指數價格折線（左軸）
    fig.add_trace(
        go.Scatter(
            x=merged["date"],
            y=merged[index_name],
            name=index_name,
            mode="lines",
            line=dict(width=2)
        )
    )

    fig.update_layout(
        height=580,

        hovermode="x unified",

        template="plotly_white",

        margin=dict(l=20, r=20, t=20, b=20),

        yaxis=dict(
            title=index_name,
            showgrid=True
        ),

        yaxis2=dict(
        title=f"{macro_name} YoY (%)",
        overlaying="y",
        side="right",
        showgrid=False,
        zeroline=True
        ),

        legend=dict(
            orientation="h",
            y=1.02,
            x=0
        )
    )

    st.plotly_chart(fig, use_container_width=True)

    st.caption("第一版先合畫原始數值；後面可改成雙軸、標準化、YoY、事件垂直線。")

