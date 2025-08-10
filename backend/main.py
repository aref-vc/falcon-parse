import os
import asyncio
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from contextlib import asynccontextmanager
from collections import defaultdict

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
websocket_connections: Dict[str, List[WebSocket]] = defaultdict(list)

# Progress tracking and job management
job_progress = defaultdict(lambda: {'last_update': time.time(), 'stage': 'pending'})
JOB_EXPIRY_HOURS = 2
MAX_CONCURRENT_JOBS = 5
STUCK_THRESHOLD = 30  # seconds without progress
JOB_TIMEOUT = 300  # 5 minutes total job timeout

def cleanup_expired_jobs():
    """Remove old jobs and results"""
    cutoff = datetime.now() - timedelta(hours=JOB_EXPIRY_HOURS)
    expired_jobs = [job_id for job_id, job in jobs.items() if job.created_at < cutoff]
    
    for job_id in expired_jobs:
        jobs.pop(job_id, None)
        results.pop(job_id, None)
        websocket_connections.pop(job_id, None)
        job_progress.pop(job_id, None)
    
    if expired_jobs:
        print(f"🧹 Cleaned up {len(expired_jobs)} expired jobs")

async def periodic_cleanup():
    """Periodic cleanup task"""
    while True:
        try:
            await asyncio.sleep(300)  # Run every 5 minutes
            cleanup_expired_jobs()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"⚠️ Cleanup task error: {e}")

def is_job_stuck(job_id: str) -> bool:
    """Check if job hasn't made progress recently"""
    if job_id not in job_progress:
        return False
    progress = job_progress[job_id]
    return time.time() - progress['last_update'] > STUCK_THRESHOLD

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
    
    # Start cleanup task
    cleanup_task = asyncio.create_task(periodic_cleanup())
    
    yield
    
    # Shutdown
    print("🔄 Shutting down gracefully...")
    cleanup_task.cancel()
    
    # Cancel all running jobs
    for job_id, job in jobs.items():
        if job.status == ScrapeStatus.PROCESSING:
            job.status = ScrapeStatus.FAILED
            job.error_message = "Server shutdown"
    
    # Close WebSocket connections
    for ws_list in list(websocket_connections.values()):
        for ws in ws_list:
            try:
                await ws.close()
            except:
                pass
    
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
    """Process a scraping job in the background with timeout and progress tracking"""
    try:
        # Add timeout wrapper
        async with asyncio.timeout(JOB_TIMEOUT):
            job = jobs[job_id]
            job.status = ScrapeStatus.PROCESSING
            
            # Stage 1: Initialization
            await notify_job_update(job_id, "🚀 Initializing scraping job...", "initializing")
            
            # Import processing services
            from services.scraper import WebScraper
            from services.gemini_client import GeminiClient
            from services.data_processor import DataProcessor
            
            # Get services from app state
            scraper = app.state.scraper
            gemini_client = app.state.gemini_client
            data_processor = DataProcessor()
            
            start_time = datetime.now()
            
            # Stage 2: Content Loading with timeout detection
            await notify_job_update(job_id, "🌐 Loading website content...", "loading")
            load_start = time.time()
            
            html_content = await scraper.scrape_url(job.url)
            
            load_time = time.time() - load_start
            if load_time > 60:  # 1 minute
                await notify_job_update(job_id, f"⏰ Content loading took {load_time:.1f}s (slow site detected)", "loading_slow")
            
            await notify_job_update(job_id, f"✅ Content loaded ({len(html_content.get('text', ''))} chars)", "content_loaded")
            
            # Check if dynamic content was loaded
            method = html_content.get('method', 'unknown')
            if method == 'playwright':
                await notify_job_update(job_id, "🔄 Dynamic content and pagination processed", "dynamic_content")
            
            # Stage 3: AI Processing with progress indicators
            await notify_job_update(job_id, "🤖 Sending to Gemini AI for analysis...", "ai_processing")
            
            # Create progress callback for AI processing
            async def ai_progress_callback(message):
                await notify_job_update(job_id, f"🧠 {message}", "ai_thinking")
            
            raw_data = await gemini_client.extract_data(
                html_content, 
                job.data_type, 
                job.custom_instructions
            )
            
            await notify_job_update(job_id, f"✨ AI extracted {len(raw_data)} data items", "ai_completed")
            
            # Stage 4: Data Processing
            await notify_job_update(job_id, "🔧 Processing and cleaning extracted data...", "data_processing")
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
            await notify_job_update(job_id, "📁 Generating JSON and CSV export files...", "exporting")
            data_processor.generate_exports(job_id, processed_data)
            
            await notify_job_update(job_id, f"🎉 Completed! Successfully extracted {result.row_count} rows in {processing_time:.1f}s", "completed")
        
    except asyncio.TimeoutError:
        # Handle timeout
        job = jobs[job_id]
        job.status = ScrapeStatus.FAILED
        job.error_message = f"Job timed out after {JOB_TIMEOUT} seconds"
        job.completed_at = datetime.now()
        
        result = ScrapeResult(
            job_id=job_id,
            status=ScrapeStatus.FAILED,
            error_message=job.error_message
        )
        results[job_id] = result
        
        await notify_job_update(job_id, f"⏰ Job cancelled - timeout reached after {JOB_TIMEOUT}s", "timeout")
        
    except Exception as e:
        # Handle other errors
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
        
        await notify_job_update(job_id, f"❌ Failed: {str(e)}", "failed")

