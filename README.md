# 美股市場觀察工具 v0.1

## 功能
- 第一層總覽：S&P 500、NASDAQ、DOW、SOX、QQQ
- 開盤中：價格用綠色顯示
- 閉盤 / 休市：收盤價用紅色顯示
- 顯示漲跌幅 %
- 次要基本面摘要：CPI、Core CPI、PPI、非農、Fed 有效利率
- 旁觀數據：WTI 原油、美元指數、10Y / 30Y 美債殖利率
- 第二層雛形：基本數據與大盤價格合畫對比

## 安裝
```bash
cd market_tool
python -m pip install -r requirements.txt
```

## 執行
```bash
streamlit run app.py
```

## 後續可加
- CPI / PPI / 非農「預期值」資料源
- FedWatch 降息 / 升息機率
- 20Y 美債、日債殖利率
- 巴菲特指標
- VIX / RSP / 市場廣度
- 第二層雙軸與事件垂直線
