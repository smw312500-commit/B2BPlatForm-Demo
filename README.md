# B2B Platform Demo

AI agent orchestration demo for an apparel B2B supply-chain scenario.

The demo is separated from the development repository. It runs with demo databases and seed data so portfolio reviewers can inspect the platform without local production data.

## Components

- `플랫폼agent`: central orchestrator, report channels, dispatch planner, insight dashboard.
- `라벨agent`: care-label producer agent.
- `옷감agent`: fabric producer agent.
- `지퍼단추agent`: zipper/button producer agent.
- `물류agent`: logistics company agent.
- `demo_data/four_year_supply_chain`: four-year synthetic supply-chain dataset for insight and dispatch scenarios.

## Demo Mode

Each backend has `backend/.env.demo` with:

- `DEMO_MODE=1`
- empty secrets
- demo-only database names such as `platform_demo` and `company_label_demo`

On first EXE launch, the launcher copies `backend/.env.demo` to `backend/.env` when `.env` does not exist. The backend then creates the MySQL database if needed and seeds demo data. Re-running does not keep duplicating the July seed data.

## Local Prerequisites

- MySQL running on `127.0.0.1:3306`
- Python installed and available as `py` or `python`
- Backend packages installed per agent `backend/requirements.txt`
- Node is only needed when rebuilding frontends. Built frontend assets are already included.

## Suggested Start Order

1. `플랫폼agent/PlatformAgent.exe`
2. `물류agent/LogisticsAgent.exe`
3. `라벨agent/LabelAgent.exe`
4. `옷감agent/FabricAgent.exe`
5. `지퍼단추agent/ZipperButtonAgent.exe`

Ports:

- Platform: `http://localhost:8000`
- Label: `http://localhost:8001`
- Fabric: `http://localhost:3000`
- Zipper/Button: `http://localhost:5175`
- Logistics: `http://localhost:3001`

## Security Notes

This repository must not include real `.env` files, API keys, database passwords, `.claude`, virtual environments, or local-only logs. API-backed insight can be enabled locally by filling `OPENAI_API_KEY` in each generated `.env`, but the committed demo works with seed/mock data.
