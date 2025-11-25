import sys
import os
# Add project root directory to path to allow importing src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from google.adk.agents import Agent
from google.adk.sessions import DatabaseSessionService
from src.agent import create_qa_agent
from dotenv import load_dotenv
import aiohttp

# Monkey patch for aiohttp < 3.8 compatibility with google-genai
if not hasattr(aiohttp, 'ClientConnectorDNSError'):
    aiohttp.ClientConnectorDNSError = aiohttp.ClientConnectorError

load_dotenv()

# Initialize Session Service
# We use the same database as main.py for consistency
session_service = DatabaseSessionService(db_url="sqlite:///storage/sessions.db")

# Create the agent
# We assign it to root_agent as expected by ADK Web UI
root_agent = create_qa_agent()
