#!/bin/bash

# Define paths to your Python files
START_SCRIPT="main.py"
TERMINATE_SCRIPT="terminate.py"
BENCHMARK_SCRIPT="benchmark.py"

# Log file to capture the output
LOG_FILE="cloud_automation.log"

# Function to check for errors and exit if a command fails
check_error() {
    if [ $? -ne 0 ]; then
        echo "Error encountered during $1. Check the log file for details."
        exit 1
    fi
}

echo "Starting cloud infrastructure with $START_SCRIPT..." | tee -a $LOG_FILE
# Run the main.py script to set up infrastructure
python3 -u $START_SCRIPT | tee -a $LOG_FILE
check_error "starting cloud infrastructure"

# Terminate question
echo "Do you want to benchmark the infrastructure? (yes/no)"
read BENCHMARK_CONFIRM

if [ "$BENCHMARK_CONFIRM" == "yes" ]; then
    echo "Running benchmarks with $BENCHMARK_SCRIPT..." | tee -a $LOG_FILE
    # Run the terminate.py script to tear down infrastructure
    python3 -u $BENCHMARK_SCRIPT | tee -a $LOG_FILE
    check_error "benchmarking cloud infrastructure"
    echo "Benchmark complete." | tee -a $LOG_FILE
else
    echo "Skipping benchmarking."
fi

# Terminate question
echo "Do you want to terminate the infrastructure? (yes/no)"
read TERMINATE_CONFIRM

if [ "$TERMINATE_CONFIRM" == "yes" ]; then
    echo "Terminating cloud infrastructure with $TERMINATE_SCRIPT..." | tee -a $LOG_FILE
    # Run the terminate.py script to tear down infrastructure
    python3 -u $TERMINATE_SCRIPT | tee -a $LOG_FILE
    check_error "terminating cloud infrastructure"
    echo "Cloud infrastructure terminated." | tee -a $LOG_FILE
else
    echo "Skipping termination. You can run $TERMINATE_SCRIPT manually later."
fi

echo "All tasks completed successfully!" | tee -a $LOG_FILE
killall python3
