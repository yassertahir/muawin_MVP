import streamlit as st
import os
import threading
import uvicorn
import nest_asyncio
import socket
import time

# Set page config as the first Streamlit command
st.set_page_config(page_title="DocAssist - AI Assistant for Doctors", layout="wide")

# Apply nest_asyncio to enable running asyncio event loops inside Jupyter/IPython
nest_asyncio.apply()

# First, make sure the database is initialized for Streamlit Cloud
from init_for_cloud import ensure_db_initialized
ensure_db_initialized()

# Function to check if a port is in use
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

# Function to start FastAPI server in a thread
def start_fastapi_server():
    # Try to find an available port, starting with 8000
    port = 8000
    max_attempts = 10
    
    for attempt in range(max_attempts):
        if not is_port_in_use(port):
            try:
                # Store the port in session state so other components can access it
                st.session_state['api_port'] = port
                # Run FastAPI on the available port
                uvicorn.run(fastapi_app, host="0.0.0.0", port=port, log_level="warning")
                break
            except Exception as e:
                st.error(f"Failed to start API server: {e}")
                port += 1
        else:
            port += 1
            if attempt == max_attempts - 1:
                st.error("Could not find an available port to run the API server")

# Import FastAPI app
from api import app as fastapi_app

# Create or get a session state key to track if the server has been started
if 'server_started' not in st.session_state:
    st.session_state['server_started'] = False
    
# Start FastAPI server in a background thread if not started already
if not st.session_state['server_started']:
    api_thread = threading.Thread(target=start_fastapi_server, daemon=True)
    api_thread.start()
    st.session_state['server_started'] = True
    # Give the server a moment to start
    time.sleep(1)

# Set the BASE_URL in the session state so app.py can use it
if 'api_port' in st.session_state:
    st.session_state['BASE_URL'] = f"http://localhost:{st.session_state['api_port']}"
else:
    # Fallback if port detection failed
    st.session_state['BASE_URL'] = "http://localhost:8000"

# Import the app module but don't run its set_page_config
import sys
import importlib.util
spec = importlib.util.spec_from_file_location("app_module", "app.py")
app_module = importlib.util.module_from_spec(spec)
app_module.st = st  # Pass our st instance with config already set
spec.loader.exec_module(app_module)