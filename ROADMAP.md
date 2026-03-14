# TfL Explorer Roadmap

## Completed Phases

### Phase 1: Project Scaffolding & Data Foundation

All scaffolding and data pipeline work is complete.

**Root project files:**
- `.gitignore`, `.env.example`, `docker-compose.yml` (Neo4j 5 Enterprise + APOC), `Makefile` with all development targets (`install`, `dev`, `docker-up/down`, `download-tfl`, `load-data`, `data-refresh`, `clean`)

**Cypher schema** (`cypher/schema.cypher`):
- Uniqueness constraints on Station.naptanId, Line.lineId, BikePoint.id, Zone.number
- Spatial point indexes on Station.location and BikePoint.location
- Text index on Station.name for fuzzy search

**Data download** (`scripts/download_tfl_data.py`):
- Downloads stations (paginated by mode), lines (with official TfL colors), route sequences (per line), and bike points from the TfL Unified API
- CLI flags: `--all`, `--stations`, `--lines`, `--routes`, `--bikepoints`
- Optional `TFL_APP_KEY` for higher rate limits

**Graph loading** (`scripts/load_graph.py`):
- Batch-loads stations with `point()` coordinates, lines with colors, bike points with dock counts
- Creates relationship types: `ON_LINE` (with sequence), `NEXT_STOP` (ordered chains from route data), `NEAR_STATION` (bike points within 500m via spatial query), `INTERCHANGE_WITH` (stations within 100m), `IN_ZONE`
- Prints summary counts after loading

**Sample queries** (`cypher/sample_queries.cypher`):
- 7 reference queries: nearest stations, bounding box, shortest route, line stations, bike availability, interchanges, zone station counts

---

### Phase 2: Backend - FastAPI + MAF Agent

The full backend is implemented and functional.

**Configuration** (`backend/app/config.py`):
- `Settings(BaseSettings)` loading Neo4j, OpenAI, TfL, Mapbox, and server config from environment variables with sensible defaults

**Memory lifecycle** (`backend/app/memory_setup.py`):
- Global `MemoryClient` singleton managed via FastAPI lifespan (connect on startup, close on shutdown)
- `create_memory()` factory producing `Neo4jMicrosoftMemory` instances with short-term, long-term, and reasoning memory enabled

**Transport tools** (`backend/app/tools/transport.py`):
- 10 `FunctionTool` implementations using the `@tool` decorator:
  - `find_nearest_stations` - spatial `point.distance()` query
  - `search_station` - fuzzy text match
  - `get_station_details` - full station info with lines, bike points, interchanges
  - `find_route` - `shortestPath` over NEXT_STOP relationships
  - `get_line_stations` - stations on a line in sequence order
  - `find_bike_points` - spatial search for cycle hire docking stations
  - `get_line_status` - live status from TfL API
  - `get_disruptions` - live network disruptions from TfL API
  - `execute_cypher` - read-only Cypher execution with write-query validation
  - `get_graph_schema` - Neo4j schema introspection
- Every tool returns JSON with `graph_data` (nodes/relationships for NVL) and `map_markers` (coordinates for Mapbox)

**TfL API client** (`backend/app/tfl_client.py`):
- Async httpx client with `get_line_status()`, `get_disruptions()`, `plan_journey()`

**Agent** (`backend/app/agent.py`):
- MAF agent with system prompt covering London transport domain knowledge
- Combines memory tools (from `create_memory_tools()`) + transport tools + context provider
- `run_agent_stream()` retrieves full conversation history via `memory.get_conversation()` and passes all messages to `agent.run()` for multi-turn context
- Yields SSE events (token, tool_call, tool_result, done, error)
- Post-response memory operations (save assistant message + record reasoning trace) run asynchronously via `asyncio.create_task()` to avoid blocking the stream
- Entity extraction configured with `ExtractorType.LLM` (OpenAI) instead of spaCy/GLiNER pipeline

**FastAPI server** (`backend/app/main.py`):
- 15 endpoints: SSE streaming chat, sync chat, health check, stations (list/detail/nearby), lines (list/stations/graph), bikepoints/nearby, graph/neighborhood expansion, disruptions, memory context/graph/preferences
- `GET /lines/{id}/graph` returns full line subgraph with Station, Zone, and BikePoint nodes plus NEXT_STOP, IN_ZONE, and NEAR_STATION relationships
- CORS middleware, session management, lifespan management

---

### Phase 3: Frontend - Next.js + Chakra UI + NVL + Map

The full frontend is implemented with all planned components.

**Project setup:**
- Next.js 14, React 18, TypeScript, Chakra UI v3, Neo4j NVL, react-map-gl (Mapbox GL JS), Zustand, react-markdown

