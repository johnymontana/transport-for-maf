# CLAUDE.md

This file provides context for Claude Code when working on this project.

## Project Overview

TfL Explorer is a London transport conversational assistant. It combines a Microsoft Agent Framework (MAF) agent with Neo4j Agent Memory and Transport for London data. The app has a three-panel UI: chat (left), map/graph tabs (center), and detail panel (right).

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, Microsoft Agent Framework (`agent-framework`), `neo4j-agent-memory[openai,microsoft-agent]`, OpenAI GPT-4o
- **Frontend**: Next.js 14, React 18, TypeScript, Chakra UI v3, Neo4j NVL (`@neo4j-nvl/react`), Mapbox GL JS (`react-map-gl`), Zustand
- **Database**: Neo4j 5 Enterprise with APOC plugin, spatial indexes
- **Package managers**: `uv` for Python (always use `uv` for all Python operations), `npm` for Node.js

## Common Commands

```bash
# Install dependencies
make install                    # Both backend + frontend
cd backend && uv sync           # Backend only
cd frontend && npm install      # Frontend only

# Run dev servers
make dev                        # Both (backend:8000, frontend:3000)
make dev-backend                # Backend only
make dev-frontend               # Frontend only

# Database
make docker-up                  # Start Neo4j
make docker-down                # Stop Neo4j

# Data pipeline
make download-tfl               # Download TfL API data to data/
make load-data                  # Load JSON into Neo4j graph
make data-refresh               # Both

# Tests (always run from backend/)
cd backend
uv run pytest tests/ -m unit                    # Fast unit tests
uv run pytest tests/ -m "unit or integration"   # Unit + integration
uv run pytest tests/e2e/ -m e2e                 # E2E (needs running server)
```

## Project Layout

```
backend/
  app/
    main.py           # FastAPI app, all HTTP endpoints, lifespan management
    agent.py          # MAF agent creation, SSE streaming, system prompt
    config.py         # Settings(BaseSettings) - reads env vars at import time
    memory_setup.py   # MemoryClient lifecycle (global singleton)
    tfl_client.py     # httpx async client for live TfL API
    tools/
      transport.py    # 10 FunctionTools using @tool decorator
  tests/
    conftest.py       # MockGraphExecutor, MockMemoryClient, MockMemory, fixtures
    unit/             # Tests with mocked dependencies (no network/DB)
    integration/      # test_api_endpoints.py (httpx AsyncClient against FastAPI)
                      # test_neo4j_graph.py (real Neo4j via testcontainers)
    e2e/              # Smoke tests against running server
    test_data_pipeline.py  # Download/load script tests

frontend/
  src/
    app/page.tsx                  # Main three-panel layout
    components/chat/ChatPanel.tsx # SSE streaming chat with tool call display
    components/map/TransportMap.tsx  # Mapbox map
    components/graph/TransportGraphView.tsx  # NVL graph viz (dynamic import, no SSR)
    components/graph/MemoryGraphView.tsx     # Memory entity graph
    components/detail/DetailPanel.tsx        # Right sidebar
    components/LineStatusBanner.tsx          # Clickable line badges (loads line graph)
    lib/api.ts        # API client (streamChat SSE generator, REST calls)
    lib/types.ts      # TypeScript interfaces
    lib/graphStyles.ts # TFL_LINE_COLORS, node styling
    store/useAppStore.ts  # Zustand state (selectedStation, mapCenter, graphData, etc.)

scripts/
  download_tfl_data.py  # CLI: --all, --stations, --lines, --routes, --bikepoints
  load_graph.py         # Loads JSON into Neo4j, creates relationships

cypher/
  schema.cypher         # Constraints + indexes (run before loading data)
  sample_queries.cypher # Reference geospatial queries
```

## Key Patterns

### Agent tool return format
Every transport tool in `backend/app/tools/transport.py` returns JSON with:
- `graph_data: {nodes: [...], relationships: [...]}` - consumed by NVL graph
- `map_markers: [{lat, lon, name, type}]` - consumed by Mapbox map

The ChatPanel parses tool_result SSE events and dispatches to the Zustand store, which triggers map/graph updates.

### SSE streaming
`POST /chat` returns Server-Sent Events with event types: `token`, `tool_call`, `tool_result`, `done`, `error`. The frontend processes these via an async generator in `lib/api.ts`.

### Memory integration
The agent uses `neo4j-agent-memory` v0.1.0 with three memory types:
- **Short-term**: conversation messages (auto-stored via `memory.save_message()`)
- **Long-term**: entities (POLE+O schema) + preferences + facts (via `create_memory_tools()`)
- **Reasoning**: tool call traces (via `record_agent_trace()`)

