from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.graph import router as graph_router
from backend.api.integration import router as integration_router
from backend.api.rag import router as rag_router
from backend.api.report import router as report_router
from backend.api.session import router as session_router
from backend.api.textbooks import router as textbooks_router


ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIST_DIR = ROOT_DIR / "frontend" / "dist"


def create_app(frontend_dist_dir: Path | None = FRONTEND_DIST_DIR) -> FastAPI:
    app = FastAPI(title="KIBot API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(session_router)
    app.include_router(textbooks_router)
    app.include_router(graph_router)
    app.include_router(rag_router)
    app.include_router(integration_router)
    app.include_router(report_router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "KIBot"}

    if frontend_dist_dir is not None:
        dist_dir = Path(frontend_dist_dir)
        index_html = dist_dir / "index.html"

        if index_html.is_file():
            assets_dir = dist_dir / "assets"
            if assets_dir.is_dir():
                app.mount(
                    "/assets",
                    StaticFiles(directory=assets_dir),
                    name="frontend-assets",
                )

            @app.get("/{full_path:path}", include_in_schema=False)
            def serve_frontend(full_path: str) -> FileResponse:
                if full_path == "api" or full_path.startswith("api/"):
                    raise HTTPException(status_code=404, detail="Not Found")

                requested_file = (dist_dir / full_path).resolve()
                try:
                    requested_file.relative_to(dist_dir.resolve())
                except ValueError:
                    raise HTTPException(status_code=404, detail="Not Found") from None

                if requested_file.is_file():
                    return FileResponse(requested_file)

                return FileResponse(index_html)

    return app


app = create_app()
