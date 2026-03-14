# Telegram Trading Signals Bot

A Python bot that receives **TradingView** alerts (RSI, MACD) via webhooks and optionally monitors **Coinglass** for liquidation spikes, then sends concise **Buy/Sell** notifications to your Telegram chat or channel. No auto-trading—notifications only. Designed to run 24/7 on a VPS or in Docker.

---

## Features

- **TradingView webhooks**: Receive RSI and MACD (or strategy) alerts in real time.
- **Multiple assets (crypto, stocks, forex)**: Create one alert per symbol in TradingView; all hit the same webhook URL. The bot accepts any `symbol`/`ticker` and forwards to Telegram—you control which assets to monitor by creating alerts on those charts.
- **Coinglass**: Poll liquidations once per minute (configurable) and alert on spikes.
- **Fully customizable**: Indicators, rules, and signal parameters are controlled by you—via TradingView alert conditions and `.env` thresholds (RSI oversold/overbought, liquidation spike USD, cooldowns).
- **Anti-spam**: Per-asset cooldown and max alerts per minute.
- **Clear Telegram messages**: Asset pair, timeframe, trigger type, values, timestamp, and Buy/Sell recommendation.

---

## Requirements

- Python 3.9+
- A Telegram bot token ([@BotFather](https://t.me/BotFather)) and your chat ID (e.g. [@userinfobot](https://t.me/userinfobot)).
- (Optional) Coinglass API key from [Coinglass](https://www.coinglass.com/user) for liquidation alerts.

---

## Quick setup

### 1. Clone or copy the project

```bash
cd Telegram_bot
```

### 2. Create virtual environment and install dependencies

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure environment

Copy the example env and edit with your values:

```bash
copy .env.example .env   # Windows
# or
cp .env.example .env    # Linux/macOS
```

Edit `.env`:

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `TELEGRAM_CHAT_ID` | Your chat or channel ID (e.g. from @userinfobot) |
| `WEBHOOK_PORT` | Port for webhook server (default `80`; TradingView HTTP allows only port 80) |
| `COINGLASS_API_KEY` | Optional; leave empty to disable liquidation polling |
| `COINGLASS_SYMBOLS` | e.g. `Binance:BTCUSDT,Binance:ETHUSDT` |
| `RSI_OVERSOLD` / `RSI_OVERBOUGHT` | RSI thresholds (default 30 / 70) |
| `LIQUIDATION_SPIKE_USD` | Alert when 1h liquidation exceeds this (default 5M) |
| `ALERT_COOLDOWN_SECONDS` | Min seconds between same asset+trigger (default 300) |
| `MAX_ALERTS_PER_MINUTE` | Global rate limit (default 10) |

### 4. Run the bot

```bash
python main.py
```

You should see:

```
Starting webhook server (FastAPI) on 0.0.0.0:80
```

- **Health check**: `http://localhost:80/health` (or `http://YOUR_SERVER_IP/health`)
- **TradingView webhook URL**: `http://YOUR_SERVER_IP/webhook` (TradingView allows only port 80 for HTTP; use HTTPS in production; see below).
- The server uses **FastAPI** with **Uvicorn** (async, fast).

---

## Usage

### TradingView alerts

1. In TradingView, create an alert and set **Webhook URL** to:
   - Local test: use a tunnel (e.g. ngrok: `https://xxxx.ngrok.io/webhook`).
   - Production: `https://your-domain.com/webhook` or `https://your-vps-ip:5000/webhook` (if you put a reverse proxy in front).

2. **Message** in the alert should be valid JSON. The bot accepts flexible fields. Example for RSI:

```json
{
  "symbol": "{{ticker}}",
  "timeframe": "15",
  "trigger": "RSI",
  "close": "{{close}}",
  "rsi": "28.5",
  "time": "{{timenow}}"
}
```

Example for MACD / strategy:

```json
{
  "symbol": "{{ticker}}",
  "timeframe": "1h",
  "trigger": "MACD",
  "close": "{{close}}",
  "side": "{{strategy.order.action}}",
  "time": "{{timenow}}"
}
```

Supported fields: `symbol`/`ticker`/`asset`, `timeframe`/`interval`, `trigger`/`indicator` (RSI/MACD), `close`/`price`, `rsi`, `macd`, `side`/`action`/`strategy_order_action`, `time`/`timestamp`.

### Coinglass

If `COINGLASS_API_KEY` is set and `ENABLE_COINGLASS_LIQUIDATION=true`, the bot polls liquidation history every `COINGLASS_POLL_INTERVAL` seconds (minimum 60). When 1h total liquidation for a configured symbol exceeds `LIQUIDATION_SPIKE_USD`, it sends a liquidation alert to Telegram.

---

## Demo: proving alerts flow to Telegram

1. Start the bot (`python main.py`) and ensure `.env` has a valid `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
2. Send a test webhook with curl:

```bash
curl -X POST http://localhost:5000/webhook -H "Content-Type: application/json" -d "{\"symbol\": \"BTCUSDT\", \"timeframe\": \"15m\", \"trigger\": \"RSI\", \"rsi\": \"28\", \"close\": \"42000\", \"time\": \"2025-03-08T12:00:00Z\"}"
```

3. Check your Telegram chat: you should see a message with asset, timeframe, trigger RSI, values, and recommendation **Buy** (RSI &lt; 30).

For a **screen recording**, record: (1) opening the project, (2) running `python main.py`, (3) running the curl command, (4) showing the Telegram notification.

---

## Deployment (VPS / 24/7)

### Option A: Direct on VPS

```bash
# On the VPS (e.g. Ubuntu)
sudo apt update && sudo apt install -y python3-venv python3-pip
cd /opt/Telegram_bot   # or your path
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# Copy and edit .env
nohup .venv/bin/python main.py >> bot.log 2>&1 &
# Or use systemd (see below)
```

**HTTPS**: Use a reverse proxy (nginx/caddy) with SSL and proxy to `http://127.0.0.1:5000`. Set TradingView webhook to `https://yourdomain.com/webhook`. See **"VPS & TradingView setup"** below for full steps.

### Option B: Docker

```bash
docker compose up -d
```

The compose file builds the image and runs the app; ensure `.env` is in the same directory. For production, expose port 5000 only through a reverse proxy with HTTPS.

### systemd unit (optional)

Create `/etc/systemd/system/telegram-signals-bot.service`:

```ini
[Unit]
Description=Telegram Trading Signals Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/opt/Telegram_bot
EnvironmentFile=/opt/Telegram_bot/.env
ExecStart=/opt/Telegram_bot/.venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-signals-bot
sudo systemctl start telegram-signals-bot
sudo systemctl status telegram-signals-bot
```

---

## VPS & TradingView setup (step-by-step)

### Part 1: Make the webhook reachable (VPS/domain + HTTPS)

Your bot runs **inside the VPS** on port 5000. TradingView is on the **internet**, so it needs a **public URL** to call. Two options:

#### Option 1: Only VPS IP (quick test, HTTP)

- On the VPS: run the bot (`python main.py` or Docker), and open **port 80** in the firewall.
- **Webhook URL for TradingView:** `http://YOUR_VPS_IP/webhook` (no port; TradingView allows only port 80 for HTTP)
  Example: VPS IP = `203.0.113.50` → URL = `http://203.0.113.50/webhook`
- **Limitation:** HTTP only (no HTTPS). Some networks or TradingView may prefer HTTPS. Good for testing.

**Steps on VPS (Linux):**

```bash
# Open port 80 (example for ufw)
sudo ufw allow 80
sudo ufw reload
# Check: from your PC browser open http://YOUR_VPS_IP/health — should show {"status":"ok",...}
```

#### Option 2: Domain + HTTPS (recommended for production)

You need: a **domain** (e.g. `signals.yourdomain.com`) pointing to your **VPS IP**, and a **reverse proxy with SSL** on the VPS so that `https://signals.yourdomain.com/webhook` forwards to your bot on port 5000.

**Step 1 – Domain:** Buy a domain (Namecheap, GoDaddy, Cloudflare, etc.) or use a subdomain you already have. Add an **A record**: name = `signals` (or `webhook` or `@`), value = **your VPS public IP**. Wait a few minutes for DNS to update.

**Step 2 – VPS: install Nginx and Certbot (Ubuntu/Debian):**

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

**Step 3 – Get free SSL certificate:**

```bash
sudo certbot --nginx -d signals.yourdomain.com
# Follow prompts (email, agree). Certbot will configure HTTPS for you.
```

**Step 4 – Nginx config for the webhook:**  
Create a file e.g. `/etc/nginx/sites-available/webhook-bot`:

```nginx
server {
    listen 80;
    server_name signals.yourdomain.com;
    return 301 https://$server_name$request_uri;
}
server {
    listen 443 ssl;
    server_name signals.yourdomain.com;
    ssl_certificate     /etc/letsencrypt/live/signals.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/signals.yourdomain.com/privkey.pem;

    location /webhook {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location /health {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
    }
}
```

Enable and reload:

```bash
sudo ln -s /etc/nginx/sites-available/webhook-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

**Step 5 – Your webhook URL:**  
`https://signals.yourdomain.com/webhook`  
Use this in TradingView. Your bot must be running on the same VPS (e.g. `python main.py` or Docker) on port 5000.

---

### Part 2: TradingView – kahan se kya karna hai

TradingView **khud scan nahi karta**; tum **alerts** banaoge. Jab condition hit hogi, TradingView **webhook URL ko request bhejega** → tumhara bot Telegram pe message karega.

**Step 1 – TradingView kholo**  
Browser me jao [tradingview.com](https://www.tradingview.com), login karo.

**Step 2 – Chart kholo**  
Jis pair pe alert chahiye (e.g. BTCUSDT, EURUSD) wo chart open karo. Timeframe select karo (5m, 15m, 30m, 1h).

**Step 3 – Alert create karo**  
- Chart pe **right-click** → **Add alert on …**  
  **ya**  
- Top menu me **Alerts** (clock icon) → **Create Alert**.  
- **Condition:** "RSI crosses below 30" / "MACD crossover" / ya apna strategy choose karo.  
- **Options:** Alert name (e.g. "BTC RSI 15m"), **Expiration** (e.g. No expiration).

**Step 4 – Webhook URL daalo**  
- **Notifications** section me **Webhook URL** field dikhega.  
- Paste: `https://signals.yourdomain.com/webhook` (ya `http://VPS_IP/webhook` agar Option 1 use kar rahe ho).  
- **Message** field me **JSON** daalna hai (plain text nahi). Example for **RSI**:

```json
{
  "symbol": "{{ticker}}",
  "timeframe": "15",
  "trigger": "RSI",
  "close": "{{close}}",
  "rsi": "{{plot_0}}",
  "time": "{{timenow}}"
}
```

Agar **MACD / strategy** se alert ho:

```json
{
  "symbol": "{{ticker}}",
  "timeframe": "1h",
  "trigger": "MACD",
  "close": "{{close}}",
  "side": "{{strategy.order.action}}",
  "time": "{{timenow}}"
}
```

**Step 5 – Save**  
**Create** / **Save** click karo. Jab bhi condition hit hogi, TradingView isi URL pe POST karega → bot Telegram pe message bhej dega.

**Note:** `{{ticker}}`, `{{close}}`, `{{timenow}}` TradingView ke variables hain; wo automatically replace ho jayenge. RSI value ke liye alert condition me "plot" choose karo aur message me `{{plot_0}}` use karo (ya jo plot number RSI ka ho).

---

## Project structure

```
Telegram_bot/
├── main.py              # Entry point: starts webhook server + Coinglass poller
├── config.py            # Loads settings from .env
├── webhook_server.py    # FastAPI app: /webhook (TradingView), /health
├── signal_processor.py  # RSI/MACD/liquidation logic and Buy/Sell tag
├── telegram_notifier.py # Format and send Telegram messages; throttling
├── coinglass_poller.py  # Poll Coinglass once per minute; liquidation spikes
├── requirements.txt
├── .env.example
├── .env                 # Your config (do not commit)
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Error handling and anti-spam

- **Cooldown**: Same asset + trigger type won’t send again within `ALERT_COOLDOWN_SECONDS`.
- **Rate limit**: No more than `MAX_ALERTS_PER_MINUTE` alerts in a rolling minute.
- **Coinglass**: Poll interval is at least 60 seconds to respect API limits.
- **Telegram**: Failures are logged; no retry loop to avoid burst spam. Check logs if alerts stop.
- **Webhook**: Invalid or missing payload returns 400; processing errors return 500; throttle returns 200 with "alert skipped".

---

## License

Use and modify as needed for your project.
