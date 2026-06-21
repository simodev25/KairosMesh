from fastapi import APIRouter

from app.api.routes import agent_skills, analytics, auth, backtests, benchmark, connectors, evolution, governance, health, portfolio, prompts, runs, trading
from app.api.routes.strategies import router as strategies_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(connectors.router)
api_router.include_router(agent_skills.router)
api_router.include_router(prompts.router)
api_router.include_router(runs.router)
api_router.include_router(backtests.router)
api_router.include_router(benchmark.router)
api_router.include_router(evolution.router)
api_router.include_router(analytics.router)
api_router.include_router(trading.router)
api_router.include_router(portfolio.router)
api_router.include_router(strategies_router)
api_router.include_router(governance.router)
