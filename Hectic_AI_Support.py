import os
import requests
import json
import time
import chromadb
import difflib
from datetime import datetime, timezone
import openai

# 🔒 Secure API Credentials
HALO_PSA_CLIENT_ID = os.getenv("HALO_PSA_CLIENT_ID")
HALO_PSA_CLIENT_SECRET = os.getenv("HALO_PSA_CLIENT_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 🔗 API Endpoints
HALO_PSA_BASE_URL = "https://opendoormsp.halopsa.com"
TOKEN_URL = f"{HALO_PSA_BASE_URL}/auth/token"
TICKET_URL = f"{HALO_PSA_BASE_URL}/api/tickets"
ACTION_URL = f"{HALO_PSA_BASE_URL}/api/actions"

# 🔑 Token Storage
ACCESS_TOKEN = None
TOKEN_EXPIRATION = 0

# ✅ Initialize ChromaDB for ticket storage
chroma_client = chromadb.PersistentClient(path="./chroma_db")
ticket_collection = chroma_client.get_or_create_collection("tickets")


# 🔹 FUNCTION: GET ACCESS TOKEN
def get_access_token():
    """Retrieve a new HaloPSA API token if expired."""
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


# 🔹 FUNCTION: FETCH TICKETS
def fetch_tickets():
    """Fetch only 'New' tickets from HaloPSA and store them in ChromaDB."""
    headers = {"Authorization": f"Bearer {get_access_token()}"}
    response = requests.get(TICKET_URL, headers=headers)

    if response.status_code != 200:
        print(f"❌ Failed to fetch tickets: {response.text}")
        return []

    try:
        tickets = response.json().get("tickets", [])
        new_tickets = [t for t in tickets if t.get("status_id") == 1]

        print(f"\n🎫 Retrieved {len(new_tickets)} 'New' tickets for processing.")

        # Store tickets in ChromaDB
        for ticket in new_tickets:
            ticket_id = str(ticket.get("id"))
            existing = ticket_collection.get(ids=[ticket_id])

            if existing["ids"]:
                print(f"⚠️ Ticket {ticket_id} already exists in ChromaDB. Skipping insert.")
                continue

            ticket_collection.add(
                ids=[ticket_id],
                metadatas=[ticket],
                documents=[f"Summary: {ticket.get('summary', 'No Summary')}\nDetails: {ticket.get('details', 'No Details')}"]
            )

        return new_tickets

    except json.JSONDecodeError:
        print("❌ Error decoding tickets. API response was not JSON.")
        return []


# 🔹 FUNCTION: AI ANALYSIS (Moved Above `process_tickets()`)
def analyze_ticket_with_ai(summary, details):
    """Analyze ticket details using AI and return structured recommendations."""

    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    # Truncate input to avoid exceeding token limits
    max_summary_length = 1000
    max_details_length = 3000
    summary = summary[:max_summary_length] + "..." if len(summary) > max_summary_length else summary
    details = details[:max_details_length] + "..." if len(details) > max_details_length else details

    prompt = f"""
    You are an AI support assistant. Given the following IT support ticket, analyze it and determine:
    - Urgency: Low, Medium, or High
    - Impact: No impact, Moderate, or High impact
    - Suggested Ticket Type: Incident, Service Request, or Other
    - Assignment: Should it be assigned to an AI bot or a human?

    Ticket Summary: {summary}
    Ticket Details: {details}

    Provide the output in JSON format with keys: urgency, impact, ticket_type, assign_to, reasoning.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "system", "content": "You are a helpful AI support assistant."},
                      {"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.5
        )

        ai_output = response.choices[0].message.content.strip()
        structured_output = json.loads(ai_output)

        return structured_output

    except Exception as e:
        print(f"❌ AI Analysis Error: {e}")
        return None


# 🔹 FUNCTION: PROCESS TICKETS
def process_tickets(tickets):
    """Process and update tickets with AI-generated reasoning."""
    if not tickets:
        print("✅ No new tickets to process.")
        return

    for ticket in tickets:
        ticket_id = ticket["id"]
        summary = ticket.get("summary", "No Summary")
        details = ticket.get("details", "No Details")

        print(f"\n📌 Processing Ticket #{ticket_id}")

        ai_recommendation = analyze_ticket_with_ai(summary, details)
        if not ai_recommendation:
            continue

        update_ticket(ticket_id, ai_recommendation["urgency"], ai_recommendation["impact"],
                      ai_recommendation["ticket_type"], ai_recommendation["assign_to"], ai_recommendation["reasoning"])

# 🔹 FUNCTION: Update Ticket Status
def update_ticket_status(ticket_id, new_status_id):
    """Update the status of a HaloPSA ticket using POST."""
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }
    payload = [
        {
            "id": ticket_id,
            "status_id": new_status_id
        }
    ]

    print(f"📤 Moving Ticket #{ticket_id} to 'In Progress' using POST.")

    response = requests.post(  # ✅ Changed from PUT to POST
        "https://opendoormsp.halopsa.com/api/tickets",  # ✅ Correct endpoint
        json=payload,
        headers=headers
    )

    if response.status_code in [200, 201]:
        print(f"✅ Ticket #{ticket_id} successfully updated to status ID {new_status_id}.")
        return True
    else:
        print(f"❌ Failed to update ticket #{ticket_id}. Status Code: {response.status_code}, Response: {response.text}")
        return False


### ✅ 2️⃣ Function to Add AI Note ###
def add_ticket_note(ticket_id, assign_to, ai_notes):
    """Add an AI-generated private note to a HaloPSA ticket."""
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }
    timestamp = datetime.now(timezone.utc).isoformat()

    # Ensure assigned agent ID is an integer
    try:
        assign_to = int(assign_to)
    except ValueError:
        print(f"⚠️ Invalid agent ID provided: {assign_to}. Defaulting to AI bot agent ID (1).")
        assign_to = 1  # Set to default AI agent ID (update with the correct ID)

    action_payload = [{
        "ticket_id": ticket_id,
        "outcome": "Private Note",
        "who": "AI Support Bot",
        "who_type": 1,
        "who_agentid": assign_to,  # Assign the agent
        "datetime": timestamp,
        "note": f"AI Analysis:\n{ai_notes}\n\n(Ticket moved to 'In Progress' by AI.)",
        "visibility": "private",
        "actionby_agent_id": assign_to,  # Assign agent in action
        "actiondatecreated": timestamp,
        "actioncompletiondate": timestamp,
        "actionarrivaldate": timestamp
    }]

    print(f"📤 Adding AI Note to Ticket #{ticket_id}")

    action_response = requests.post(
        ACTION_URL,  # ✅ Correct API for adding notes
        json=action_payload,
        headers=headers
    )

    if action_response.status_code in [200, 201]:
        print(f"✅ AI Note Added to Ticket #{ticket_id}")
    else:
        print(f"❌ Failed to Add AI Note. Status Code: {action_response.status_code}, Response: {action_response.text}")

### ✅ 3️⃣ Function to Process Ticket Updates ###
def update_ticket(ticket_id, urgency, impact, ticket_type, assign_to, ai_notes):
    """Update a ticket: Move to 'In Progress' and add an AI-generated note."""
    
    # Step 1: Move Ticket to 'In Progress' with correct status_id
    if update_ticket_status(ticket_id, 2):  # ✅ Pass '2' as the new_status_id
        # Step 2: Add AI-generated note only if the status update was successful
        add_ticket_note(ticket_id, assign_to, ai_notes)








# 🔹 MAIN EXECUTION
if __name__ == "__main__":
    print("\n🚀 Starting AI Ticket Triage and Analysis\n")
    process_tickets(fetch_tickets())
    print("🚀 AI Triage workflow complete. Exiting.")
