"""Main FastAPI application entrypoint for Jarvis AI COO Skill Registry."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.core.tool_registry import ToolValidationError
from app.db.base import Base
from app.db.session import engine, AsyncSessionLocal
from app.db.seed import seed_fixtures
from app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables and seed fixtures
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await seed_fixtures(session)

    yield

    # Clean up database resources
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Organization-Scoped Skill Registry Vertical Slice for Jarvis AI COO",
    version="0.1.0",
    lifespan=lifespan,
)

# Include API Router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["Health"], summary="System health probe")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
    }


# Explicit and useful error handlers for input validation and tool safety
@app.exception_handler(ToolValidationError)
async def tool_validation_exception_handler(request: Request, exc: ToolValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "ToolValidationError",
            "message": str(exc),
            "detail": "Requested tools violated security sandboxing policy. Destructive tools are forbidden.",
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        field = " -> ".join(str(loc) for loc in err.get("loc", []))
        errors.append({
            "field": field,
            "message": err.get("msg"),
            "type": err.get("type"),
        })
    return JSONResponse(
        status_code=422,
        content={
            "error": "InputValidationError",
            "message": "One or more input fields failed validation constraints.",
            "details": errors,
        },
    )

