#!/bin/bash

# Initialize database if needed
python db_init.py

# Start FastAPI backend in background
uvicorn api:app --reload &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start Streamlit frontend
streamlit run app.py

# When frontend is closed, kill backend
kill $BACKEND_PID
