import os
import requests
import json
import time
import chromadb
import difflib
from crewai import Agent, Task, Crew
from langchain.tools import Tool
from openai import OpenAI

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


def fetch_categories():
    """Retrieve categories from HaloPSA API and store them in a dictionary."""
    headers = {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"}
    response = requests.get(CATEGORY_URL, headers=headers)

    if response.status_code == 200:
        categories = response.json()
        return {cat["name"]: cat["id"] for cat in categories}
    else:
        print(f"❌ Failed to fetch categories: {response.text}")
        return {}


def find_best_category(ticket_summary, categories_dict):
    """Find the best category using fuzzy matching."""
    if not categories_dict:
        return None

    category_names = list(categories_dict.keys())
    best_match = difflib.get_close_matches(ticket_summary, category_names, n=1, cutoff=0.3)

    return categories_dict[best_match[0]] if best_match else None


def update_ticket(ticket_id, ticket_summary, urgency, impact, ticket_type, assign_to, ai_notes):
    """Update a ticket in HaloPSA with AI-selected category and add an AI note."""
    headers = {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"}

    categories_dict = fetch_categories()
    category_id = find_best_category(ticket_summary, categories_dict) or 137  # Default category

    ticket_update_payload = {
        "categoryid_1": category_id,
        "urgency": {"Low": 1, "Medium": 2, "High": 3}.get(urgency, 2),
        "impact": {"No impact": 1, "Moderate": 2, "High impact": 3}.get(impact, 2),
        "type": ticket_type,
        "assigned_to": assign_to,
        "status_id": 2
    }

    print(f"📤 Updating Ticket #{ticket_id} with category {category_id}")
    update_response = requests.patch(f"{TICKET_URL}/{ticket_id}", json=ticket_update_payload, headers=headers)

    if update_response.status_code in [200, 201]:
        print(f"✅ Updated Ticket #{ticket_id}")
    else:
        print(f"❌ Update Failed: {update_response.text}")
        return False

    action_payload = [{
        "ticket_id": ticket_id,
        "outcome": "Private Note",
        "who": "AI Support Bot",
        "who_type": 1,
        "note": f"AI Analysis:\n{ai_notes}\n\n(Ticket moved to 'In Progress' by AI.)",
        "visibility": "private"
    }]

    print(f"📤 Adding AI Note to Ticket #{ticket_id}")
    action_response = requests.post(ACTION_URL, json=action_payload, headers=headers)

    if action_response.status_code in [200, 201]:
        print(f"✅ AI Note Added to Ticket #{ticket_id}")
    else:
        print(f"❌ Failed to Add AI Note: {action_response.text}")


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

        update_ticket(
            ticket_id, summary,
            ai_recommendation["urgency"],
            ai_recommendation["impact"],
            ai_recommendation["ticket_type"],
            ai_recommendation["assign_to"],
            ai_recommendation["reasoning"]
        )

    print("🚀 AI Processing complete.")


if __name__ == "__main__":
    print("\n🚀 Starting AI Ticket Triage and Analysis\n")
    process_tickets(fetch_tickets())
    print("🚀 AI Triage workflow complete. Exiting.")
