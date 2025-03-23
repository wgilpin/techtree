#!/bin/bash

# kill_servers.sh - Script to find and kill Python and Node.js processes
# For use in Windows environments with bash shell (Git Bash or WSL)

echo "Searching for Python and Node.js processes..."

# Function to kill processes by name
kill_process() {
    process_name=$1
    echo "Looking for $process_name processes..."

    # Use tasklist to find processes and filter by name
    processes=$(tasklist //FI "IMAGENAME eq $process_name" 2>/dev/null | grep $process_name)

    if [ -z "$processes" ]; then
        echo "No $process_name processes found."
        return 0
    fi

    echo "Found $process_name processes:"
    echo "$processes"
    echo ""

    # Extract PIDs and kill each process
    echo "Terminating $process_name processes..."
    pids=$(echo "$processes" | awk '{print $2}')

    for pid in $pids; do
        echo "Killing process with PID: $pid"
        taskkill //F //PID $pid 2>/dev/null

        if [ $? -eq 0 ]; then
            echo "Successfully terminated process with PID: $pid"
        else
            echo "Failed to terminate process with PID: $pid"
        fi
    done

    echo "Finished processing $process_name."
    echo ""
}

# Kill Python processes
kill_process "python.exe"

# Kill Node.js processes
kill_process "node.exe"

echo "All operations completed."