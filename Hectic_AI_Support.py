import os
import requests
import json
import time
import chromadb
import difflib
from crewai import Agent, Task, Crew
from langchain.tools import Tool
from datetime import datetime
import openai 

# 🔒 Secure API Credentials (Use environment variables)
HALO_PSA_CLIENT_ID = os.getenv("HALO_PSA_CLIENT_ID")
HALO_PSA_CLIENT_SECRET = os.getenv("HALO_PSA_CLIENT_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 🔗 API Endpoints
HALO_PSA_BASE_URL = "https://opendoormsp.halopsa.com"
TOKEN_URL = f"{HALO_PSA_BASE_URL}/auth/token"
TICKET_URL = f"{HALO_PSA_BASE_URL}/api/tickets"
CATEGORY_URL = f"{HALO_PSA_BASE_URL}/api/categories"
ACTION_URL = f"{HALO_PSA_BASE_URL}/api/actions"

# 🔑 Token Storage
ACCESS_TOKEN = None
TOKEN_EXPIRATION = 0

# ✅ Initialize ChromaDB for ticket storage
chroma_client = chromadb.PersistentClient(path="./chroma_db")
ticket_collection = chroma_client.get_or_create_collection("tickets")


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


#def fetch_categories():
#    """Retrieve categories from HaloPSA API using the correct endpoint."""
#    headers = {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"}
#    category_url = f"{CATEGORY_URL}?showall=true&type_id=1"  # Ensure the correct type_id is used
#
#    response = requests.get(category_url, headers=headers)
#
#    if response.status_code == 200:
#        categories = response.json()
#        category_dict = {cat["name"]: cat["id"] for cat in categories}
#
#        print(f"✅ Retrieved {len(category_dict)} categories.")
#        return category_dict
#    else:
#        print(f"❌ Failed to fetch categories. Status Code: {response.status_code}, Response: {response.text}")
#        return {}


def find_best_category(ticket_summary, categories_dict):
    """Find the best category using fuzzy matching."""
    if not categories_dict:
        return None

    category_names = list(categories_dict.keys())
    best_match = difflib.get_close_matches(ticket_summary, category_names, n=1, cutoff=0.3)

    return categories_dict[best_match[0]] if best_match else None



def update_ticket(ticket_id, ai_notes):
    """Add an AI-generated private note to a ticket in HaloPSA."""
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }

    # Create timestamp in correct format
    timestamp = datetime.utcnow().isoformat() + "Z"

    # Payload to add an action (note)
    note_payload = [{
        "ticket_id": ticket_id,
        "outcome": "Private Note",
        "who": "AI Support Bot",
        "who_type": 1,
        "who_agentid": 3,  # Replace with correct agent ID if needed
        "datetime": timestamp,
        "note": f"AI Analysis:\n{ai_notes}\n\n(Ticket updated by AI.)",
        "visibility": "private",
        "actionby_agent_id": 3,  # Ensure this is the correct agent ID
        "actiondatecreated": timestamp,
        "actioncompletiondate": timestamp,
        "actionarrivaldate": timestamp
    }]

    print(f"📤 Adding AI Note to Ticket #{ticket_id}")

    note_response = requests.post(
        f"{HALO_PSA_BASE_URL}/api/Actions",  # Ensure the correct API version
        json=note_payload,
        headers=headers
    )

    if note_response.status_code in [200, 201]:
        print(f"✅ AI Note Added to Ticket #{ticket_id}")
    else:
        print(f"❌ Failed to Add AI Note. Status Code: {note_response.status_code}, Response: {note_response.text}")




def analyze_ticket_with_ai(summary, details):
    """Analyze ticket details using AI and return structured recommendations."""

    # ✅ Ensure OpenAI API key is set
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    # ✅ Truncate input if necessary to avoid exceeding token limits
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
            messages=[
                {"role": "system", "content": "You are a helpful AI support assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.5
        )

        ai_output = response.choices[0].message.content.strip()
        structured_output = json.loads(ai_output)

        return structured_output

    except Exception as e:
        print(f"❌ AI Analysis Error: {e}")
        return None








def process_tickets(tickets):
    """Process and update tickets with AI-generated reasoning."""
    if not tickets:
        print("✅ No new tickets to process.")
        return

    print(f"🚀 Processing {len(tickets)} tickets...")

    for ticket in tickets:
        ticket_id = ticket.get("id")
        summary = ticket.get("summary", "No Summary")
        details = ticket.get("details", "No Details")

        print(f"\n📌 **Processing Ticket #{ticket_id}**")

        ai_recommendation = analyze_ticket_with_ai(summary, details)
        if not ai_recommendation:
            print(f"⚠️ AI analysis failed for Ticket #{ticket_id}, skipping.")
            continue

        update_ticket(ticket_id, ai_recommendation["reasoning"])


    print("🚀 AI Processing complete.")


if __name__ == "__main__":
    print("\n🚀 Starting AI Ticket Triage and Analysis\n")
    process_tickets(fetch_tickets())
    print("🚀 AI Triage workflow complete. Exiting.")
