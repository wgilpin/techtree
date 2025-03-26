#!/bin/bash

# Start the Flask frontend
echo "Starting Flask frontend..."
# Run using the flask module, specifying the app location
# The --debug flag enables the reloader and debugger
python -m flask --app frontend.app run --debug --port 5000