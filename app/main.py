from fastapi import FastAPI

from app.modules.copilot.routes import router as copilot_router
from app.modules.explain.routes import router as explain_router
from app.modules.parser.routes import router as parser_router


app = FastAPI(
    title="HireAI GenAI Service",
    description="Resume parsing, recruiter copilot, and explainable scoring APIs.",
    version="0.4.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Simple health check endpoint for local testing."""
    return {"status": "ok"}


app.include_router(parser_router)
app.include_router(copilot_router)
app.include_router(explain_router)
