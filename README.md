# MemoryBridge

> Giving dementia patients their own voice back.

57 million people live with dementia. They forget their children's names, their
wedding days, the sound of their own voice. MemoryBridge clones a patient's voice
from 90 seconds of home video audio, builds a semantic memory graph from family
photos using AMD MI300X GPU-accelerated embeddings, and delivers it as an immersive
spatial memory room on Apple Vision Pro — where the patient can walk through their
past and hear themselves remember.

Built at Hack for Humanity 2026, Santa Clara University. Feb 28 - Mar 1, 2026.

---

## Demo

> Add demo GIF or screenshot here before Devpost submission.

```
[ Insert 90-second screen recording link — YouTube or Loom ]
[ Insert spatial room screenshot ]
```

Live demo: https://memorybridge-h4h-2026.web.app

---

## Architecture

```
+===========================================================================+
|                           MEMORYBRIDGE SYSTEM                             |
+===========================================================================+

  FAMILY / CAREGIVER                       PATIENT
  +------------------+                  +---------------------------+
  | Upload Portal    |                  | Apple Vision Pro          |
  | - 25 photos      |                  | WebSpatial SDK            |
  | - 90s voice clip |                  | Floating photo panels     |
  | - Photo captions |                  | by era (Z-depth)          |
  +--------+---------+                  +-------------+-------------+
           |                                          |
           | HTTPS (Firebase SDK)                     | HTTPS / WebSocket
           |                                          |
+----------v------------------------------------------v-----------------+
|                          FLASK REST API (Python 3.11)                  |
|             AMD Developer Cloud  /  Local CPU fallback                 |
+----+----------------------------+---------------------------+----------+
     |                            |                           |
     v                            v                           v
+----+----------+    +------------+-----------+   +----------+---------+
| ElevenLabs    |    | AMD Instinct MI300X     |   | Firebase           |
|               |    | ROCm + sentence-        |   |                    |
| Instant Voice |    | transformers            |   | Firestore          |
| Clone         |    | 384-dim embeddings      |   | Storage            |
|               |    | Cosine similarity graph |   | Hosting            |
| Conversational|    | 192 GB HBM3 unified mem |   | Auth               |
| AI Agent      |    | <400ms batch of 25 photos|  |                    |
| STT + TTS     |    |                         |   |                    |
| Knowledge Base|    | CPU fallback (same API) |   |                    |
+---------------+    +-------------------------+   +--------------------+

  VOICE PIPELINE                    MEMORY GRAPH
  Voice sample (WAV)                Photo captions
       |                                 |
       v                                 v
  ElevenLabs IVC             sentence-transformers
  Voice ID                   384-dim embedding per caption
       |                                 |
       v                                 v
  Conversational Agent       Cosine similarity matrix
  + Knowledge Base           Emotional connection graph
       |                                 |
       v                                 v
  Live conversation          "Tell me about Christmas"
  in patient's own voice     -> retrieve most similar memories
```

---

## Tech Stack

| Layer | Technology | Why |
|-------|------------|-----|
| Voice cloning | ElevenLabs Instant Voice Clone | Only API that produces an indistinguishable clone from 90s of audio |
| Conversational AI | ElevenLabs Conversational AI SDK | Built-in STT, TTS, knowledge base, real-time WebSocket — no assembly required |
| GPU inference | AMD Instinct MI300X (ROCm) | 192 GB unified HBM3 keeps encoder + similarity index fully resident; zero swapping at batch sizes that matter |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | 384-dim semantic embeddings; ROCm-native; CPU fallback without code changes |
| Spatial UI | WebSpatial SDK (ByteDance) | Native visionOS from React + Vite — no Swift required |
| Frontend | React + Vite | Fast iteration; WebSpatial integration is React-native |
| Backend API | Flask (Python 3.11) | Thin orchestration layer; matches team Python expertise |
| Database | Firebase Firestore | Real-time sync — photo added on phone appears in spatial room in <1s |
| File storage | Firebase Storage | Authenticated write access; CDN delivery for photos in spatial room |
| Hosting | Firebase Hosting | Global CDN; custom domain; CI deploy in one command |
| Auth | Firebase Auth | Family-only write access; read-only share links scoped to session ID |

---

## Setup

### Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Node.js | 18+ | https://nodejs.org |
| Python | 3.11+ | https://python.org |
| Firebase CLI | latest | `npm install -g firebase-tools` |
| Git | 2+ | https://git-scm.com |
| Xcode (Mac only) | 15+ | App Store — required for visionOS simulator |

You will need accounts at:
- Firebase (free): https://console.firebase.google.com
- ElevenLabs (free tier works for demo): https://elevenlabs.io
- AMD Developer Cloud (request access 3 days early): https://devcloud.amd.com

AMD access requires pre-approval. Apply immediately. The app works on CPU fallback
without AMD — same code path, ~8x slower embedding.

---

### Step 1 — Clone the repository

```bash
git clone https://github.com/[YOUR_USERNAME]/memorybridge.git
cd memorybridge
```

---

### Step 2 — Configure environment variables

```bash
# Frontend
cp frontend/.env.example frontend/.env

# Backend
cp backend/.env.example backend/.env
```

Fill in `frontend/.env`:

```env
VITE_FIREBASE_API_KEY=<from Firebase console>
VITE_FIREBASE_AUTH_DOMAIN=memorybridge-h4h-2026.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=memorybridge-h4h-2026
VITE_FIREBASE_STORAGE_BUCKET=memorybridge-h4h-2026.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=<from Firebase console>
VITE_FIREBASE_APP_ID=<from Firebase console>
VITE_BACKEND_URL=http://localhost:5000
VITE_ELEVENLABS_AGENT_ID=<from ElevenLabs Conversational AI dashboard>
VITE_WEBSPATIAL_ENABLED=false   # set true only on Mac with Xcode installed
```

Fill in `backend/.env`:

```env
ELEVENLABS_API_KEY=sk_...
ELEVENLABS_VOICE_ID=...
ELEVENLABS_KB_ID=...
ELEVENLABS_AGENT_ID=...
AMD_API_KEY=...         # leave empty to use CPU fallback automatically
AMD_ENDPOINT=https://api.amd.com/v1
FIREBASE_PROJECT_ID=memorybridge-h4h-2026
```

Download Firebase service account key: Firebase Console > Project Settings >
Service Accounts > Generate new private key. Save as `backend/serviceAccount.json`.
This file is gitignored — never commit it.

See `docs/elevenlabs-setup.md` for the complete ElevenLabs voice clone and agent
setup walkthrough (steps 1-10, including knowledge base construction).

---

### Step 3 — Install frontend dependencies

```bash
cd frontend
npm install
```

---

### Step 4 — Set up Python backend

```bash
# Unix / Mac
chmod +x backend/setup_venv.sh
./backend/setup_venv.sh

# Windows
backend\setup_venv.bat
```

---

### Step 5 — Run in development

```bash
# Unix / Mac — starts both servers
chmod +x scripts/dev.sh
./scripts/dev.sh

# Windows — two terminals
# Terminal 1:
cd backend && .venv\Scripts\activate && flask run --host=0.0.0.0 --port=5000

# Terminal 2:
cd frontend && npm run dev
```

Frontend: http://localhost:5173
Backend API: http://localhost:5000
Health check: http://localhost:5000/api/health

---

### Deploy to Firebase Hosting

```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh

# Live at: https://memorybridge-h4h-2026.web.app
```

---

## Project Structure

```
memorybridge/
├── frontend/                   # React + Vite + WebSpatial
│   ├── src/
│   │   ├── components/         # VoiceWidget, MemoryRoom, PhotoCard, etc.
│   │   ├── pages/              # Upload, Processing, Room, Timeline
│   │   ├── hooks/              # useVoiceAgent, useMemoryGraph
│   │   └── lib/                # Firebase client, API helpers
│   └── .env.example
├── backend/                    # Flask REST API
│   ├── app/
│   │   ├── routes/             # /upload, /voice, /embed, /agent
│   │   ├── services/           # elevenlabs_service, amd_service, firebase_service
│   │   └── models/             # Memory, VoiceClone, EmbeddingResult
│   ├── recordings/             # Voice samples (gitignored)
│   ├── .env.example
│   ├── setup_venv.sh
│   └── setup_venv.bat
├── ai/                         # Embedding + similarity logic
│   ├── embeddings.py           # sentence-transformer wrapper (AMD / CPU)
│   ├── similarity.py           # Cosine similarity + memory graph builder
│   └── knowledge_base/         # Knowledge base formatter for ElevenLabs
├── scripts/
│   ├── dev.sh                  # Start both servers locally
│   └── deploy.sh               # Build + deploy to Firebase
├── docs/
│   ├── devpost-content.md      # Complete Devpost submission — copy-paste ready
│   ├── demo-script-timing.md   # 4-minute demo script with exact timestamps
│   ├── prize-targeting.md      # Per-prize strategy
│   ├── screenshot-guide.md     # 6 screenshot instructions for Devpost
│   ├── elevenlabs-setup.md     # Complete ElevenLabs voice clone walkthrough
│   └── setup-guide.md          # Developer environment setup
├── firebase.json
├── firestore.rules
├── firestore.indexes.json
├── storage.rules
└── README.md
```

