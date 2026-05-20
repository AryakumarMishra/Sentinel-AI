from fastapi import FastAPI
from api.webhook import webhook_router

app = FastAPI(title="Sentinel AI Healing Engine Backend")

# Registering the Webhook routing logic
app.include_router(webhook_router, prefix="/api")

@app.get("/health")
def get_health():
    return {"status":"online", "service": "Sentinel AI Engine"}