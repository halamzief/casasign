"""CasaSign - Generic digital document signature service."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from loguru import logger

from src.config import settings

# Template directory
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = TEMPLATES_DIR / "static"


class TemplateEngine:
    """Jinja2 template engine wrapper."""

    def __init__(self, templates_dir: Path) -> None:
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=True,
            enable_async=True,
        )

    async def TemplateResponse(self, template_name: str, context: dict) -> HTMLResponse:
        """Render a template and return an HTML response."""
        template = self.env.get_template(template_name)
        content = await template.render_async(**context)
        return HTMLResponse(content=content)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle events."""
    # Startup
    logger.info(
        f"Starting {settings.service_name} service",
        service=settings.service_name,
        port=settings.service_port,
        debug=settings.debug,
    )

    # Initialize database engine
    from src.database.engine import dispose_engine, get_engine

    get_engine()
    logger.info("Database engine initialized")

    # Create storage directories
    import os

    os.makedirs(settings.signatures_storage_path, exist_ok=True)
    logger.info("Storage directory ready", path=settings.signatures_storage_path)

    # Initialize template engine
    app.state.templates = TemplateEngine(TEMPLATES_DIR)
    logger.info("Template engine initialized", templates_dir=str(TEMPLATES_DIR))

    yield

    # Shutdown
    await dispose_engine()
    logger.info(f"Shutting down {settings.service_name} service")


# Create FastAPI application
app = FastAPI(
    title=f"{settings.service_name} API",
    description="Digital document signature service with audit trails",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": "0.1.0",
    }


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with service information."""
    return {
        "service": settings.service_name,
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


# Include API routers
from src.api.admin_templates import router as admin_templates_router  # noqa: E402
from src.api.pages import router as pages_router  # noqa: E402
from src.api.signatures import router as signatures_router  # noqa: E402
from src.api.sse_status import router as sse_router  # noqa: E402

# Mount static files for JS/CSS
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# API routes
app.include_router(signatures_router)
app.include_router(sse_router)
app.include_router(admin_templates_router)

# Page routes (must be last to avoid conflicts)
app.include_router(pages_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.service_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
