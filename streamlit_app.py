import streamlit as st
import os
import threading
import uvicorn
import nest_asyncio

# Set page config as the first Streamlit command
st.set_page_config(page_title="Muawin - AI Assistant for Doctors", layout="wide")

# Apply nest_asyncio to enable running asyncio event loops inside Jupyter/IPython
nest_asyncio.apply()

# First, make sure the database is initialized for Streamlit Cloud
from init_for_cloud import ensure_db_initialized
ensure_db_initialized()

# Function to start FastAPI server in a thread
def start_fastapi_server():
    # Run FastAPI on port 8000
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)

# Import FastAPI app after setting page config
from api import app as fastapi_app

# Start FastAPI server in a background thread
threading.Thread(target=start_fastapi_server, daemon=True).start()

# Import the app module but don't run its set_page_config
import sys
import importlib.util
spec = importlib.util.spec_from_file_location("app_module", "app.py")
app_module = importlib.util.module_from_spec(spec)
app_module.st = st  # Pass our st instance with config already set
spec.loader.exec_module(app_module)