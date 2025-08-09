#!/bin/bash

# Falcon Parse - Stop Script
# Stops both frontend and backend servers

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_colored() {
    echo -e "${1}${2}${NC}"
}

port_in_use() {
    lsof -i :$1 >/dev/null 2>&1
}

kill_port() {
    if port_in_use $1; then
        print_colored $YELLOW "Stopping process on port $1..."
        lsof -ti:$1 | xargs kill -9 2>/dev/null || true
        sleep 1
        
        if port_in_use $1; then
            print_colored $RED "Failed to stop process on port $1"
            return 1
        else
            print_colored $GREEN "✅ Stopped process on port $1"
            return 0
        fi
    else
        print_colored $YELLOW "No process running on port $1"
        return 0
    fi
}

main() {
    print_colored $YELLOW "🛑 Stopping Falcon Parse..."
    echo
    
    # Stop backend (port 8010)
    kill_port 8010
    
    # Stop frontend (port 3010)
    kill_port 3010
    
    # Clean up log files
    if [ -f "backend.log" ]; then
        rm backend.log
    fi
    
    if [ -f "frontend.log" ]; then
        rm frontend.log
    fi
    
    echo
    print_colored $GREEN "🎉 Falcon Parse stopped successfully!"
}

main "$@"