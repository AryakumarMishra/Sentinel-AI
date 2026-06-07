# Sentinel AI — Autonomous GitLab CI/CD Healer

**Built for the Google Rapid Agent Hackathon**

Sentinel AI is an autonomous agent that diagnoses and fixes failed GitLab CI/CD pipelines. It uses **Google ADK (Agent Development Kit)** with a **Gemini 3.1 Flash Lite** model, connected to GitLab via **MCP (Model Context Protocol)** tools to automatically identify root causes, generate patches, and create merge requests — all with human-in-the-loop approval.

## How It Works

```
GitLab Pipeline Failure
        │
        ▼
  ┌─ Webhook / Manual Trigger ───┐
  │  De-duplication check        │  ← Prevents healing the same repo twice
  └──────────┬───────────────────┘
             ▼
  ┌──────────────────────────────┐
  │   ANALYSIS PHASE (Gemini)    │
  │  1. get_failed_jobs          │
  │  2. get_pipeline_logs        │
  │  3. read_repository_files    │
  │  4. Generate JSON patch      │
  └──────────┬───────────────────┘
             ▼
  ┌──────────────────────────────┐
  │   HUMAN-IN-THE-LOOP          │
  │ Review patch → Approve/Reject│
  └──────────┬───────────────────┘
             ▼
  ┌──────────────────────────────┐
  │   DEPLOY PHASE (Direct API)  │
  │  create_branch               │
  │  commit_file_change          │
  │  create_merge_request        │
  └──────────────────────────────┘
```

## Architecture

```
┌──────────────┐     ┌──────────────────────────────────────┐
│   Frontend   │     │            Backend (FastAPI)         │
│  Next.js 15  │     │                                      │
│              │     │  ┌─────────┐  ┌──────────────────┐   │
│  Dashboard   │◄───►│  │ Routes  │  │  Webhook Handler │   │
│  Recovery    │     │  └────┬────┘  └────────┬─────────┘   │
│  Detail      │     │       │                │             │
│  Approve/    │     │       ▼                ▼             │
│  Reject UI   │     │  ┌─────────────────────────┐         │
└──────────────┘     │  │    Healing Service       │        │
                     │  │  (Gemini + ADK Runner)   │        │
                     │  └────────────┬────────────┘         │
                     │               │                      │
                     │               ▼                      │
                     │  ┌──────────────────────┐            │
                     │  │  MCP Tool Subprocess  │           │
                     │  │  (gitlab_mcp.server)  │           │
                     │  └──────────┬───────────┘            │
                     │              │                       │
                     └──────────────┼───────────────────────┘
                                    │
                                    ▼
                          ┌──────────────────┐
                          │  GitLab API v4   │
                          └──────────────────┘
```

### Key Components

| Component | Technology | Role |
|---|---|---|
| **Agent** | Google ADK + Gemini 3.1 Flash Lite | Reasoning, tool orchestration |
| **Backend** | FastAPI + Uvicorn | HTTP API, webhook receiver, state management |
| **Tools** | MCP (Model Context Protocol) over stdio | GitLab operations via subprocess |
| **Frontend** | Next.js 15 (App Router) | Recovery dashboard, approve/reject UI |
| **State** | JSON file-based (`recovery_states/`) | Persists recovery progress & logs |

## Features

- **Autonomous Pipeline Diagnosis** -- Gemini reads failed job logs, traces import chains to find the real bug location, and generates a correct patch
- **Human-in-the-Loop Safety** -- Every patch is held for engineer review before deployment
- **De-duplication** -- Ignores webhook events for repos already being healed (with 15-minute TTL crash guard)
- **Concurrency Throttle** -- Prevents Gemini Free Tier rate-limit hits by serializing healing sessions
- **File Hallucination Defense** -- Verifies every claimed file path exists in the repo via GitLab API before presenting it as a fix
- **Resilient Deploy** -- Direct GitLab API calls (bypasses agent for deploy phase, avoiding MCP instability)
- **Multi-Repository** -- Each recovery session is fully isolated via UUID, independent of project boundaries

