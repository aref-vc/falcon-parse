#!/bin/bash

# Falcon Parse - Startup Script
# Launches both frontend and backend servers

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored output
print_colored() {
    echo -e "${1}${2}${NC}"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if port is in use
port_in_use() {
    lsof -i :$1 >/dev/null 2>&1
}

# Function to kill process on port
kill_port() {
    if port_in_use $1; then
        print_colored $YELLOW "Killing existing process on port $1..."
        lsof -ti:$1 | xargs kill -9 2>/dev/null || true
        sleep 2
    fi
}

# Main startup function
main() {
    print_colored $CYAN "🦅 Starting Falcon Parse..."
    echo
    
    # Check if we're in the right directory
    if [ ! -f "start.sh" ]; then
        print_colored $RED "❌ Please run this script from the Falcon Parse root directory"
        exit 1
    fi
    
    # Check dependencies
    print_colored $BLUE "🔍 Checking dependencies..."
    
    if ! command_exists python3; then
        print_colored $RED "❌ Python 3 is required but not installed"
        exit 1
    fi
    
    if ! command_exists node; then
        print_colored $RED "❌ Node.js is required but not installed"
        exit 1
    fi
    
    if ! command_exists npm; then
        print_colored $RED "❌ npm is required but not installed"
        exit 1
    fi
    
    # Check environment file
    if [ ! -f ".env" ]; then
        print_colored $YELLOW "⚠️  No .env file found. Copying from .env.example..."
        cp .env.example .env
        print_colored $RED "❗ Please edit .env file and add your GEMINI_API_KEY before proceeding"
        print_colored $CYAN "   You can get a Gemini API key from: https://aistudio.google.com/app/apikey"
        exit 1
    fi
    
    # Check if Gemini API key is set
    source .env
    if [ -z "$GEMINI_API_KEY" ] || [ "$GEMINI_API_KEY" = "your_gemini_api_key_here" ]; then
        print_colored $RED "❗ Please set your GEMINI_API_KEY in the .env file"
        print_colored $CYAN "   You can get a Gemini API key from: https://aistudio.google.com/app/apikey"
        exit 1
    fi
    
    # Kill existing processes
    kill_port 8010  # Backend
    kill_port 3010  # Frontend
    
    # Install backend dependencies
    print_colored $BLUE "📦 Installing backend dependencies..."
    cd backend
    if [ ! -d "venv" ]; then
        print_colored $YELLOW "Creating Python virtual environment..."
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    
    # Install Playwright browsers
    print_colored $BLUE "🌐 Setting up Playwright browsers..."
    playwright install chromium
    
    cd ..
    
    # Install frontend dependencies
    print_colored $BLUE "📦 Installing frontend dependencies..."
    cd frontend
    if [ ! -d "node_modules" ]; then
        npm install
    fi
    cd ..
    
    print_colored $GREEN "✅ All dependencies installed!"
    echo
    
    # Start backend
    print_colored $BLUE "🚀 Starting backend server on port 8010..."
    cd backend
    source venv/bin/activate
    nohup python main.py > ../backend.log 2>&1 &
    BACKEND_PID=$!
    cd ..
    
    # Wait for backend to start
    print_colored $YELLOW "⏳ Waiting for backend to start..."
    sleep 5
    
    # Check if backend is running
    if ! port_in_use 8010; then
        print_colored $RED "❌ Backend failed to start. Check backend.log for errors."
        exit 1
    fi
    
    # Start frontend
    print_colored $BLUE "🚀 Starting frontend server on port 3010..."
    cd frontend
    nohup npm run dev > ../frontend.log 2>&1 &
    FRONTEND_PID=$!
    cd ..
    
    # Wait for frontend to start
    print_colored $YELLOW "⏳ Waiting for frontend to start..."
    sleep 5
    
    # Check if frontend is running
    if ! port_in_use 3010; then
        print_colored $RED "❌ Frontend failed to start. Check frontend.log for errors."
        kill $BACKEND_PID 2>/dev/null
        exit 1
    fi
    
    echo
    print_colored $GREEN "🎉 Falcon Parse is now running!"
    print_colored $CYAN "📱 Frontend: http://localhost:3010"
    print_colored $CYAN "🔧 Backend:  http://localhost:8010"
    echo
    print_colored $YELLOW "📋 Process IDs:"
    print_colored $YELLOW "   Backend PID:  $BACKEND_PID"
    print_colored $YELLOW "   Frontend PID: $FRONTEND_PID"
    echo
    print_colored $BLUE "💡 To stop the servers:"
    print_colored $BLUE "   kill $BACKEND_PID $FRONTEND_PID"
    print_colored $BLUE "   or run: ./stop.sh"
    echo
    print_colored $PURPLE "🔍 Logs:"
    print_colored $PURPLE "   Backend:  tail -f backend.log"
    print_colored $PURPLE "   Frontend: tail -f frontend.log"
    echo
    
    # Open browser (optional)
    if command_exists open; then
        print_colored $GREEN "🌐 Opening browser..."
        open http://localhost:3010
    elif command_exists xdg-open; then
        print_colored $GREEN "🌐 Opening browser..."
        xdg-open http://localhost:3010
    fi
    
    # Keep script running to show logs
    print_colored $CYAN "📺 Showing live logs (Ctrl+C to stop):"
    echo
    trap cleanup INT TERM
    tail -f backend.log frontend.log
}

# Cleanup function
cleanup() {
    echo
    print_colored $YELLOW "🔄 Shutting down Falcon Parse..."
    
    # Kill background processes
    jobs -p | xargs kill 2>/dev/null || true
    
    # Kill processes on ports
    kill_port 8010
    kill_port 3010
    
    print_colored $GREEN "✅ Falcon Parse stopped successfully"
    exit 0
}

# Run main function
main "$@"