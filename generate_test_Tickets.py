import requests
import random
import time

# Configuration - Replace with actual API keys and endpoints
HALO_PSA_CLIENT_ID = "f1d979f7-22d8-4c25-81a4-256b95709ee6"
HALO_PSA_CLIENT_SECRET = "8bc61385-6990-46c4-8ffe-ff5f75ecd0f8-75b7d638-c689-4708-b986-f2f7ef6ad268"
HALO_PSA_BASE_URL = "https://opendoormsp.halopsa.com"
TOKEN_URL = f"{HALO_PSA_BASE_URL}/auth/token"

# Categories (Adjust if needed)
CATEGORIES = [137, 155, 162]  # Example category IDs

# Random ticket subjects and details
TICKET_SUBJECTS = [
    "System Crash on Login",
    "Email Sync Issue",
    "Printer Not Connecting",
    "VPN Connection Drops",
    "Software Installation Fails",
    "Slow Internet Speed",
    "Access Denied to SharePoint",
    "Computer Keeps Restarting"
]

TICKET_DETAILS = [
    "User reports their system crashes when logging in. No error message displayed.",
    "Email sync issue detected on Outlook 365. Messages not updating.",
    "Printer is not responding. Connected via network but fails to print.",
    "VPN drops connection intermittently after 10 minutes of use.",
    "Software installation fails with error code 0x80004005.",
    "Internet speed suddenly drops below 10 Mbps on corporate WiFi.",
    "User cannot access the company SharePoint. Receiving permission error.",
    "Laptop restarts unexpectedly when launching heavy applications."
]

# Token storage
ACCESS_TOKEN = None
TOKEN_EXPIRATION = 0

def get_access_token():
    """Fetches a new access token from HaloPSA and refreshes it when needed."""
    global ACCESS_TOKEN, TOKEN_EXPIRATION

    if ACCESS_TOKEN and time.time() < TOKEN_EXPIRATION:
        return ACCESS_TOKEN

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
        TOKEN_EXPIRATION = time.time() + expires_in - 60  # Refresh 1 min before expiry
        print("✅ Retrieved New Access Token")
        return ACCESS_TOKEN
    else:
        print(f"❌ Failed to retrieve access token: {response.text}")
        raise Exception("Failed to retrieve access token")

def create_test_ticket():
    """Create a randomized test ticket in HaloPSA."""
    global ACCESS_TOKEN
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "summary": f"TEST - {random.choice(TICKET_SUBJECTS)}",
        "details": random.choice(TICKET_DETAILS),
        "user_id": 125,  # Assign to test user (adjust if needed)
        "categoryid_1": random.choice(CATEGORIES),
        "impact": random.randint(1, 3),  # Random impact (1 = High, 2 = Medium, 3 = Low)
        "urgency": random.randint(1, 3)  # Random urgency (1 = High, 2 = Medium, 3 = Low)
    }

    response = requests.post(f"{HALO_PSA_BASE_URL}/tickets", json=payload, headers=headers)

    if response.status_code == 201:
        print(f"✅ Successfully created test ticket: {response.json()['id']} - {payload['summary']}")
        return response.json()
    else:
        print(f"❌ Failed to create test ticket: {response.text}")
        return None

def generate_test_tickets(count=5):
    """Generate multiple test tickets."""
    get_access_token()  # Ensure we have a valid token

    print(f"🚀 Creating {count} test tickets in HaloPSA...")
    for _ in range(count):
        create_test_ticket()
        time.sleep(1)  # Avoid spamming API
    print("✅ Test ticket generation complete.")

if __name__ == "__main__":
    num_tickets = int(input("Enter the number of test tickets to create: "))
    generate_test_tickets(num_tickets)
