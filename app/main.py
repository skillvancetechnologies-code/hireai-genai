from fastapi import FastAPI

from app.modules.copilot.routes import router as copilot_router


app = FastAPI(
    title="G2 AI Copilot Engine",
    description="Week 3 API for filter and semantic recruiter search.",
    version="0.3.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Simple health check endpoint for local testing."""
    return {"status": "ok"}


app.include_router(copilot_router)