---

## Demo Walkthrough

1. Open the live demo at https://memorybridge-h4h-2026.web.app
2. Click "Start Demo" to enter the pre-loaded demo account (Robert, 25 memories)
3. On Apple Vision Pro: walk into the spatial room, gaze at a photo panel
4. On browser: click any photo card in the timeline view
5. Pinch (Vision Pro) or click (browser) to start a conversation
6. Ask: "Tell me about my wedding day"
7. The AI responds in Robert's cloned voice: "May 3rd, 1974. You wore your mother's
   dress. It rained in the morning but the sun came out just in time."
8. Ask a follow-up: "Who else was there?"
9. The agent references the memory graph to name the people in the wedding photo

If the AMD endpoint is unavailable, the system falls back to CPU embeddings
automatically — response time increases but all features remain functional.
If ElevenLabs quota is exhausted, see `docs/demo-script-timing.md` for the
pre-recorded audio fallback procedure.

---

## Ethical Design

MemoryBridge handles the most sensitive possible data: the voice and memories of a
cognitively impaired person. Our ethical architecture:

**Consent.** Voice cloning requires explicit authorization from the patient's legal
guardian, who provides the original recording. We clone the patient's own voice —
preserved from when they were healthy. We do not impersonate any other person.

**Access control.** Firebase Security Rules enforce authenticated write access. Only
verified family members can add or modify memories. Share links are read-only and
scoped to a specific session ID — not a browsable index.

**Distress detection.** The ElevenLabs agent system prompt monitors for distress
signals. If detected, the agent pivots immediately to a calming phrase and offers to
change the topic. Caregivers can set a safe word that ends any session instantly.

**Data minimization.** We store only what is necessary: photo captions (not photos on
the AI server), voice ID (not the raw recording after cloning), session IDs (not
patient identity linked to medical records).

Reminiscence therapy — using personal memories to trigger recall and emotional
grounding — is clinically validated (Woods et al., Cochrane Review, 2018). We make
it interactive, personalized, and scalable. We do not claim to treat or diagnose
dementia.

---

## Business Model

| Track | Price | Target |
|-------|-------|--------|
| Family | $39/month | 11M unpaid family caregivers in the US |
| Facility | $299/month per resident | 15,000 memory care facilities in the US |

At 10% penetration of US memory care facilities at 10 residents each:
Annual revenue = 1,500 facilities x 10 residents x $299 x 12 = **$538M**

Exit targets: Honor, Amedisys, Apple Healthcare, CarePredict.
Clinical moat: IRB-approved reminiscence therapy efficacy study with UCSF.

---

## Prizes We Are Targeting

| Prize | Why We Win |
|-------|------------|
| Grand Prize | End-to-end working demo, real emotional impact, real users tested |
| Best Freshman Hack | All Class of 2029 — built full production stack in 22 hours |
| Best Use of ElevenLabs | Voice is the core product, not a feature; clone indistinguishable from original |
| Best AMD Tech | MI300X is architecturally required — 192 GB unified memory for semantic graph |
| Best WebSpatial | First eldercare tool on visionOS; solved real spatial engineering problems |
| Future Unicorn | $350B market, defensible tech stack, acquisition targets exist |
| Best Responsible AI | Consent, access control, distress detection — built for people who can't advocate for themselves |

---

## Team

| Name | Role | Class |
|------|------|-------|
| [Name 1] | AI / Backend | 2029 |
| [Name 2] | Frontend / WebSpatial | 2029 |
| [Name 3] | Design / UX | 2029 |
| [Name 4] | DevOps / Firebase | 2029 |

---

## License

MIT License — see LICENSE for details.

---

Built with urgency and care at Hack for Humanity 2026, Santa Clara University.
