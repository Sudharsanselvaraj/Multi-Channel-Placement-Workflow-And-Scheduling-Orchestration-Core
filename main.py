import asyncio
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import pytz
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, JSONResponse

sys.path.insert(0, str(Path(__file__).parent))

from guardian import guardian
from app.utils.logger import logger
from config.settings import settings

IST = pytz.timezone(settings.timezone)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    asyncio.create_task(guardian.startup())
    yield
    # Shutdown
    await guardian.shutdown()


app = FastAPI(
    title="Haveloc Guardian",
    description="24/7 Placement Email Monitoring System",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    """UptimeRobot pings this to keep Render alive."""
    return {
        "status": "ok",
        "service": "haveloc-guardian",
        "timestamp": datetime.now(IST).isoformat(),
        "uptime_stats": {
            "total_processed": guardian.stats["total_processed"],
            "shortlists_found": guardian.stats["shortlists_found"],
            "last_check": guardian.stats["last_check"],
        },
    }


@app.get("/status")
async def status():
    """Detailed system status."""
    return {
        "status": "running",
        "user": settings.user_name,
        "monitoring": settings.gmail_address,
        "poll_interval": settings.poll_interval_seconds,
        "stats": guardian.stats,
        "scheduler_jobs": [
            {"id": job.id, "next_run": str(job.next_run_time)}
            for job in guardian.scheduler.get_jobs()
        ],
    }


@app.post("/trigger-check")
async def trigger_check(background_tasks: BackgroundTasks):
    """Manually trigger an email check."""
    background_tasks.add_task(guardian.run_check)
    return {"message": "Email check triggered", "timestamp": datetime.now(IST).isoformat()}


@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    """Handle Telegram bot commands."""
    try:
        data = await request.json()
        message = data.get("message", {})
        text = message.get("text", "").strip().lower()
        chat_id = str(message.get("chat", {}).get("id", ""))

        # Security: only respond to configured chat
        if chat_id != settings.telegram_chat_id:
            return {"ok": True}

        if text == "/status":
            await guardian.send_status()

        elif text == "/check":
            await guardian.run_check()
            await guardian.orchestrator.telegram.send("✅ Manual email check completed.")

        elif text == "/summary":
            await guardian.send_daily_summary()

        elif text == "/events":
            events = guardian.orchestrator.reminder_scheduler.get_upcoming_events()
            if events:
                msg = "📅 *Upcoming Events:*\n\n"
                for ev in events[:10]:
                    msg += f"• {ev.get('company')} — {ev.get('event_type')} | {ev.get('time_str')}\n"
            else:
                msg = "✅ No upcoming events tracked."
            await guardian.orchestrator.telegram.send(msg)

        elif text == "/help":
            help_msg = """
🛡 *Haveloc Guardian Commands*

/status — System health & stats
/check — Force email check now
/summary — Today's placement summary
/events — Upcoming tracked events
/help — This message
""".strip()
            await guardian.orchestrator.telegram.send(help_msg)

    except Exception as e:
        logger.error(f"Telegram webhook error: {e}")

    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Simple status dashboard."""
    stats = guardian.stats
    now = datetime.now(IST).strftime("%d %b %Y, %I:%M %p")

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Haveloc Guardian</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap');
  
  :root {{
    --bg: #0a0a0f;
    --surface: #111118;
    --border: #1e1e2e;
    --accent: #00ff88;
    --accent2: #ff3860;
    --text: #e0e0f0;
    --muted: #555577;
  }}
  
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Syne', sans-serif;
    min-height: 100vh;
    padding: 2rem;
  }}
  
  .header {{
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 2.5rem;
    border-bottom: 1px solid var(--border);
    padding-bottom: 1.5rem;
  }}
  
  .pulse {{
    width: 12px; height: 12px;
    background: var(--accent);
    border-radius: 50%;
    animation: pulse 2s infinite;
  }}
  
  @keyframes pulse {{
    0%, 100% {{ box-shadow: 0 0 0 0 rgba(0,255,136,0.4); }}
    50% {{ box-shadow: 0 0 0 8px rgba(0,255,136,0); }}
  }}
  
  h1 {{ font-size: 1.8rem; font-weight: 800; }}
  h1 span {{ color: var(--accent); }}
  
  .subtitle {{ color: var(--muted); font-size: 0.85rem; font-family: 'JetBrains Mono', monospace; margin-top: 0.25rem; }}
  
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
  
  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
  }}
  
  .card-label {{ font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.1em; font-family: 'JetBrains Mono', monospace; margin-bottom: 0.5rem; }}
  .card-value {{ font-size: 2rem; font-weight: 800; }}
  .card-value.green {{ color: var(--accent); }}
  .card-value.red {{ color: var(--accent2); }}
  
  .identity-block {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem;
  }}
  
  .identity-block h3 {{ font-family: 'Syne', sans-serif; margin-bottom: 1rem; color: var(--accent); }}
  
  .row {{ display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid var(--border); }}
  .row:last-child {{ border-bottom: none; }}
  .row-key {{ color: var(--muted); }}
  .row-val {{ color: var(--text); }}
  
  footer {{ color: var(--muted); font-size: 0.75rem; text-align: center; margin-top: 3rem; font-family: 'JetBrains Mono', monospace; }}
</style>
</head>
<body>

<div class="header">
  <div class="pulse"></div>
  <div>
    <h1>Haveloc <span>Guardian</span></h1>
    <div class="subtitle">24/7 Placement Monitor · {now}</div>
  </div>
</div>

<div class="grid">
  <div class="card">
    <div class="card-label">Status</div>
    <div class="card-value green">LIVE</div>
  </div>
  <div class="card">
    <div class="card-label">Emails Processed</div>
    <div class="card-value">{stats['total_processed']}</div>
  </div>
  <div class="card">
    <div class="card-label">Shortlists Found</div>
    <div class="card-value {'green' if stats['shortlists_found'] > 0 else ''}">{stats['shortlists_found']}</div>
  </div>
  <div class="card">
    <div class="card-label">Events Tracked</div>
    <div class="card-value">{stats['events_tracked']}</div>
  </div>
</div>

<div class="identity-block">
  <h3>🎯 Monitoring Identity</h3>
  <div class="row"><span class="row-key">Name</span><span class="row-val">{settings.user_name}</span></div>
  <div class="row"><span class="row-key">Reg Number</span><span class="row-val">{settings.register_number}</span></div>
  <div class="row"><span class="row-key">Email</span><span class="row-val">{settings.college_email}</span></div>
  <div class="row"><span class="row-key">Poll Interval</span><span class="row-val">{settings.poll_interval_seconds}s</span></div>
  <div class="row"><span class="row-key">Last Check</span><span class="row-val">{stats.get('last_check', 'N/A')}</span></div>
  <div class="row"><span class="row-key">Watching</span><span class="row-val">alerts@haveloc.com · srm@haveloc.com</span></div>
</div>

<footer>Haveloc Guardian v1.0 · Built for Sudharsan S · SRMIST Trichy</footer>

</body>
</html>
"""
    return HTMLResponse(content=html)
