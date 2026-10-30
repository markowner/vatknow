from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.logs import router as logs_router
from app.api.proxy import router as proxy_router
from app.api.public import router as public_router
from app.api.search import router as search_router
from app.api.shares import router as shares_router
from app.api.site import router as site_router
from app.api.spaces import router as spaces_router
from app.api.users import router as users_router
from app.config import settings
from app.db import init_db
from app.services.audit import install_audit


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="VatKnow", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
install_audit(app)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(spaces_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(shares_router, prefix="/api/v1")
app.include_router(logs_router, prefix="/api/v1")
app.include_router(proxy_router, prefix="/api/v1")
app.include_router(public_router, prefix="/api/v1")
app.include_router(site_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")


@app.get("/health")
@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
