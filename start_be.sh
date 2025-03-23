#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Start the FastAPI backend
echo "Starting FastAPI backend..."
cd "$SCRIPT_DIR/backend"
python main.py