**Components:**
- `ChatPanel` - SSE streaming chat with tool call badges, example prompt chips, session management. Parses `graph_data`, `map_markers`, and `route` from tool results. Merges graph data from multiple tool calls, accumulates map markers, and auto-zooms to routes.
- `TransportMap` - Mapbox GL map with station markers (sized by zone), dynamic markers from agent responses, GeoJSON route line rendering, flyTo on store changes
- `TransportGraphView` - Neo4j NVL graph with `d3Force` layout, zoom/pan/drag, click-to-inspect properties panel, click-to-select-station + pan-map, double-click-to-expand via API. Uses `useState`-based dynamic import pattern for reliable NVL initialization.
- `MemoryGraphView` - NVL visualization of conversation entities and relationships from the memory graph
- `DetailPanel` - Context-sensitive right sidebar showing station details (lines, bike points, interchanges) or preferences
- `LineStatusBanner` - Clickable line badges at the top of the layout. Clicking a line fetches its full network graph (stations, zones, bike points) via `GET /lines/{id}/graph` and populates both map markers and transport graph. Clicking again deselects. Selected line highlighted with white outline.

**Shared state** (`useAppStore.ts`):
- Zustand store with selectedStation, selectedLine, mapCenter/Zoom, mapMarkers, routeCoordinates, graphData, mainView, and actions

**Styling** (`graphStyles.ts`):
- TfL line color map (14 lines), node color scheme by type, zone-based node sizing

---

### Phase 4: Integration & Polish (Partially Complete)

**Completed:**
- State synchronization between chat, map, and graph panels via Zustand
  - Agent tool results dispatch `graph_data` and `map_markers` to the store
  - Graph node click pans the map to the station location
  - Map marker click updates the detail panel
  - Multiple tool results merge graph data and accumulate markers
  - Route results auto-zoom map to fit route bounds
- Interactive line network exploration via `LineStatusBanner`:
  - Click a line badge to load its full subgraph (stations, zones, bike points) into map + graph
  - `GET /lines/{id}/graph` backend endpoint returns ready-to-render graph data
  - Click again to deselect; selected line highlighted with white outline
- Full conversation history passed to agent for multi-turn context (`memory.get_conversation()`)
- Async post-response memory saving (fire-and-forget `asyncio.create_task`)
- LLM-based entity extraction (replaced spaCy/GLiNER pipeline with `ExtractorType.LLM`)
- Bounded `shortestPath` queries (`*..50`) to eliminate Neo4j performance warnings
- Transport graph improvements: d3Force layout, zoom/pan/drag, properties panel, node expansion, legend
- README.md with architecture, setup guide, API reference, and testing docs
- CLAUDE.md with codebase context for AI-assisted development

**Completed (added beyond original plan):**
- Comprehensive test suite with 80+ tests across all tiers:
  - Unit tests for config, TfL client, transport tools, agent, and memory setup
  - Integration tests for all FastAPI endpoints (httpx AsyncClient) and Neo4j graph operations (testcontainers)
  - E2E smoke tests against a running server
  - Data pipeline tests for download and load scripts
- `pyproject.toml` test configuration with markers (`unit`, `integration`, `e2e`) and `asyncio_mode = "auto"`

---

## Remaining Work

### Phase 4 Items Not Yet Completed

#### 4.1 Full-Stack Docker Compose

Add Dockerfiles and docker-compose services for the backend and frontend so the entire application can be started with a single `docker compose up`.

- `backend/Dockerfile` - Python image with uv, installs deps, runs uvicorn
- `frontend/Dockerfile` - Node image, builds Next.js, runs in production mode
- Update `docker-compose.yml` with `backend` and `frontend` services, depends_on Neo4j, environment variable pass-through

#### 4.2 Map-to-Graph Bidirectional Highlighting

Currently graph click pans the map, but map click does not highlight the corresponding node in the graph view. Add bidirectional highlighting:
- Map marker click -> dispatch to store -> NVL `selectedNodeIds` prop highlights the node
- Add visual indicator (pulse/glow) on the selected node in both views

#### 4.3 Route Visualization on Map

The `find_route` tool returns station coordinates in the path, but the map route line rendering (GeoJSON LineString) may need polish:
- Draw the route as a colored polyline matching the line color
- Show intermediate station markers along the route
- Handle multi-line routes with different colors per segment

---

## Future Ideas

### Enhanced Agent Capabilities

**Journey planner integration** - The `plan_journey` TfL API client method exists but is not yet exposed as an agent tool. Add a `plan_journey` tool that calls the TfL Journey Planner API and returns step-by-step directions with mode changes, walking segments, and estimated times. Overlay the full journey path on the map.

