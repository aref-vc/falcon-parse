# 🦅 Falcon Parse

AI-powered web scraping and data extraction tool that uses Gemini AI to intelligently extract structured data from any website.

## ✨ Features

- **Smart Data Extraction**: Uses Gemini AI to understand and extract specific data types from web pages
- **Advanced Dynamic Content Handling**: Automatically handles infinite scroll, pagination, and "Load More" buttons
- **Multiple Scraping Methods**: Combines BeautifulSoup and Playwright for maximum compatibility
- **Comprehensive Social Media Detection**: Extracts emails, LinkedIn, Twitter/X, and other social platforms
- **Scalable Extraction**: Can extract hundreds or thousands of items from paginated content
- **Real-time Progress**: WebSocket updates showing live extraction progress with detailed status
- **Export Options**: Download results as JSON or CSV files
- **Clean UI**: Modern React interface with responsive design
- **Flexible Input**: Pre-defined data types or custom extraction instructions

## 🚀 Quick Start

### Prerequisites

- Python 3.8+ 
- Node.js 16+
- npm or yarn
- Gemini API key ([Get one here](https://aistudio.google.com/app/apikey))

### Installation & Setup

1. **Clone or navigate to the project directory**
   ```bash
   cd "Falcon Parse"
   ```

2. **Set up environment**
   ```bash
   cp .env.example .env
   ```
   
3. **Add your Gemini API key to `.env`**
   ```bash
   GEMINI_API_KEY=your_actual_api_key_here
   ```

4. **Start the application**
   ```bash
   ./start.sh
   ```

The script will:
- Install all dependencies
- Set up Python virtual environment
- Install Playwright browsers
- Start both backend (port 8010) and frontend (port 3010)
- Open your browser automatically

## 🎯 Usage

1. **Enter URL**: Input the website URL you want to scrape
2. **Select Data Type**: Choose from predefined types or use custom instructions
3. **Extract Data**: Click "Extract Data" and watch real-time progress
4. **View Results**: See extracted data in a table format
5. **Download**: Export results as JSON or CSV files

### Pre-defined Data Types

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

## 🏗️ Architecture

### Backend (FastAPI)
- **Port**: 8010
- **API Endpoints**: RESTful API for scraping jobs
- **WebSocket**: Real-time progress updates
- **AI Integration**: Gemini API for intelligent data extraction
- **Scraping Engine**: Playwright + BeautifulSoup

### Frontend (React + Vite)  
- **Port**: 3010
- **UI Framework**: React with modern hooks
- **Styling**: Custom CSS with design system
- **Real-time Updates**: WebSocket integration
- **File Downloads**: Direct browser downloads

## 🛠️ Development

### Project Structure
```
falcon-parse/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── services/
│   │   ├── scraper.py       # Web scraping logic
│   │   ├── gemini_client.py # AI integration
│   │   └── data_processor.py # Data processing
│   ├── models/              # Pydantic models
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── services/        # API clients
│   │   └── App.jsx         # Main application
│   ├── package.json
│   └── public/
├── start.sh                 # Launch script
├── stop.sh                 # Stop script
└── .env.example            # Environment template
```

### Manual Development Setup

**Backend:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python main.py
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## 🔧 Configuration

### Environment Variables (.env)
```bash
# Required
GEMINI_API_KEY=your_gemini_api_key_here

# Optional
BACKEND_PORT=8010
FRONTEND_PORT=3010
BACKEND_HOST=0.0.0.0
MAX_CONCURRENT_SCRAPES=5
SCRAPE_TIMEOUT=30
TEMP_FILE_CLEANUP_HOURS=24
```

### Port Configuration
- **Frontend**: http://localhost:3010
- **Backend API**: http://localhost:8010
- **Health Check**: http://localhost:8010/health

## 📊 API Documentation

### Core Endpoints
- `POST /scrape` - Create scraping job
- `GET /status/{job_id}` - Check job status  
- `GET /result/{job_id}` - Get extraction results
- `GET /download/{job_id}/{format}` - Download files
- `WS /ws/{job_id}` - Real-time updates

### Example API Usage
```javascript
// Create scraping job
const response = await fetch('http://localhost:8010/scrape', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    url: 'https://example.com',
    data_type: 'product_listings',
    custom_instructions: null
  })
});
```

## 🚫 Stopping the Application

```bash
./stop.sh
```

Or manually kill the processes:
```bash
# Kill processes on specific ports
lsof -ti:8010 | xargs kill -9  # Backend
lsof -ti:3010 | xargs kill -9  # Frontend
```

## 🔍 Troubleshooting

### Common Issues

1. **Backend won't start**
   - Check if Python 3.8+ is installed
   - Verify Gemini API key in `.env` file
   - Check `backend.log` for error details

2. **Frontend won't start**
   - Check if Node.js 16+ is installed
   - Try `rm -rf node_modules && npm install`
   - Check `frontend.log` for error details

3. **Scraping fails**
   - Some websites block automated requests
   - Check if the website requires authentication
   - Verify the URL is accessible

4. **API key errors**
   - Ensure Gemini API key is valid and active
   - Check API quotas and billing
   - Verify key has proper permissions

### Logs
```bash
# View backend logs
tail -f backend.log

# View frontend logs  
tail -f frontend.log

# View both simultaneously
tail -f backend.log frontend.log
```

## 🎨 Customization

### Adding New Data Types
Edit `frontend/src/components/ScrapeForm.jsx`:
```javascript
const DATA_TYPE_OPTIONS = [
  // Add your custom type
  { value: 'my_custom_type', label: 'My Custom Type' },
  // ... existing options
];
```

### Styling
The app uses a custom CSS design system in `frontend/src/index.css` with CSS variables for easy theming.

## 📝 License

This project is for educational and personal use. Please respect website terms of service and robots.txt when scraping.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

---

**Built with ❤️ using React, FastAPI, and Gemini AI**