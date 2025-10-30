from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import runs, samples, stats

app = FastAPI(title="Bizim Performans Aracı API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs.router)
app.include_router(samples.router)
app.include_router(stats.router)


@app.get("/health")
def healthcheck():
    return {"status": "ok"}
