#!/usr/bin/env python3
"""
Generate a new STAR-method presentation from the template deck, fill in placeholders, and return a share-URL.

Usage:
  python3 generate_star_deck.py

Prerequisites are identical to generate_grow_deck.py (credentials.json + requirements).
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

PLACEHOLDER_MAP: Dict[str, str] = {
    "{{Title}}": "The STAR Method",
    "{{Subtitle}}": "A framework for telling powerful stories about your experience.",
    "{{Title 2}}": "Why Use STAR?",
    "{{Subtitle 2}}": (
        "It provides a structured way to craft concise, compelling stories that show hiring managers exactly how you deliver results."
    ),
    "{{Explainer 1}}": (
        "Instead of just listing duties, STAR helps you build a narrative. It gives interviewers the context they need and clarifies what was at stake, making your experience more memorable and impactful."
    ),
    "{{Explainer 2}}": (
        "The framework forces you to focus on your specific actions and, most importantly, the quantifiable results, proving your effectiveness and the value you can bring to the role."
    ),
    "{{Title 3}}": "Where Do I Start?",
    "{{Subtitle 3}}": "By turning your career wins into memorable STAR stories before you even interview.",
    "{{Title 4}}": "What is STAR?",
    "{{Subtitle 4}}": (
        "STAR is a method to structure your interview answers. **S**ituation: Set the scene and context. **T**ask: Define your goal or the problem you faced. **A**ction: Detail the specific steps you personally took. **R**esult: Share the quantifiable outcome of your actions. It’s a blueprint for proving your skills with concrete evidence."
    ),
    "{{Title 5}}": "Using STAR",
    "{{Subtitle 5}}": (
        "Review the job description for key skills. For each, brainstorm a relevant experience. Break it down into bullet points for Situation, Task, Action, and Result. Focus most of your detail on the Action you took and the Result you achieved. Aim to tell the full story in under 2 minutes."
    ),
    "{{Tip 1}}": "Quantify your results. Use metrics like revenue gained, time saved, or error rates reduced to show concrete impact.",
    "{{Tip 2}}": "Avoid using 'we' too much. Focus on your specific contribution and clarify your individual role in the team's success.",
    "{{Tip 3}}": "Keep the Situation and Task sections brief. The interviewer cares most about what you did (Action) and what happened (Result).",
    "{{Tip 4}}": "Prepare 2-3 different stories for each core skill (e.g., leadership, problem-solving) so you have varied examples.",
    "{{Tip 5}}": "Always conclude by connecting your story's result to the value you can specifically bring to this new role.",
    "{{Challenge}}": (
        "Think of one achievement you're proud of. In the comments, share just the 'A' (Action) and 'R' (Result). What specific steps did you take, and what was the measurable outcome? Let's see some impactful stories!"
    ),
}

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/presentations",
]

# ---------------------------------------------------------------------------
# Auth helpers ---------------------------------------------------------------
# ---------------------------------------------------------------------------

def get_credentials() -> Credentials:
    creds: Credentials | None = None
    token_path = pathlib.Path("token.json")
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(token_path.as_posix(), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())
    return creds

# ---------------------------------------------------------------------------
# API helpers ----------------------------------------------------------------
# ---------------------------------------------------------------------------

def copy_presentation(drive_service):
    title = f"STAR Method – {datetime.datetime.utcnow():%Y-%m-%d %H:%M:%S}"
    new_file = (
        drive_service.files()
        .copy(fileId=TEMPLATE_PRESENTATION_ID, body={"name": title}, fields="id")
        .execute()
    )
    return new_file["id"]


def replace_all_text(slides_service, presentation_id: str):
    requests = [
        {
            "replaceAllText": {
                "containsText": {"text": ph, "matchCase": True},
                "replaceText": repl,
            }
        }
        for ph, repl in PLACEHOLDER_MAP.items()
    ]
    slides_service.presentations().batchUpdate(
        presentationId=presentation_id, body={"requests": requests}
    ).execute()


def make_public(drive_service, file_id: str) -> str:
    drive_service.permissions().create(
        fileId=file_id, body={"role": "reader", "type": "anyone"}, fields="id"
    ).execute()
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
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1) 