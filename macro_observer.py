from __future__ import annotations

import math
from datetime import datetime, time
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

st.set_page_config(page_title="美股市場觀察工具", page_icon="📈", layout="wide")

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
        df = fetch_fred(sid)
        if df.empty:
            rows.append([name, "N/A", "N/A", "待接預期值", "—"])
            continue
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else latest
        expected = get_expectation(name)

        rows.append([
            name,
            f"{latest['date'].year % 100}/{latest['date'].month}",
            f"{latest['value']:.2f}%" if name == "巴菲特指標" else f"{latest['value']:.2f}",
            "N/A" if expected is None else f"{expected:.2f}",
            f"{prev['value']:.2f}%" if name == "巴菲特指標" else f"{prev['value']:.2f}",
        ])

    return pd.DataFrame(rows, columns=["數據", "更新日", "最新", "預期值", "前期"])


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
    [data-testid="stAppViewContainer"] {
    background: #f7f8fa;
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
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("美股市場觀察")
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
    left, right = st.columns([1.35, 1])
    with left:
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

    with right:
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
        st.dataframe(pd.DataFrame(side_rows,  columns=["指標", "最新", "日漲跌"]), use_container_width=False, hide_index=True)

st.markdown("---")
write_market_summary(is_open)

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
        st.line_chart(merged.set_index("date")[[index_name, macro_name]], use_container_width=True)
        st.caption("第一版先合畫原始數值；後面可改成雙軸、標準化、YoY、事件垂直線。")

st.caption("資料源：yfinance / FRED CSV。預期值欄位先保留，後續可接經濟日曆 API 或手動表格。")
