# Cloud Alerts V2 - GitHub Actions Setup

Hệ thống backup cảnh báo chạy trên GitHub Actions — **miễn phí**, chạy tự động mỗi 15 phút, không cần PC luôn bật.

## Cách hoạt động

```
GitHub Actions (mỗi 15 phút)
    ↓
cloud_alerts.py --once
    ↓
Fetch dữ liệu (Binance + Yahoo Finance)
    ↓
Phân tích kỹ thuật (RSI, MACD, ADX, Trend)
    ↓
Gửi Telegram BOT1 + BOT2
```

## Setup (5 phút)

### 1. Tạo GitHub Repository

```bash
# Từ thư mục TradingView-Analyzer
cd D:\NOTEBOOK\TradingView-Analyzer
git init
git add .
git commit -m "Cloud alerts v2"
git remote add origin https://github.com/YOUR_USERNAME/tva-cloud-alerts.git
git push -u origin main
```

### 2. Thêm Secrets trên GitHub

Vào repository → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Thêm 4 secrets:

| Secret Name | Value |
|-------------|-------|
| `BOT1_TOKEN` | `8756578403:AAELaPnA-YmC3ZuNXBd9vGpL1AkpQMjhiGg` |
| `BOT1_CHAT` | `5575146754` |
| `BOT2_TOKEN` | `8943977178:AAHr2YvNjBKcTNGaB1jwpxdR0SRBiZ-7dGo` |
| `BOT2_CHAT` | `5575146754` |

### 3. Kích hoạt Workflow

1. Vào **Actions** tab trên GitHub
2. Chọn **TVA Cloud Alerts**
3. Nhấn **Enable workflow**

### 4. Test

Nhấn **Run workflow** → **Run workflow** để test thủ công.

Kiểm tra Telegram BOT1 + BOT2 có nhận tin nhắn không.

## Chạy local (không cần GitHub)

```powershell
# Test 1 lần
$env:BOT1_TOKEN="8756578403:AAELaPnA-YmC3ZuNXBd9vGpL1AkpQMjhiGg"
$env:BOT1_CHAT="5575146754"
$env:BOT2_TOKEN="8943977178:AAHr2YvNjBKcTNGaB1jwpxdR0SRBiZ-7dGo"
$env:BOT2_CHAT="5575146754"
python cloud_alerts.py --once
```

## Symbols được phân tích

| Tên | Nguồn data |
|-----|-----------|
| Gold (XAUUSD) | Binance PAXGUSDT |
| USOIL | Yahoo CL=F |
| Bitcoin | Binance BTCUSDT |
| Ethereum | Binance ETHUSDT |
| US30 | Yahoo ^DJI |
| GBP/USD | Yahoo GBPUSD=X |
| EUR/USD | Yahoo EURUSD=X |
| USD/JPY | Yahoo USDJPY=X |
| DXY | Yahoo DX-Y.NYB |
| JPY Index | Yahoo JPY=X |
| US 10Y (Lãi suất) | Yahoo ^TNX |

## Lưu ý

- **GitHub Actions free tier**: 2,000 phút/tháng → ~80 lần chạy/tháng (đủ cho 15-min interval)
- **Workflow tự tắt** nếu không commit gì trong 60 ngày → commit định kỳ hoặc dùng `workflow_dispatch`
- **Dữ liệu Yahoo Finance**: delayed 15 phút (miễn phí)
- **Dữ liệu Binance**: real-time (miễn phí)