Memory tools (9 total) are created by `create_memory_tools(memory, include_gds_tools=True)` from `neo4j_agent_memory.integrations.microsoft_agent`. This includes 6 core tools + 3 GDS graph algorithm tools (find_connection_path, find_similar_items, find_important_entities).

Key implementation details:
- **Conversation history**: `run_agent_stream()` retrieves full conversation history via `memory.get_conversation(limit=20)` and passes all messages to `agent.run()` for proper multi-turn context.
- **Async memory saving**: Post-response memory operations (saving assistant message + reasoning trace + entity extraction + geocoding + enrichment) run as fire-and-forget `asyncio.create_task()` to avoid blocking the SSE stream.
- **Entity extraction**: Configured with `ExtractionConfig(extractor_type=ExtractorType.LLM)` in `memory_setup.py` to use OpenAI for extraction (spaCy/GLiNER not installed).
- **Entity resolution**: Composite strategy (exact + fuzzy + semantic) configured via `ResolutionConfig` in `memory_setup.py` for entity deduplication.
- **Geocoding**: Location entities auto-geocoded via Nominatim provider. Exposed via `/memory/locations` endpoint.
- **Enrichment**: Wikimedia enrichment runs in background for entity context.
- **GDS integration**: `GDSConfig(enabled=True, fallback_to_basic=True)` in `memory_setup.py` enables graph algorithm tools with Cypher fallback when GDS plugin is not installed.
- **Memory graph export**: `/memory/graph` uses the typed `get_graph()` API instead of custom Cypher.

### Line network graph endpoint
`GET /lines/{id}/graph` returns the full subgraph for a line in a single Cypher query: Station nodes (ordered by sequence), Zone nodes with IN_ZONE relationships, BikePoint nodes with NEAR_STATION relationships, and NEXT_STOP edges between consecutive stations. The frontend `LineStatusBanner` calls this when a line badge is clicked, populating both the map and graph views.

### Config gotcha
`backend/app/config.py` evaluates `os.getenv()` at class definition time (module import), not at Settings instantiation. Tests that need to override defaults must reload the module with `importlib` after patching the environment. They must also patch `dotenv.load_dotenv` to prevent the `.env` file from overriding test values.

### Neo4j spatial queries
Stations and bike points have `location: point({latitude, longitude})` properties with `POINT INDEX` for fast spatial lookups. Queries use `point.distance(node.location, referencePoint) < radius`.

### Frontend graph visualization
`TransportGraphView.tsx` uses a `useState`-based dynamic import pattern (not `next/dynamic`) for reliable NVL initialization. A separate `NvlGraph` sub-component dynamically imports `@neo4j-nvl/react`'s `InteractiveNvlWrapper` in a `useEffect`, then renders it with `d3Force` layout and `mouseEventCallbacks` for zoom/pan/drag/click. `MemoryGraphView.tsx` follows a similar pattern.

### ChatPanel tool result processing
`processToolResult()` in `ChatPanel.tsx` handles both string and already-parsed object results from SSE events. It merges graph data from multiple tool calls (deduplicating nodes by ID), accumulates map markers via `addMapMarkers()`, and auto-zooms the map to fit route coordinates when a `route` key is present.

## Testing Conventions

- Tests use pytest markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.e2e`
- `asyncio_mode = "auto"` in pyproject.toml - no need for `@pytest.mark.asyncio` on every test (but it's used for clarity)
- Unit tests mock the memory client layer using `MockMemoryClient` and `MockMemory` from `conftest.py`
- API integration tests use `httpx.AsyncClient` with `ASGITransport` against the FastAPI app
- Neo4j integration tests use the `neo4j_config` fixture (env vars or testcontainers)
- E2E tests make real HTTP calls to `BACKEND_URL` (default `http://localhost:8000`)
- Mock the global `tfl_client` in `app.main` directly when testing disruption endpoints

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEO4J_URI` | Yes | `bolt://localhost:7687` | Neo4j connection URI |
| `NEO4J_USERNAME` | Yes | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | Yes | `password` | Neo4j password |
| `OPENAI_API_KEY` | Yes | - | OpenAI API key (for agent + embeddings) |
| `NEXT_PUBLIC_MAPBOX_TOKEN` | Yes | - | Mapbox access token (for map) |
| `TFL_APP_KEY` | No | - | TfL API key (raises rate limits) |
| `BACKEND_PORT` | No | `8000` | Backend server port |
| `CORS_ORIGINS` | No | `http://localhost:3000` | Allowed CORS origins |
