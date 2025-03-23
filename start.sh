#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Change to the techtree-frontend directory
cd "$SCRIPT_DIR/techtree-frontend"

# Run the dev-all command
npm run dev-all