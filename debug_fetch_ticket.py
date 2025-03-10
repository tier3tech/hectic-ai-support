import requests
import json
import time

# Configuration
HALO_PSA_CLIENT_ID = "f1d979f7-22d8-4c25-81a4-256b95709ee6"
HALO_PSA_CLIENT_SECRET = "8bc61385-6990-46c4-8ffe-ff5f75ecd0f8-75b7d638-c689-4708-b986-f2f7ef6ad268"
HALO_PSA_BASE_URL = "https://opendoormsp.halopsa.com"
TOKEN_URL = f"{HALO_PSA_BASE_URL}/auth/token"
TICKET_URL = f"{HALO_PSA_BASE_URL}/api/tickets"

# Token storage (🔹 Define global variables)
ACCESS_TOKEN = None
TOKEN_EXPIRATION = 0

def get_access_token():
    """Retrieve a new HaloPSA API token if expired."""
    global ACCESS_TOKEN, TOKEN_EXPIRATION  # Declare as global

    if ACCESS_TOKEN and time.time() < TOKEN_EXPIRATION:
        return ACCESS_TOKEN  # Return existing token if still valid

    payload = {
        "grant_type": "client_credentials",
        "client_id": HALO_PSA_CLIENT_ID,
        "client_secret": HALO_PSA_CLIENT_SECRET,
        "scope": "all"
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(TOKEN_URL, data=payload, headers=headers)

    if response.status_code == 200:
        token_data = response.json()
        ACCESS_TOKEN = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 3600)  # Default to 1 hour
        TOKEN_EXPIRATION = time.time() + expires_in - 60  # Refresh before expiry
        print("✅ Retrieved New Access Token")
        return ACCESS_TOKEN
    else:
        print(f"❌ Failed to retrieve access token: {response.text}")
        raise Exception("Failed to retrieve access token")

def fetch_ticket_debug(ticket_id):
    """Fetches a specific ticket and logs its structure to debug category format."""
    url = f"{TICKET_URL}/{ticket_id}"
    headers = {"Authorization": f"Bearer {get_access_token()}"}

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        ticket_data = response.json()
        print(f"✅ Successfully fetched Ticket #{ticket_id}")
        print(json.dumps(ticket_data, indent=4))  # Pretty-print ticket details
    else:
        print(f"❌ Failed to fetch Ticket #{ticket_id}. Error: {response.text}")

# Run the test function with a ticket ID
fetch_ticket_debug(4571)
