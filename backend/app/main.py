from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, engine, ensure_schema
from .routes import review, settings, stats, words


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    yield


app = FastAPI(title="WordGlass API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(words.router)
app.include_router(review.router)
app.include_router(stats.router)
app.include_router(settings.router)


@app.get("/api/health")
def health():
    return {"ok": True}
