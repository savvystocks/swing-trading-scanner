# Vultr Deploy - Flow WebSocket Worker

All commands runnable from PowerShell. Assumes you have SSH access to Vultr via key.
Replace `VULTR_IP` with your box's IP.

## One-time setup (run once)

### 1. SSH in and create service user + directories
From PowerShell on your laptop:

```powershell
ssh root@VULTR_IP
```

Then on the Vultr box:
```bash
# Create dedicated user
useradd -m -s /bin/bash flowws

# Install Python + git + websocat (optional, for debugging)
apt update && apt install -y python3 python3-venv python3-pip git

# Create app directory
mkdir -p /opt/flow-ws
chown flowws:flowws /opt/flow-ws

# Create log file
touch /var/log/flow-ws.log
chown flowws:flowws /var/log/flow-ws.log

# Exit back to your laptop
exit
```

### 2. Copy code to Vultr (from PowerShell on laptop)
Adjust the local path to wherever you cloned this repo:

```powershell
# Push source
scp -r "C:\Users\savva\OneDrive\Documents\Swing Trading\src" root@VULTR_IP:/opt/flow-ws/
scp "C:\Users\savva\OneDrive\Documents\Swing Trading\deploy\flow-ws.service" root@VULTR_IP:/etc/systemd/system/
```

### 3. Set up Python venv + secrets (SSH in again)
```powershell
ssh root@VULTR_IP
```

Then on the box:
```bash
# Become flowws user
su - flowws
cd /opt/flow-ws

# Create venv + install deps
python3 -m venv venv
./venv/bin/pip install websocket-client

# Create .env with secrets - REPLACE THE PLACEHOLDERS
cat > .env <<EOF
UNUSUAL_WHALES_TOKEN=06a8d311-3b6b-4620-9b57-809fcc87f488
TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID=YOUR_TELEGRAM_CHAT_ID
WHALE_PREMIUM_MIN=1000000
ALERT_DEDUPE_SECONDS=300
EOF

chmod 600 .env

# Back to root
exit
```

### 4. Enable + start systemd service
```bash
# Set ownership on copied files
chown -R flowws:flowws /opt/flow-ws

# Enable + start
systemctl daemon-reload
systemctl enable flow-ws
systemctl start flow-ws

# Verify it's running
systemctl status flow-ws

# Watch the log live
tail -f /var/log/flow-ws.log
```

You should see:
- `WS open - subscribing to channels`
- `joined channel: flow-alerts`
- `joined channel: news`
- `joined channel: trading_halts`

And a Telegram message: "WS worker started  whale threshold: $1.0M"

## Updating the code

From PowerShell, after pulling new code locally:
```powershell
scp "C:\Users\savva\OneDrive\Documents\Swing Trading\src\ws_worker.py" root@VULTR_IP:/opt/flow-ws/src/
ssh root@VULTR_IP "systemctl restart flow-ws && tail -20 /var/log/flow-ws.log"
```

## Tuning thresholds

Edit `/opt/flow-ws/.env` to change:
- `WHALE_PREMIUM_MIN` (default $1M) - raise to reduce alert volume, lower to catch more
- `ALERT_DEDUPE_SECONDS` (default 300) - same ticker/strike won't re-alert within this window

After editing, restart:
```bash
systemctl restart flow-ws
```

## Stop / disable

```bash
systemctl stop flow-ws       # stop now
systemctl disable flow-ws    # don't auto-start on boot
```

## Position monitoring

The worker also monitors any open positions you tell it about. When a position
is active, it subscribes to `gex:TICKER` + `net_flow:TICKER` for that ticker and
fires Telegram alerts on:

- **Dealer regime flip** (POSITIVE_PIN <-> NEGATIVE_AMP) - severity depends on
  your side
- **Spot crossing gamma flip strike** - hedging regime change
- **Heavy opposite-side flow** - $2M+ premium 2x+ vs your side = institutions
  positioning against you

### Add a position (from PowerShell on your laptop)

```powershell
# After you've bought, log it:
python "C:\Users\savva\OneDrive\Documents\Swing Trading\scripts\position.py" add NVDA CALL 215 2026-07-02 14.63 --size 30

# Push to Vultr (replace VULTR_IP):
python "C:\Users\savva\OneDrive\Documents\Swing Trading\scripts\position.py" push VULTR_IP
```

Worker auto-detects within 60s and Telegrams "Position monitor: Active: NVDA".

### Remove (after exit)

```powershell
python "C:\Users\savva\OneDrive\Documents\Swing Trading\scripts\position.py" remove NVDA CALL 215
python "C:\Users\savva\OneDrive\Documents\Swing Trading\scripts\position.py" push VULTR_IP
```

### List active

```powershell
python "C:\Users\savva\OneDrive\Documents\Swing Trading\scripts\position.py" list
```

The positions file lives at `/opt/flow-ws/data/positions.json` on the Vultr box.
You can also `ssh` in and `nano` it directly if PS isn't handy.

### One-time setup for position monitoring

Make sure the data dir exists on Vultr:

```bash
mkdir -p /opt/flow-ws/data
chown -R flowws:flowws /opt/flow-ws/data
```

(Already covered if you did the main setup above.)

## Debugging

```bash
# Check service status
systemctl status flow-ws

# Last 50 log lines
tail -50 /var/log/flow-ws.log

# Watch live
tail -f /var/log/flow-ws.log

# Restart
systemctl restart flow-ws

# Test the WS connection manually (requires websocat)
apt install -y websocat
websocat "wss://api.unusualwhales.com/socket?token=$UW_TOKEN"
# Then type:
{"channel":"flow-alerts","msg_type":"join"}
```
