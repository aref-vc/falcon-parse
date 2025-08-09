import os
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from dotenv import load_dotenv

from models.scrape_models import (
    ScrapeRequest, ScrapeJob, ScrapeResult, JobStatus, 
    ScrapeStatus, HealthCheck
)

# Load environment variables
load_dotenv()

# Global storage for jobs (in production, use a database)
jobs: Dict[str, ScrapeJob] = {}
results: Dict[str, ScrapeResult] = {}
websocket_connections: Dict[str, WebSocket] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Falcon Parse Backend Starting...")
    
    # Import services here to ensure they're loaded after environment
    from services.scraper import WebScraper
    from services.gemini_client import GeminiClient
    
    # Initialize services
    app.state.scraper = WebScraper()
    app.state.gemini_client = GeminiClient()
    
    # Test Gemini API connection
    try:
        await app.state.gemini_client.test_connection()
        print("✅ Gemini API connection successful")
    except Exception as e:
        print(f"⚠️ Gemini API connection failed: {e}")
    
    yield
    
    # Shutdown
    print("🔄 Falcon Parse Backend Shutting down...")
    if hasattr(app.state, 'scraper'):
        await app.state.scraper.cleanup()

app = FastAPI(
    title="Falcon Parse API",
    description="AI-powered web scraping and data extraction service",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3010"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint"""
    gemini_healthy = False
    try:
        if hasattr(app.state, 'gemini_client'):
            await app.state.gemini_client.test_connection()
            gemini_healthy = True
    except:
        pass
        
    return HealthCheck(
        status="healthy",
        timestamp=datetime.now(),
        gemini_api=gemini_healthy
    )

@app.post("/scrape", response_model=JobStatus)
async def create_scrape_job(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """Create a new scraping job"""
    job_id = str(uuid.uuid4())
    
    # Create job
    job = ScrapeJob(
        job_id=job_id,
        url=str(request.url),
        data_type=request.data_type,
        custom_instructions=request.custom_instructions,
        status=ScrapeStatus.PENDING,
        created_at=datetime.now()
    )
    
    jobs[job_id] = job
    
    # Start processing in background
    background_tasks.add_task(process_scrape_job, job_id)
    
    return JobStatus(
        job_id=job_id,
        status=ScrapeStatus.PENDING,
        message="Job created and queued for processing"
    )

async def process_scrape_job(job_id: str):
    """Process a scraping job in the background"""
    try:
        job = jobs[job_id]
        job.status = ScrapeStatus.PROCESSING
        
        # Notify WebSocket clients
        await notify_job_update(job_id, "Processing started...")
        
        # Import processing services
        from services.scraper import WebScraper
        from services.gemini_client import GeminiClient
        from services.data_processor import DataProcessor
        
        # Get services from app state
        scraper = app.state.scraper
        gemini_client = app.state.gemini_client
        data_processor = DataProcessor()
        
        start_time = datetime.now()
        
        # Step 1: Scrape the website
        await notify_job_update(job_id, "🌐 Scraping website content...")
        html_content = await scraper.scrape_url(job.url)
        
        await notify_job_update(job_id, f"📄 Content loaded ({len(html_content.get('text', ''))} characters)")
        
        # Check if dynamic content was loaded
        method = html_content.get('method', 'unknown')
        if method == 'playwright':
            await notify_job_update(job_id, "🔄 Dynamic content and pagination processed")
        
        # Step 2: Extract data using Gemini AI
        await notify_job_update(job_id, "🤖 Analyzing content with Gemini AI...")
        raw_data = await gemini_client.extract_data(
            html_content, 
            job.data_type, 
            job.custom_instructions
        )
        
        await notify_job_update(job_id, f"✨ AI extracted {len(raw_data)} data items")
        
        # Step 3: Process and structure the data
        await notify_job_update(job_id, "🔧 Processing and cleaning extracted data...")
        processed_data = data_processor.process_data(raw_data)
        
        # Create result
        processing_time = (datetime.now() - start_time).total_seconds()
        result = ScrapeResult(
            job_id=job_id,
            status=ScrapeStatus.COMPLETED,
            data=processed_data.get('data', []),
            columns=processed_data.get('columns', []),
            row_count=len(processed_data.get('data', [])),
            processing_time=processing_time
        )
        
        # Update job and store result
        job.status = ScrapeStatus.COMPLETED
        job.completed_at = datetime.now()
        results[job_id] = result
        
        # Generate export files
        await notify_job_update(job_id, "📁 Generating JSON and CSV export files...")
        data_processor.generate_exports(job_id, processed_data)
        
        await notify_job_update(job_id, f"🎉 Completed! Successfully extracted {result.row_count} rows in {processing_time:.1f}s")
        
    except Exception as e:
        # Handle errors
        job = jobs[job_id]
        job.status = ScrapeStatus.FAILED
        job.error_message = str(e)
        job.completed_at = datetime.now()
        
        result = ScrapeResult(
            job_id=job_id,
            status=ScrapeStatus.FAILED,
            error_message=str(e)
        )
        results[job_id] = result
        
        await notify_job_update(job_id, f"❌ Failed: {str(e)}")

async def notify_job_update(job_id: str, message: str):
    """Notify WebSocket clients about job updates"""
    if job_id in websocket_connections:
        try:
            await websocket_connections[job_id].send_json({
                "job_id": job_id,
                "message": message,
                "timestamp": datetime.now().isoformat()
            })
        except:
            # Remove disconnected WebSocket
            websocket_connections.pop(job_id, None)

@app.get("/status/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get the status of a scraping job"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    result = results.get(job_id)
    
    return JobStatus(
        job_id=job_id,
        status=job.status,
        message=result.error_message if result and result.error_message else None
    )

@app.get("/result/{job_id}", response_model=ScrapeResult)
async def get_job_result(job_id: str):
    """Get the result of a completed scraping job"""
    if job_id not in results:
        raise HTTPException(status_code=404, detail="Result not found")
    
    return results[job_id]

@app.get("/download/{job_id}/{format}")
async def download_result(job_id: str, format: str):
    """Download the result in JSON or CSV format"""
    if job_id not in results:
        raise HTTPException(status_code=404, detail="Result not found")
    
    if format not in ["json", "csv"]:
        raise HTTPException(status_code=400, detail="Format must be 'json' or 'csv'")
    
    file_path = f"/tmp/falcon_parse_{job_id}.{format}"
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Export file not found")
    
    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=f"falcon_parse_result.{format}"
    )

@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time job updates"""
    await websocket.accept()
    websocket_connections[job_id] = websocket
    
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_connections.pop(job_id, None)

if __name__ == "__main__":
    port = int(os.getenv("BACKEND_PORT", 8010))
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    
    print(f"🚀 Starting Falcon Parse Backend on http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=True)