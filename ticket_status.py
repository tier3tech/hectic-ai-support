import requests
import os
import json
import time
from datetime import datetime, timezone

# 🔒 Secure API Credentials
HALO_PSA_CLIENT_ID = os.getenv("HALO_PSA_CLIENT_ID")
HALO_PSA_CLIENT_SECRET = os.getenv("HALO_PSA_CLIENT_SECRET")
HALO_PSA_BASE_URL = "https://opendoormsp.halopsa.com"
TOKEN_URL = f"{HALO_PSA_BASE_URL}/auth/token"

# 🔑 Global Variables for API Token (Declare These Before `get_access_token`)
ACCESS_TOKEN = None
TOKEN_EXPIRATION = 0

# 🔹 FUNCTION: GET ACCESS TOKEN
def get_access_token():
    """Retrieve a new HaloPSA API token if expired."""
    global ACCESS_TOKEN, TOKEN_EXPIRATION  # ✅ Ensure global variables are modified
    if ACCESS_TOKEN and time.time() < TOKEN_EXPIRATION:
        return ACCESS_TOKEN

    payload = {
        "grant_type": "client_credentials",
        "client_id": HALO_PSA_CLIENT_ID,
        "client_secret": HALO_PSA_CLIENT_SECRET,  # ✅ Fixed: Removed extra quote
        "scope": "all"
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(TOKEN_URL, data=payload, headers=headers)

    if response.status_code == 200:
        token_data = response.json()
        ACCESS_TOKEN = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 3600)
        TOKEN_EXPIRATION = time.time() + expires_in - 60  # ✅ Set expiration
        print("✅ Retrieved New Access Token")
        return ACCESS_TOKEN
    else:
        print(f"❌ Failed to retrieve access token: {response.text}")
        raise Exception("Failed to retrieve access token")

# 🔹 FUNCTION: GET TICKET STATUSES

def get_ticket_statuses():
    """Retrieve all available ticket statuses from HaloPSA."""
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }

    # ✅ Correct API path to fetch ticket statuses
    endpoint = f"{HALO_PSA_BASE_URL}/api/status?type=ticket"

    response = requests.get(endpoint, headers=headers)

    if response.status_code == 200:
        statuses = response.json()  # ✅ Directly get the list
        if isinstance(statuses, list):  # ✅ Ensure it's a list before iterating
            for status in statuses:
                print(f"ID: {status['id']}, Name: {status['name']}")
            return statuses  # ✅ Return the status list
        else:
            print("❌ Unexpected response format. Expected a list.")
            print(f"Response: {statuses}")
    else:
        print(f"❌ Failed to fetch ticket statuses. Status Code: {response.status_code}, Response: {response.text}")
        return None

# ✅ Run the function to check available ticket statuses
get_ticket_statuses()
