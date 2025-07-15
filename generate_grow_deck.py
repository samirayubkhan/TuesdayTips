#!/usr/bin/env python3
"""
Generate a new GROW-model presentation from a template deck, fill in placeholders, and return a share-URL.

Prerequisites:
  1. Create/enable a Google Cloud project with Slides & Drive APIs on.
  2. Download your OAuth 2.0 Client credentials as `credentials.json` and place next to this script.
  3. pip install -r requirements.txt

Usage:
  python3 generate_grow_deck.py

The first run opens a browser for OAuth consent; subsequent runs are automatic via token.json.
"""

from __future__ import annotations

import datetime
import pathlib
import sys
from typing import Dict

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ---------------------------------------------------------------------------
# Configuration --------------------------------------------------------------
# ---------------------------------------------------------------------------
TEMPLATE_PRESENTATION_ID: str = "1NR8TMMW7FuQy5x7E2BlAqswf8O4LTwNDs3KnQm56nnM"

# Map of {{placeholder}} → replacement text
PLACEHOLDER_MAP: Dict[str, str] = {
    "{{Title}}": "The GROW Model",
    "{{Subtitle}}": "A simple 4-step framework for continuous personal development.",
    "{{Title 2}}": "Why GROW Works",
    "{{Subtitle 2}}": (
        "It provides a clear and structured path from reflection to action, "
        "cutting through the complexity and overwhelm of setting and achieving goals."
    ),
    "{{Explainer 1}}": (
        "GROW forces you to define a single, clear goal first. It then grounds you "
        "with a reality check, preventing wishful thinking and highlighting where you "
        "currently stand, including your strengths and limitations."
    ),
    "{{Explainer 2}}": (
        "By brainstorming options, you avoid the trap of seeing only one solution. "
        "The final step creates a bias for action, turning your reflection into "
        "immediate momentum with a concrete task."
    ),
    "{{Title 3}}": "How Do I Start?",
    "{{Subtitle 3}}": (
        "You can apply this powerful framework in just 5 minutes with a simple sticky note."
    ),
    "{{Title 4}}": "What is GROW?",
    "{{Subtitle 4}}": (
        "GROW is an acronym for a four-step coaching framework. It guides you to set a clear "
        "Goal (what you want), assess your current Reality (where you are now), explore your "
        "Options (what you can do), and establish a Way Forward (what you will do). "
        "It's a full-circle tool for structured thinking and growth."
    ),
    "{{Title 5}}": "Using GROW",
    "{{Subtitle 5}}": (
        "Grab a card and draw four quadrants: G, R, O, W. Spend one minute on each, "
        "answering the key questions.\n"
        "G: What do I want?\n"
        "R: Where am I now?\n"
        "O: What could I do?\n"
        "W: What will I do first?\n"
        "Place the card where you'll see it daily to stay focused."
    ),
    "{{Tip 1}}": (
        "Pair your weekly GROW review with an existing habit, like Sunday planning, to build consistency."
    ),
    "{{Tip 2}}": (
        "Share your \"Way Forward\" with a friend. Social accountability can boost follow-through by up to 65%."
    ),
    "{{Tip 3}}": (
        "When feeling stuck, add \"yet\" to your thought. For example, \"I haven't figured this out... yet.\""
    ),
    "{{Tip 4}}": (
        "Update the Reality and Way Forward sections weekly as you make progress or circumstances change."
    ),
    "{{Tip 5}}": (
        "Focus on facts, not judgments, in the Reality section. This will give you a clearer picture of the situation."
    ),
    "{{Challenge}}": (
        "Pick one small goal for this week. Run it through the GROW model. Share your \"W\" (Way Forward) in the comments! "
        "What is the one action you will take, and when will you do it? Let's inspire each other to take action!"
    ),
}

# OAuth scopes we need
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/presentations",
]


# ---------------------------------------------------------------------------
# Auth helpers ---------------------------------------------------------------
# ---------------------------------------------------------------------------

def get_credentials() -> Credentials:
    """Load stored creds or run OAuth flow."""
    creds: Credentials | None = None
    token_path = pathlib.Path("token.json")

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(token_path.as_posix(), SCOPES)

    # Refresh expired tokens
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    # Run local-server flow if no valid creds
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    return creds


# ---------------------------------------------------------------------------
# API operations -------------------------------------------------------------
# ---------------------------------------------------------------------------

def copy_presentation(drive_service):
    """Copy the template deck; return new file ID."""
    new_title = f"GROW Model – {datetime.datetime.utcnow():%Y-%m-%d %H:%M:%S}"
    body = {"name": new_title}
    new_file = (
        drive_service.files()
        .copy(fileId=TEMPLATE_PRESENTATION_ID, body=body, fields="id")
        .execute()
    )
    return new_file["id"]


def replace_all_text(slides_service, presentation_id: str):
    """Replace every {{placeholder}} in one batchUpdate call."""
    requests = []
    for placeholder, replacement in PLACEHOLDER_MAP.items():
        requests.append(
            {
                "replaceAllText": {
                    "containsText": {"text": placeholder, "matchCase": True},
                    "replaceText": replacement,
                }
            }
        )

    slides_service.presentations().batchUpdate(
        presentationId=presentation_id,
        body={"requests": requests},
    ).execute()


def make_public(drive_service, file_id: str) -> str:
    """Set anyone-with-link can view and return webViewLink."""
    # Create permission
    drive_service.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"},
        fields="id",
    ).execute()

    # Get link
    meta = drive_service.files().get(fileId=file_id, fields="webViewLink").execute()
    return meta["webViewLink"]


# ---------------------------------------------------------------------------
# Main -----------------------------------------------------------------------
# ---------------------------------------------------------------------------

def main() -> None:
    creds = get_credentials()
    drive_service = build("drive", "v3", credentials=creds)
    slides_service = build("slides", "v1", credentials=creds)

    print("Copying template presentation…", flush=True)
    new_id = copy_presentation(drive_service)
    print(f"  New presentation ID: {new_id}")

    print("Replacing placeholders…", flush=True)
    replace_all_text(slides_service, new_id)

    print("Setting public share link…", flush=True)
    link = make_public(drive_service, new_id)

    print("\n✅ Done! Anyone with the link can view the slide deck:\n" + link)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1) 