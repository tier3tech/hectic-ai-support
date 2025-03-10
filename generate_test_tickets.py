import requests
import random
import time

# Configuration - Replace with actual credentials
HALO_PSA_CLIENT_ID = "f1d979f7-22d8-4c25-81a4-256b95709ee6"
HALO_PSA_CLIENT_SECRET = "8bc61385-6990-46c4-8ffe-ff5f75ecd0f8-75b7d638-c689-4708-b986-f2f7ef6ad268"
HALO_PSA_BASE_URL = "https://opendoormsp.halopsa.com"
TOKEN_URL = f"{HALO_PSA_BASE_URL}/auth/token"
CREATE_TICKET_URL = f"{HALO_PSA_BASE_URL}/api/tickets"

# Store the access token globally
ACCESS_TOKEN = None
TOKEN_EXPIRATION = 0

# Sample test data for random ticket generation
TICKET_TITLES = [
    "System is slow", "Printer not working", "Cannot access VPN",
    "Email issues", "WiFi keeps disconnecting", "Software installation request",
    "Security warning popup", "Laptop screen flickering", "Can't log into application",
    "Missing network drive"
]

TICKET_DETAILS = [
    "User reports performance issues across applications.",
    "Printer is not responding even after rebooting.",
    "User is unable to connect to the corporate VPN.",
    "Emails are bouncing back for external recipients.",
    "WiFi randomly drops, affecting user productivity.",
    "Request to install software for finance team.",
    "Security alert popup appearing on login.",
    "Screen flickers when adjusting brightness.",
    "User unable to log into company portal.",
    "Shared drive is missing from file explorer."
]

# These IDs should match what was used in the successful test
DEFAULT_USER_ID = 125
DEFAULT_CATEGORY_ID = 137
DEFAULT_IMPACT = 2
DEFAULT_URGENCY = 3

def get_access_token():
    """Retrieve and refresh the HaloPSA API token."""
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
        expires_in = token_data.get("expires_in", 3600)
        TOKEN_EXPIRATION = time.time() + expires_in - 60
        print("✅ Retrieved New Access Token")
        return ACCESS_TOKEN
    else:
        print(f"❌ Failed to retrieve access token: {response.text}")
        raise Exception("Failed to retrieve access token")

def create_test_ticket():
    """Creates a single test ticket in HaloPSA with the correct format."""
    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    ticket_payload = [{
        "summary": f"TEST - {random.choice(TICKET_TITLES)}",
        "details": random.choice(TICKET_DETAILS),
        "user_id": DEFAULT_USER_ID,
        "categoryid_1": DEFAULT_CATEGORY_ID,
        "impact": DEFAULT_IMPACT,
        "urgency": DEFAULT_URGENCY
    }]

    response = requests.post(CREATE_TICKET_URL, json=ticket_payload, headers=headers)

    # Debugging response content
    print(f"🔍 API Response ({response.status_code}): {response.text}")

    if response.status_code in [200, 201]:
        ticket_data = response.json()

        # Ensure response is a list and contains at least one item
        if isinstance(ticket_data, list) and len(ticket_data) > 0 and "id" in ticket_data[0]:
            print(f"✅ Successfully created test ticket: {ticket_data[0]['id']} - {ticket_payload[0]['summary']}")
        else:
            print(f"⚠️ Ticket creation response format unexpected: {ticket_data}")
    else:
        print(f"❌ Failed to create test ticket: {response.status_code} - {response.text}")

def main():
    num_tickets = int(input("Enter the number of test tickets to create: "))
    print(f"🚀 Creating {num_tickets} test tickets in HaloPSA...")

    for _ in range(num_tickets):
        create_test_ticket()
        time.sleep(1)  # Slight delay to avoid rate-limiting

    print("✅ Test ticket generation complete.")

if __name__ == "__main__":
    main()
