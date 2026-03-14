.PHONY: install install-backend install-frontend dev dev-backend dev-frontend \
       docker-up docker-down download-tfl load-data data-refresh clean

# Install all dependencies
install: install-backend install-frontend

install-backend:
	cd backend && uv sync

install-frontend:
	cd frontend && npm install

# Development servers
dev:
	$(MAKE) -j2 dev-backend dev-frontend

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

# Docker
docker-up:
	docker compose up -d

docker-down:
	docker compose down

# Data pipeline
download-tfl:
	cd scripts && uv run python download_tfl_data.py --all

load-data:
	cd scripts && uv run python load_graph.py

data-refresh: download-tfl load-data

# Cleanup
clean:
	rm -rf data/
	rm -rf frontend/.next
	rm -rf backend/__pycache__
