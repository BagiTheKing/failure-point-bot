# failure-point-bot

The automated pipeline behind **The Point of Failure**, a YouTube channel about
engineering and industrial disasters: the structure, machine or plant that
failed, the exact part that broke, the warning that was missed, and what it
cost.

It researches each story from Wikipedia, writes the script with free LLM
tiers, narrates it locally (Kokoro), builds maps, archival imagery, cast cards
and thumbnails, and uploads to YouTube on a schedule. No API key or token ever
lives in this repository: everything comes from GitHub Actions secrets.

## What runs, and when

| Workflow | Schedule (UTC) | What it does |
|---|---|---|
| `daily_publish.yml` | manual only | One standalone Short from the topic pool (`src/topics.py`). Each long video already brings its own highlight Short |
| `weekly_longform.yml` | Wed 09:00 | Long video, **encore lane**: expands the best-performing Short, else the rotation |
| `weekly_timely.yml` | Tue, Thu, Sat 07:40 | Long video, **news lane**: an engineering failure in this week's news picks a historical failure of the same kind; a quiet week takes this week's anniversary |
| `topic_scout.yml` | daily 07:05 | Researches the next story for each lane ahead of time |
| `rotate_thumbnails.yml` | daily 12:17 | Rotates each long video's thumbnail variants |
| `reconcile_playlist.yml` | Sun 06:00 | Keeps the series playlist complete |
| `tests.yml` | on push | Offline regression tests (`python -m unittest discover tests`) |

**The channel never posts twice within 48 hours** (`src/upload_gate.py`): a
long video, then its highlight Short 48 hours later, then the next long video
48 hours after that. Every publishing workflow checks the channel first and
stands down inside the window; tick `ignore_spacing` on a manual run to
override.

**Scheduled runs are off until you switch them on** (step 5 below), so the
repository does not fail on a timer while secrets are still missing. Every
workflow can also be started by hand from the Actions tab.

## The niche, in code

- `src/formats.py`: the five episode types (THE COLLAPSE, THE BREACH, THE BLAST,
  THE SINKING, THE MACHINE), each with its accent colour, writer brief, tags
  and hashtags.
- `src/topics.py`: about 100 curated disasters with reach ratings and
  anniversary dates. Add topics here. Keep each one a single failure with a
  mechanism a viewer could repeat afterwards.
- `src/failure_news.py`: the news lane's feed (Google News search, no key).
  The live event is only ever a hook: the video tells a settled historical
  failure, and never states or guesses the cause of this week's event.
- Titles follow the winning formula in this niche: **big number + physical
  thing + what failed + consequence** (`STORY_TITLE_RULES` in
  `src/longform_llm.py`).
- Thumbnails lead with the **object** look: the failed thing full frame, its
  number huge (`object_look` in `src/thumb_variants.py`).

## Setup

### 1. YouTube channel and Google Cloud project

1. Create The Point of Failure channel (a Brand Account under your Google
   account is fine).
2. In Google Cloud Console, create a **new project** for this channel. It gets
   its own 10,000 units/day YouTube quota.
3. Enable **YouTube Data API v3**.
4. OAuth consent screen: user type External, add yourself as a test user, then
   set **Publishing status: In production**. In "Testing" the refresh token
   expires every 7 days and uploads start failing with `invalid_grant`.
   Unverified is fine for an app only you use.
5. Credentials: create an OAuth client ID (Desktop app is simplest) and
   download its JSON.

### 2. Refresh token (on your own computer)

```
pip install google-auth-oauthlib
python tools/get_youtube_refresh_token.py path/to/client_secret.json
```

When the browser asks which account or channel, **pick The Point of Failure**, not
your other channel. Keep the printed token private.

### 3. Repository secrets

Settings → Secrets and variables → Actions → **Secrets**. Use exactly these
names (the `_2` you give a key in a provider's dashboard does not matter
here: each repository has its own secrets).

| Secret | Needed? | Where it comes from |
|---|---|---|
| `YT_CLIENT_SECRET_JSON` | **required** | The whole OAuth client JSON from step 1 |
| `YT_REFRESH_TOKEN` | **required** | Step 2 |
| `GEMINI_API_KEY` | **required** (or another writer) | https://aistudio.google.com/apikey. The free quota is per Google Cloud **project**, so create this key in a project the other channel's pipeline does not use |
| `GROQ_API_KEY` | recommended | https://console.groq.com/keys |
| `CEREBRAS_API_KEY` | recommended | https://cloud.cerebras.ai |
| `ZHIPU_API_KEY` | optional | https://z.ai/model-api |
| `OPENROUTER_API_KEY` | optional | https://openrouter.ai/keys |
| `CF_ACCOUNT_ID`, `CF_API_TOKEN` | recommended | Cloudflare Workers AI (FLUX image generation), "Workers AI" token template |
| `WIKIMEDIA_TOKEN` | recommended | https://api.wikimedia.org (higher rate limits for archival images) |
| `PEXELS_API_KEY` | optional | https://www.pexels.com/api/ (stock b-roll) |
| `HF_TOKEN` | optional | https://huggingface.co/settings/tokens (animated hook shot) |
| `GEMINI_API_KEY_2` | optional | A second Gemini key from a **different project** |
| `ANTHROPIC_API_KEY` | optional, paid | Last in the writer chain; leave unset to stay free |

Run **Actions → Check Keys** and **Probe writer keys** to confirm the keys work.

### 4. First video by hand

Run **Long-Form — News Lane** with `skip_upload` ticked for a dry run, and
download the video and thumbnails from the run's artifacts. When it looks
right, run it again without `skip_upload`.

Check the uploaded video in YouTube Studio. If it shows **"Locked (private)"**
or an API policy notice, the Cloud project needs YouTube's API audit (the
"YouTube API Services – Audit and Quota Extension" form). Until it passes, set
`PRIVACY_STATUS: private` in the workflows and publish by hand.

### 5. Turn the schedule on

Settings → Secrets and variables → Actions → **Variables** → New repository
variable: `PIPELINE_ENABLED` = `true`.

## Data branches

The workflows keep state on their own branches. Never merge them into `main`:
`run-cache` (a failed run's progress), `topic-queue` (stories researched
ahead), `thumb-rotation` (thumbnail rotation state and held first comments)
the `preview-*` branches made by the probe workflows, and `samples` (finished
sample videos, kept so no render goes to waste).

## Public repository hygiene

This repository is public, so its Actions logs are public too. Secrets are
masked in logs automatically. Never `print` a token, an OAuth response or a
value derived from a secret, and never commit `client_secret*.json` or a
`.env` (both are in `.gitignore`).