async def notify_job_update(job_id: str, message: str, stage: str = None):
    """Enhanced notify with progress tracking and stuck detection"""
    # Update progress heartbeat
    job_progress[job_id]['last_update'] = time.time()
    if stage:
        job_progress[job_id]['stage'] = stage
    
    # Check if job appears stuck (but don't mark completed/failed jobs as stuck)
    stuck_indicator = ""
    progress_age = time.time() - job_progress[job_id]['last_update']
    if is_job_stuck(job_id) and stage not in ['completed', 'failed', 'timeout', 'cancelled']:
        stuck_indicator = " ⚠️ [Job may be stuck - check status]"
    
    if job_id in websocket_connections:
        message_data = {
            "job_id": job_id,
            "message": message + stuck_indicator,
            "stage": stage or job_progress[job_id]['stage'],
            "progress_age": progress_age,
            "is_stuck": is_job_stuck(job_id),
            "timestamp": datetime.now().isoformat()
        }
        
        # Send to all connections for this job, remove dead ones
        active_connections = []
        for ws in websocket_connections[job_id]:
            try:
                await ws.send_json(message_data)
                active_connections.append(ws)
            except:
                # WebSocket is disconnected, skip it
                pass
        
        # Update with only active connections
        if active_connections:
            websocket_connections[job_id] = active_connections
        else:
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

@app.post("/cancel/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a running job"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    if job.status in [ScrapeStatus.COMPLETED, ScrapeStatus.FAILED]:
        raise HTTPException(status_code=400, detail="Job already finished")
    
    # Mark as cancelled
    job.status = ScrapeStatus.FAILED
    job.error_message = "Cancelled by user"
    job.completed_at = datetime.now()
    
    # Store cancelled result
    results[job_id] = ScrapeResult(
        job_id=job_id,
        status=ScrapeStatus.FAILED,
        error_message="Job cancelled by user"
    )
    
    # Notify via WebSocket
    await notify_job_update(job_id, "🛑 Job cancelled by user", "cancelled")
    
    return {"message": "Job cancelled successfully"}

@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time job updates"""
    await websocket.accept()
    
    # Add this connection to the list for this job
    websocket_connections[job_id].append(websocket)
    
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        # Remove this specific connection
        if job_id in websocket_connections:
            try:
                websocket_connections[job_id].remove(websocket)
                # Remove the job key if no connections left
                if not websocket_connections[job_id]:
                    websocket_connections.pop(job_id, None)
            except ValueError:
                # Connection was already removed
                pass

if __name__ == "__main__":
    port = int(os.getenv("BACKEND_PORT", 8010))
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    
    print(f"🚀 Starting Falcon Parse Backend on http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=True)