## Project Structure

```
sentinel_ai/
├── backend/
│   ├── multi_tool_agent/
│   │   ├── agent.py                 # ADK Agent definition with MCP tools
│   │   ├── main.py                  # FastAPI entrypoint
│   │   ├── utils.py                 # Shared utilities (JSON parsing, file verification)
│   │   ├── api/
│   │   │   ├── routes.py            # Manual trigger, approve/reject, recovery listing
│   │   │   └── webhook.py           # GitLab webhook handler with de-duplication
│   │   ├── gitlab_mcp/
│   │   │   └── server.py            # MCP server exposing GitLab tools
│   │   ├── runtime/
│   │   │   └── adk_runtime.py       # ADK Runner wrapper (execute_agent)
│   │   ├── workflows/
│   │   │   └── pipeline_recovery.py # Recovery state CRUD (JSON file-based)
│   │   └── config/
│   │       └── settings.py          # Environment configuration
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── page.tsx             # Dashboard — recovery list
│       │   └── recovery/[id]/
│       │       └── page.tsx          # Detail page with logs + approve/reject
│       └── lib/
│           └── api.ts               # Frontend API client
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 20+
- A Google AI API key with Gemini access
- A GitLab Personal Access Token (read/write API scope)
- GitLab repository with CI/CD configured

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp multi_tool_agent/.env.example multi_tool_agent/.env
# Edit .env with your GOOGLE_API_KEY, GITLAB_PRIVATE_TOKEN, GITLAB_BASE_URL

# Start server
uvicorn multi_tool_agent.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### GitLab Webhook Configuration

1. In your GitLab project → Settings → Webhooks
2. URL: `https://your-server:8000/api/gitlab-webhook`
3. Secret Token: set `GITLAB_WEBHOOK_SECRET` in your `.env`
4. Trigger: **Pipeline events**
5. Save -- Sentinel AI will now automatically respond to failures

### Manual Trigger

```bash
curl -X POST http://localhost:8000/api/recoveries/manual-trigger \
  -H "Content-Type: application/json" \
  -d '{"project_path": "your-namespace/your-repo", "pipeline_id": 12345, "commit_sha": "main"}'
```

## MCP Tools (GitLab)

The agent uses these GitLab operations via the MCP subprocess:

| Tool | Purpose |
|---|---|
| `get_failed_jobs` | Lists failed jobs for a pipeline |
| `get_pipeline_logs` | Fetches trace logs for a specific job |
| `read_repository_files` | Reads file content from a repository ref |
| `create_branch` | Creates a new branch from a base ref |
| `commit_file_change` | Creates or updates a file on a branch |
| `create_merge_request` | Opens a merge request |

## Safety & Reliability

- **Agent never deploys** -- The analysis phase is read-only (diagnose + patch generation only). Deployment happens via direct API calls after explicit human approval
- **Hallucination guard** -- Every suggested file path is verified against the live GitLab repository before being stored as a proposed fix
- **Crash-tolerant locks** -- Healing de-duplication uses a 15-minute TTL; if the server crashes mid-healing, the lock auto-releases
- **Graceful fallbacks** -- JSON parsing uses three strategies (fenced code block, unlabeled block, brace-counter) to handle Gemini's variable output formatting
- **Prompt engineering** -- Cooperative instruction framing avoids Gemini safety filter refusals that adversarial prompts trigger

## Built With

- [Google ADK](https://google.adk.dev) -- Agent Development Kit
- [Gemini 3.1 Flash Lite](https://ai.google.dev) -- Lightweight reasoning model
- [MCP (Model Context Protocol)](https://modelcontextprotocol.io) -- Standardized tool interface
- [FastAPI](https://fastapi.tiangolo.com) -- Async Python web framework
- [Next.js 15](https://nextjs.org) -- React framework with App Router
- [GitLab API v4](https://docs.gitlab.com/ee/api/) -- REST API for repository operations

## License

Apache License 2.0