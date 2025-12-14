from fastapi import FastAPI
import uvicorn

app = FastAPI(title="HoardRun Test Server")

@app.get("/")
async def root():
    return {"message": "HoardRun Backend is running!"}

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "hoardrun-backend"}

if __name__ == "__main__":
    print("🚀 Starting simple test server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
