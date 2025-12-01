from fastapi import FastAPI
app = FastAPI(title = "Taylor Make API")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy"
    }

