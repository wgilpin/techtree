#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Start the FastAPI backend in the background
echo "Starting FastAPI backend..."
cd "$SCRIPT_DIR/backend"
python main.py &
BACKEND_PID=$!

# Wait a moment for the backend to start
sleep 2

# Return to the main directory
cd "$SCRIPT_DIR"

# Start the Flask frontend in the background
echo "Starting Flask frontend..."
python app.py &
FRONTEND_PID=$!

# Wait a moment for the frontend to start
sleep 2

# If the Flask app exits, kill the backend process
kill $BACKEND_PID
kill $FRONTEND_PID