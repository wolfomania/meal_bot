# Telegram-to-Notion nutrition logger: full implementation blueprint

**The optimal architecture is a standalone Python bot — not an OpenClaw skill — using Gemini 2.5 Flash Lite as a unified transcription-and-analysis engine, with python-telegram-bot for message handling and the Notion SDK for database writes.** This design eliminates the STT-then-LLM two-step pipeline by sending audio and frames to Gemini in a single multimodal call that returns structured JSON. Total infrastructure cost: **$0–5/month** depending on hosting choice, with near-zero per-request AI cost under the Gemini free tier.

The system flow is simple: user records a circular video note describing their meal → bot downloads the MP4, extracts audio (WAV) and 3–4 keyframes (JPEG) via FFmpeg → sends both to Gemini 2.5 Flash Lite with a structured-output prompt → receives a JSON object with meal name, calories, macros, food items, and meal type → writes the entry to a Notion database. The entire pipeline runs in under 10 seconds.

---

## OpenClaw: powerful but wrong tool for this job

OpenClaw is a **196k-star open-source AI agent framework** (formerly "Clawdbot," renamed January 2026) created by Peter Steinberger. It runs as a self-hosted Node.js gateway on port 18789, connecting 20+ messaging platforms to LLM-powered agents via a skill/plugin system. It has **first-class Telegram integration** (configure a bot token in `openclaw.json` and it handles polling, authentication, group routing) and **community Notion skills** (the `MoikasLabs/openclaw-notion-skill` provides full CRUD including `add-entry` to databases).

Skills are not code plugins — they are **SKILL.md files** containing YAML frontmatter and Markdown instructions injected into the agent's system prompt. The agent reads these instructions and invokes accompanying CLI scripts. Over 5,400 skills exist on ClawHub. You could build a nutrition logger as a skill with a SKILL.md teaching the agent to parse food descriptions and a `notion-cli.js` script to write entries.

**Why standalone wins over OpenClaw for this project:**

- OpenClaw requires Node.js ≥22 plus the full gateway runtime — heavy for a single-purpose bot needing **~256 MB RAM** total
- Every message routes through an LLM conversation, adding latency and token cost even for simple logging
- Video note binary handling (download → FFmpeg → multimodal API) requires custom code regardless — OpenClaw's skill system (text instructions → CLI scripts) doesn't simplify this workflow
- Security concerns are real: Cisco found data exfiltration in third-party skills, and 135,000+ instances were found exposed to the internet
- A standalone Python bot is **~200 lines of code** for the core pipeline and gives you full control

**When OpenClaw makes sense:** if you already run an OpenClaw instance as your personal assistant and want nutrition logging as one of many capabilities. In that case, write a skill that shells out to a Python script handling the FFmpeg + Gemini pipeline, and have the script call the Notion API directly.

## Gemini 2.5 Flash Lite is the unified AI layer

The model (ID: `gemini-2.5-flash-lite`, GA/stable) is the linchpin of this architecture because it accepts **images, audio, and text simultaneously** and returns structured JSON — collapsing what would otherwise be three separate services (STT, vision, nutrition estimation) into one API call.

**Core capabilities for this use case:**

| Capability | Detail |
|---|---|
| Multimodal input | Images (JPEG/PNG), audio (WAV/MP3/OGG/FLAC), video (MP4), text |
| Audio tokenization | **32 tokens per second** of audio (~1,920 tokens/minute) |
| Context window | **1M input tokens**, 65K output tokens |
| Structured output | `response_mime_type: "application/json"` with `response_json_schema` |
| Thinking mode | Off by default (fast); can be enabled for complex reasoning |

**Pricing makes this essentially free for personal use.** The free tier allows **1,000 requests/day** and 250K tokens/minute. At 20 meals/day, you will never exceed free limits. On the paid tier, costs per meal analysis are negligible:

| Component | Tokens | Cost (paid tier) |
|---|---|---|
| 60s audio input | 1,920 tokens | $0.000576 |
| 4 food photo frames | ~1,000 tokens | $0.000100 |
| Text prompt | ~200 tokens | $0.000020 |
| JSON output | ~300 tokens | $0.000120 |
| **Total per meal** | | **$0.0008** |