**Real-time arrivals** - Add a `get_arrivals(station_id)` tool that calls `GET /StopPoint/{id}/Arrivals` for live train arrival times. Display as a departures board in the detail panel.

**Accessibility-aware routing** - Use the step-free access data from TfL to offer routes that avoid stairs. Integrate with memory preferences so the agent remembers "I need step-free access" and automatically filters routes.

**Multi-modal journey planning** - Combine tube, bus, cycle hire, and walking into a single journey. Show each leg with the appropriate icon and color on the map.

**Natural language place resolution** - Instead of requiring coordinates for spatial queries, integrate a geocoding service (Mapbox Geocoding API or OpenAI function calling) to resolve "near Covent Garden" to coordinates automatically.

### Frontend Improvements

**Responsive/mobile layout** - The three-panel layout is desktop-first. Add a mobile layout with bottom sheet chat, full-screen map, and swipeable panels. Collapse side panels on smaller screens.

**Dark mode** - Chakra UI v3 color mode is wired up but the map and graph styles may need dark-mode variants. Add dark Mapbox style and adjusted NVL colors.

**Route animation** - Animate a dot traveling along the route path on the map to visually communicate the journey direction and stops.

**Station search autocomplete** - Add a search bar with typeahead that queries the `/stations` endpoint or uses the Neo4j text index for fuzzy matching. Show results in a dropdown with line indicators.

**Favorites and recent stations** - Let users star stations. Persist via the agent's memory preference system ("Remember my home station is King's Cross"). Show favorites as quick-access chips.

**Graph layout options** - Add a toggle between force-directed layout (current) and geographic layout (stations positioned by lat/lon coordinates). The geographic layout would make the graph a stylized tube map.

### Data & Backend Enhancements

**Bus network** - Extend the data pipeline to include bus stops and routes. The TfL API supports bus mode via the same endpoints. This would add ~19,000 bus stops and ~700 bus routes.

**Timetable data** - Load schedule data for each line to answer "When is the last Northern Line train?" or "How frequent is the Victoria Line on Sundays?"

**Historical disruption tracking** - Store disruptions in Neo4j with timestamps to enable "Was the Northern Line disrupted last week?" queries and disruption frequency analytics.

**Incremental data refresh** - Currently `data-refresh` reloads everything. Add incremental updates that only refresh bike point availability (changes frequently) and line status without reloading the full station graph.

**Graph Data Science** - Use Neo4j GDS algorithms to enrich the graph:
  - **Betweenness centrality** on stations to identify critical interchange hubs
  - **Community detection** to find natural station clusters
  - **Shortest path with weights** using distance or travel time
  - Expose these as additional agent tools ("Which are the most important interchange stations?")

### Memory & Personalization

**User profiles** - Associate memory with authenticated users (currently session-based). Persist preferences and conversation history across devices.

**Commute learning** - After a few conversations, the agent could learn daily commute patterns and proactively check for disruptions on the user's usual route.

**Entity linking** - When the agent mentions stations, automatically create knowledge graph links between the user's mentioned entities and the transport graph. Enable queries like "Show me all stations I've asked about."

**Memory visualization improvements** - Enhance the Memory Graph tab with:
  - Timeline view of conversation messages
  - Preference cards with edit/delete
  - Entity relationship map showing how mentioned places connect

### DevOps & Deployment

**CI/CD pipeline** - GitHub Actions workflow running unit tests on push, integration tests with Neo4j testcontainers on PR, and E2E tests on merge to main.

**Cloud deployment** - Deployment targets:
  - Neo4j Aura (managed Neo4j) instead of local Docker
  - Backend on Railway, Fly.io, or Cloud Run
  - Frontend on Vercel
  - Add `NEXT_PUBLIC_API_URL` environment variable for the deployed backend URL

**Monitoring & observability** - Add structured logging, request tracing (OpenTelemetry), and a Grafana dashboard for API latency and agent tool usage metrics.

**Pre-built data snapshot** - Commit a compressed data snapshot to the repo (or host on a CDN) so the demo works without calling the TfL API. Add a `make load-snapshot` target.

### Developer Experience

**Leaflet fallback** - Add an optional Leaflet-based map component that works without a Mapbox token. Auto-detect based on whether `NEXT_PUBLIC_MAPBOX_TOKEN` is set.

**Storybook** - Add Storybook for the UI components (ChatPanel, DetailPanel, LineStatusBanner) with mock data for isolated development.

**Frontend tests** - Add Jest + React Testing Library tests for components (ChatPanel message rendering, store actions, API client parsing). Add Playwright E2E tests for the full user flow.

**API documentation** - The FastAPI auto-generated Swagger docs exist at `/docs`. Add more detailed descriptions, example responses, and group endpoints by tag.
