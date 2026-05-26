from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.webhook import webhook_router
from .api.routes import routes_router
from .config.settings import settings

# Validating configuration on startup
settings.validate()

app = FastAPI(title="Sentinel AI Healing Engine Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mounting the Routers
app.include_router(webhook_router, prefix="/api")
app.include_router(routes_router, prefix="/api")

import os
print("GOOGLE_API_KEY:", os.getenv("GOOGLE_API_KEY"))
print("GEMINI_API_KEY:", os.getenv("GEMINI_API_KEY"))

@app.get("/health")
def get_health():
    return {"status":"online", "service": "Sentinel AI Engine"}