That is **$0.48 per month at 20 meals/day** — and likely $0 under the free tier.

**API call pattern using the Google GenAI Python SDK:**

```python
from google import genai
from pydantic import BaseModel

class MealEntry(BaseModel):
    meal_name: str
    meal_type: str  # Breakfast, Lunch, Dinner, Snack
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None
    food_items: list[str]
    notes: str

client = genai.Client(api_key=GEMINI_API_KEY)

response = client.models.generate_content(
    model="gemini-2.5-flash-lite",
    contents=[
        audio_part,          # WAV bytes
        *frame_parts,        # 3-4 JPEG images
        NUTRITION_PROMPT,    # System instruction
    ],
    config={
        "response_mime_type": "application/json",
        "response_json_schema": MealEntry.model_json_schema(),
    },
)
```

**Known issue to handle:** Flash Lite occasionally wraps JSON output in markdown code fences (`` ```json ... ``` ``). Strip these in your parsing code as a defensive measure. Test thoroughly during development.

**Why not a separate STT service?** Gemini's native audio understanding for Russian and Ukrainian is rated B+ and B- respectively — comparable to Whisper API quality. More importantly, combining transcription with food extraction in one call eliminates a network round-trip, reduces code complexity, and costs less. If Ukrainian transcription quality proves insufficient, the fallback is OpenAI's GPT-4o Mini Transcribe at **$0.003/minute** ($1.80/month at 20 clips/day) or a fine-tuned Whisper model on HuggingFace run via faster-whisper locally.

## STT alternatives ranked by cost-effectiveness

Should Gemini's built-in audio prove inadequate for Russian/Ukrainian, here are the ranked alternatives:

| Option | Cost/min | 60s latency | Russian | Ukrainian | Integration |
|---|---|---|---|---|---|
| **Gemini 2.5 Flash Lite (native)** | $0.0007 | 2–4s | B+ | B- | ★★★★★ |
| OpenAI GPT-4o Mini Transcribe | $0.003 | 2–5s | B+ | B | ★★★★★ |
| Deepgram Nova-3 | $0.0077 | <1s | B | B- | ★★★★ |
| OpenAI Whisper API | $0.006 | 2–5s | B+ | B- | ★★★★★ |
| Self-hosted faster-whisper (CPU) | $0 | 10–15s | B+ | B- | ★★★★ |
| Google Cloud STT V2 (Chirp) | $0.016 | 1–3s | A- | B+ | ★★★ |

**Deepgram offers $200 in free credit** (no expiration), which covers ~26,000 minutes — over 3 years of personal use. Google Cloud STT V2 has the best Russian/Ukrainian accuracy via the Chirp model but costs 20× more than Gemini. Self-hosted faster-whisper requires **~3 GB RAM** for large-v3 on CPU (int8 quantization) and processes 60-second clips in 10–15 seconds — viable on a Hetzner VPS but not on a PaaS with 256 MB RAM.

## Telegram Bot API: video note specifics

The bot runs on **Bot API 9.5** (March 1, 2026). Video notes are the circular messages users record by holding the camera button.

**Video note technical profile:** MPEG4 container (H.264), **384×384 pixels** square (displayed as circle), maximum **60 seconds** duration, maximum **~12 MB** file size. The bot receives a `VideoNote` object with `file_id`, `file_unique_id`, `length` (diameter), `duration` (seconds), and optional `file_size` and `thumbnail`.

**File download flow:**

```python
# 1. Get file path from file_id
file = await video_note.get_file()  # returns File object with file_path

# 2. Download (URL valid for ≥1 hour)
await file.download_to_drive("video_note.mp4")
# or: bytes = await file.download_as_bytearray()
```

The download URL format is `https://api.telegram.org/file/bot<token>/<file_path>`. Maximum downloadable file size via Bot API is **20 MB**, well above the video note cap.

**Long polling is the right choice** for a personal bot under 50 messages/day. No domain, no SSL certificate, no public IP needed. The bot calls `getUpdates` with a 25–30 second timeout. Use the `filters.VIDEO_NOTE` filter in python-telegram-bot to route only video notes to your handler.

**Recommended library: python-telegram-bot v22.6** (fully async, excellent documentation, `telegram.ext` high-level abstractions). Install with `pip install python-telegram-bot`. The core handler:

