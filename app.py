from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.chat import router as chat_router
from backend.api.graph import router as graph_router
from backend.api.integration import router as integration_router
from backend.api.rag import router as rag_router
from backend.api.report import router as report_router
from backend.api.session import router as session_router
from backend.api.textbooks import router as textbooks_router


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
app.include_router(chat_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "KIBot"}
