# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Falcon Parse is an AI-powered web scraping and data extraction tool that combines intelligent content analysis with modern web technologies. The system uses Gemini AI to understand and extract structured data from any website, handling dynamic content through Playwright automation and BeautifulSoup parsing.

## Architecture

### Backend (FastAPI)
- **Main Application**: `backend/main.py` - FastAPI server with WebSocket support
- **Models**: `backend/models/scrape_models.py` - Pydantic models for request/response validation
- **Services**:
  - `backend/services/scraper.py` - Web scraping engine (Playwright + BeautifulSoup)  
  - `backend/services/gemini_client.py` - Gemini AI integration for data extraction
  - `backend/services/data_processor.py` - Data processing and export functionality
- **Port**: 8010
- **Key Features**: RESTful API, WebSocket real-time updates, background job processing

### Frontend (React + Vite)
- **Main App**: `frontend/src/App.jsx` - React application with hooks-based state management
- **Components**:
  - `ScrapeForm.jsx` - URL input and data type selection
  - `ProgressTracker.jsx` - Real-time job status display
  - `ResultsTable.jsx` - Extracted data visualization and export
- **Services**: `frontend/src/services/api.js` - API client with WebSocket integration
- **Port**: 3010
- **Build Tool**: Vite with ESLint configuration

## Development Commands

### Quick Start
```bash
# Start both frontend and backend servers
./start.sh

# Stop all servers and cleanup
./stop.sh
```

### Manual Development
```bash
# Backend setup and run
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python main.py

# Frontend setup and run
cd frontend
npm install
npm run dev

# Frontend build and preview
npm run build
npm run preview

# Code quality
npm run lint
```

### Environment Setup
```bash
# Copy environment template
cp .env.example .env

# Edit .env file and add GEMINI_API_KEY
# Get API key from: https://aistudio.google.com/app/apikey
```

## Key Technical Details

### API Endpoints
- `POST /scrape` - Create scraping job, returns job_id
- `GET /status/{job_id}` - Check job status (pending/processing/completed/failed)
- `GET /result/{job_id}` - Get extraction results with structured data
- `GET /download/{job_id}/{format}` - Download as JSON or CSV
- `WS /ws/{job_id}` - Real-time progress updates via WebSocket
- `GET /health` - Health check with Gemini API status

### Data Flow
1. **Job Creation**: Frontend submits URL and data type to `/scrape` endpoint
2. **Background Processing**: FastAPI BackgroundTasks handles scraping asynchronously
3. **Content Extraction**: Playwright/BeautifulSoup scrapes website content
4. **AI Processing**: Gemini AI analyzes content and extracts structured data
5. **Data Processing**: Results cleaned, formatted, and exported to temp files
6. **Real-time Updates**: WebSocket streams progress messages to frontend
7. **Results Display**: Frontend shows extracted data in table format with download options

### State Management
- **Backend**: In-memory dictionaries for jobs/results (production would use database)
- **Frontend**: React hooks for component state, WebSocket for real-time updates
- **Job Lifecycle**: PENDING → PROCESSING → COMPLETED/FAILED

### Error Handling
- Backend validates requests with Pydantic models
- WebSocket fallback to HTTP polling for connectivity issues
- Gemini API connection testing on startup
- Graceful error messages propagated to frontend

## Dependencies

### Backend (Python 3.8+)
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `playwright` - Browser automation for dynamic content
- `beautifulsoup4` - HTML parsing
- `google-generativeai` - Gemini AI client
- `pandas` - Data processing
- `websockets` - Real-time communication

### Frontend (Node.js 16+)
- `react` + `react-dom` - UI framework
- `vite` - Build tool and dev server
- `axios` - HTTP client
- `lucide-react` - Icon system

## Environment Variables

Required in `.env` file:
- `GEMINI_API_KEY` - Gemini AI API key (required)
- `BACKEND_PORT` - Backend server port (default: 8010)
- `FRONTEND_PORT` - Frontend server port (default: 3010)
- `BACKEND_HOST` - Backend host (default: 0.0.0.0)

## Logs and Monitoring

- `backend.log` - Backend server logs and errors
- `frontend.log` - Frontend build and dev server logs
- `tail -f backend.log frontend.log` - Monitor both logs simultaneously

## Data Types Supported

Pre-configured extraction types:
- Product Listings
- Contact Information
- News Articles
- Job Postings
- Event Listings
- Pricing Tables
- Company Details
- Testimonials & Reviews
- Social Media Links
- Menu Items
- Custom Instructions (user-defined)

## Port Configuration (from CLAUDE.md)

- **3010**: Falcon Parse Frontend (AI web scraping tool interface)
- **8010**: Falcon Parse Backend API (AI web scraping service)

## Common Tasks

- **Launch Application**: Use `./start.sh` for complete setup with dependency installation
- **Development**: Use manual commands for faster iteration during active development
- **Debugging**: Monitor logs in real-time, check health endpoint for API status
- **Testing**: Verify WebSocket functionality and Gemini API connectivity
- **Adding Data Types**: Edit `frontend/src/components/ScrapeForm.jsx` DATA_TYPE_OPTIONS array