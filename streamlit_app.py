import streamlit as st
import os
import threading
import uvicorn
import nest_asyncio
from api import app as fastapi_app

# Apply nest_asyncio to enable running asyncio event loops inside Jupyter/IPython
nest_asyncio.apply()

# First, make sure the database is initialized for Streamlit Cloud
from init_for_cloud import ensure_db_initialized
ensure_db_initialized()

# Function to start FastAPI server in a thread
def start_fastapi_server():
    # Run FastAPI on port 8000
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)

# Start FastAPI server in a background thread
threading.Thread(target=start_fastapi_server, daemon=True).start()

# Import and run the Streamlit app
import app  # This imports and runs your existing app.py