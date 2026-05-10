from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "KIBot"}