```python
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

async def handle_video_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vn = update.message.video_note
    file = await vn.get_file()
    video_bytes = await file.download_as_bytearray()
    # → FFmpeg → Gemini → Notion pipeline
    await update.message.reply_text("✅ Logged: Grilled Chicken Salad — 450 kcal")

app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.VIDEO_NOTE, handle_video_note))
app.run_polling(allowed_updates=["message"])
```

**Bot setup:** Create via @BotFather (`/newbot`), receive token. No special permissions needed for 1:1 private chat — the bot receives all messages automatically. Privacy mode is irrelevant for direct messages.

## Notion API: schema and write pattern

Use the **Notion API v2025-09-03** with the `notion-client` Python SDK (v2.7.0, `pip install notion-client`). Authentication is via an internal integration token (starts with `ntn_` or `secret_`).

**Integration setup:** Create at notion.so/my-integrations → enable "Insert content" capability → share the target database with the integration via the ⋯ → Connections menu. Rate limit is **~3 requests/second** average — irrelevant for personal use.

**Recommended database schema:**

| Property | Type | Purpose |
|---|---|---|
| Meal | `title` | Primary identifier (e.g., "Grilled Chicken Salad") |
| Date | `date` | Meal date/time |
| Calories | `number` | Total kcal |
| Protein (g) | `number` | Grams of protein |
| Carbs (g) | `number` | Grams of carbohydrates |
| Fat (g) | `number` | Grams of fat |
| Meal Type | `select` | Breakfast / Lunch / Dinner / Snack |
| Food Items | `multi_select` | Individual ingredient tags |
| Notes | `rich_text` | Transcript or free-form notes |

**Write pattern:**

```python
from notion_client import Client

notion = Client(auth=NOTION_TOKEN)

def log_meal(entry: MealEntry):
    notion.pages.create(
        parent={"database_id": DATABASE_ID},
        properties={
            "Meal":        {"title": [{"text": {"content": entry.meal_name}}]},
            "Date":        {"date": {"start": date.today().isoformat()}},
            "Calories":    {"number": entry.calories},
            "Protein (g)": {"number": entry.protein_g},
            "Carbs (g)":   {"number": entry.carbs_g},
            "Fat (g)":     {"number": entry.fat_g},
            "Meal Type":   {"select": {"name": entry.meal_type}},
            "Food Items":  {"multi_select": [{"name": f} for f in entry.food_items]},
            "Notes":       {"rich_text": [{"text": {"content": entry.notes}}]},
        }
    )
```

Property names must **exactly match** the database column names. Multi-select options are auto-created if they don't exist (maximum 100 options). Rich text content is capped at 2,000 characters.

## FFmpeg commands: two operations, minimal complexity

**Extract 16kHz mono WAV for STT:**
```bash
ffmpeg -i input.mp4 -vn -ac 1 -ar 16000 -y output.wav
```
A 60-second video note produces a **~1.9 MB WAV**. The `-vn` flag strips video; `-ac 1` forces mono; `-ar 16000` resamples to 16kHz — the standard for all STT engines.

**Extract 4 evenly-spaced frames as JPEG:**
```bash
# For a 30-second video, extract frames at 6s, 12s, 18s, 24s
ffmpeg -ss 6  -i input.mp4 -frames:v 1 -q:v 2 -y frame_01.jpg
ffmpeg -ss 12 -i input.mp4 -frames:v 1 -q:v 2 -y frame_02.jpg
ffmpeg -ss 18 -i input.mp4 -frames:v 1 -q:v 2 -y frame_03.jpg
ffmpeg -ss 24 -i input.mp4 -frames:v 1 -q:v 2 -y frame_04.jpg
```

Place `-ss` before `-i` for fast keyframe seeking. The `-q:v 2` flag produces high-quality JPEG (scale 1–31, lower is better). At 384×384 native resolution, each frame is **~15–30 KB**.

**Python integration uses `asyncio.create_subprocess_exec`** — no third-party FFmpeg library needed:

```python
async def extract_audio(input_path: str, output_path: str):
    proc = await asyncio.create_subprocess_exec(
        'ffmpeg', '-i', input_path, '-vn', '-ac', '1', '-ar', '16000', '-y', output_path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {stderr.decode()[-500:]}")

async def extract_frames(input_path: str, tmpdir: str, duration: float, n: int = 4):
    timestamps = [duration * (i + 1) / (n + 1) for i in range(n)]
    paths = []
    for i, ts in enumerate(timestamps):
        out = f"{tmpdir}/frame_{i:02d}.jpg"
        proc = await asyncio.create_subprocess_exec(
            'ffmpeg', '-ss', str(ts), '-i', input_path,
            '-frames:v', '1', '-q:v', '2', '-y', out,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
        if proc.returncode == 0:
            paths.append(out)
    return paths
```

Use `tempfile.TemporaryDirectory()` as a context manager to ensure automatic cleanup of all intermediate files.

## Hosting: four viable options compared

| Platform | Monthly cost | RAM | ffmpeg | Deploy effort | Best for |
|---|---|---|---|---|---|
| **Oracle Cloud Free** | **$0** | 24 GB (ARM) | ✅ | Medium | Zero-budget, if ARM capacity available |
| **Hetzner CX22** | **€3.79 (~$4.10)** | 4 GB | ✅ | Medium | Best price/performance ratio |
| **Railway Hobby** | **~$5–7** | Flexible | ✅ | Very low | Best developer experience |
| **Fly.io** | **~$4–5** | 256–512 MB | ✅ | Low-medium | Docker-native workflow |

**Oracle Cloud's Always Free tier** is absurdly generous: **4 ARM Ampere OCPUs + 24 GB RAM** for $0/month forever. The catch is ARM instance availability — popular regions frequently have zero capacity. Sign up, convert to pay-as-you-go (still free for free-tier resources, prevents account reclamation), and try less popular regions. If you secure an instance, it runs faster-whisper locally as a fallback STT and has headroom for anything else.

**Hetzner CX22** at €3.79/month gives **2 vCPU + 4 GB RAM + 40 GB NVMe** — massive overkill for a bot but leaves room for self-hosted Whisper, a database, or other projects. Requires manual server management (systemd unit, firewall, updates).

**Railway** is the lowest-friction option. Push to GitHub, set environment variables in the dashboard, done. Nixpacks auto-detects Python and installs ffmpeg. The **$5/month Hobby plan** includes $5 in usage credits; a lightweight bot typically stays within this. No free tier beyond a 30-day trial.

**Fly.io** works well if you're comfortable with Docker. A `shared-cpu-1x` machine with 256 MB RAM costs ~$1.94/month, but add $2/month for a dedicated IPv4 if using webhooks. No free tier for new accounts since October 2024.

**Recommended choice:** Start with **Railway** for fast iteration during development (zero DevOps). Once stable, optionally migrate to **Hetzner** or **Oracle Free** for long-term cost savings. For a bot that just does long polling + occasional FFmpeg + one Gemini API call, even 256 MB RAM on any platform is sufficient.

## Conclusion: the complete execution pipeline

The end-to-end flow for a single meal log takes **5–8 seconds** and costs effectively nothing:

1. User records a video note in Telegram (up to 60s, 384×384 MP4)
2. python-telegram-bot receives the message, downloads the file via `getFile` + `download_as_bytearray`
3. FFmpeg extracts 16kHz mono WAV (~1.9 MB) and 4 JPEG keyframes (~100 KB total) in a temporary directory
4. A single Gemini 2.5 Flash Lite API call receives the audio + frames + a structured-output prompt, returning a `MealEntry` JSON with name, type, calories, macros, and food items
5. The `notion-client` SDK writes the entry to the Notion database
6. Bot replies with a confirmation message showing the logged data

**Key architectural decisions that simplify everything:** using Gemini's native multimodal input eliminates the need for a separate STT service; structured JSON output eliminates response parsing; long polling eliminates SSL/domain setup; and the Notion SDK's `pages.create` is a single function call. The entire bot — including error handling, temp file management, and retry logic — fits in roughly **250 lines of Python**.

The stack: **Python 3.11+ / python-telegram-bot 22.6 / google-genai SDK / notion-client 2.7.0 / ffmpeg (system binary) / asyncio subprocess**. No web framework, no database, no queue — just a long-polling loop that processes video notes as they arrive.