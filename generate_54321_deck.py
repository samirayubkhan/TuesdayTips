#!/usr/bin/env python3
"""
Generate a new 5-4-3-2-1 Rule presentation by copying the template deck,
replacing placeholders, and outputting a public share link.

Run:  python3 generate_54321_deck.py
"""

from __future__ import annotations

import datetime
import pathlib
import sys
import time
from typing import Dict

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

TEMPLATE_PRESENTATION_ID: str = "1NR8TMMW7FuQy5x7E2BlAqswf8O4LTwNDs3KnQm56nnM"

PLACEHOLDER_MAP: Dict[str, str] = {
    "{{Title}}": "The 5-4-3-2-1 Rule",
    "{{Subtitle}}": "A simple sensory technique to calm anxiety and be present.",
    "{{Title 2}}": "Why Grounding Matters",
    "{{Subtitle 2}}": (
        "When you feel overwhelmed by anxiety or stress, grounding pulls you out of your head and anchors you in the safety of the present moment."
    ),
    "{{Explainer 1}}": (
        "Anxiety often traps us in future worries or past regrets. This technique interrupts that spiral by shifting your entire focus to the physical world, which exists only in the now."
    ),
    "{{Explainer 2}}": (
        "By engaging your senses, you send a signal to your nervous system that you are safe, helping to reduce the intensity of overwhelming emotions and restore a sense of calm."
    ),
    "{{Title 3}}": "Where Do I Start?",
    "{{Subtitle 3}}": "It's as easy as counting down from 5, using nothing but your five senses.",
    "{{Title 4}}": "What is 5-4-3-2-1?",
    "{{Subtitle 4}}": (
        "It’s a sensory grounding exercise to manage distress. You mindfully notice:\n"
        "5 things you can SEE\n"
        "4 things you can FEEL\n"
        "3 things you can HEAR\n"
        "2 things you can SMELL\n"
        "1 thing you can TASTE\n"
        "It guides your mind back to your immediate surroundings, providing instant relief."
    ),
    "{{Title 5}}": "Using the Method",
    "{{Subtitle 5}}": (
        "When anxiety rises, pause. Look around and silently name 5 objects. Notice the texture of 4 things you can touch (your clothes, a table). Listen and identify 3 distinct sounds. Pinpoint 2 different smells around you. Finally, focus on 1 thing you can taste. Breathe."
    ),
    "{{Tip 1}}": (
        "Practice when you're calm. This builds muscle memory, making it easier to use the tool when you're feeling stressed."
    ),
    "{{Tip 2}}": (
        "Say the items out loud if you can. Hearing your own voice can be an extra layer of grounding and can deepen your focus."
    ),
    "{{Tip 3}}": (
        "Don't worry about finding the 'right' things. The goal isn't perfection, it's just to notice whatever your senses pick up."
    ),
    "{{Tip 4}}": (
        "Combine this technique with slow, deep breaths to enhance the calming effect on your nervous system."
    ),
    "{{Tip 5}}": (
        "You can do this anywhere, anytime. No one even has to know you're doing it. It's your discreet, go-to tool for calm."
    ),
    "{{Challenge}}": (
        "Try it right now. In the comments, share ONE thing you can SEE, ONE thing you can FEEL, and ONE thing you can HEAR from your immediate surroundings. Let's get present together!"
    ),
}

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/presentations",
]


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


def copy_presentation(drive_service):
    title = f"5-4-3-2-1 Rule – {datetime.datetime.utcnow():%Y-%m-%d %H:%M:%S}"
    return (
        drive_service.files()
        .copy(fileId=TEMPLATE_PRESENTATION_ID, body={"name": title}, fields="id")
        .execute()["id"]
    )


def replace_text_with_retry(slides_service, presentation_id: str, retries: int = 3):
    requests = [
        {
            "replaceAllText": {
                "containsText": {"text": ph, "matchCase": True},
                "replaceText": repl,
            }
        }
        for ph, repl in PLACEHOLDER_MAP.items()
    ]
    for attempt in range(1, retries + 1):
        try:
            slides_service.presentations().batchUpdate(
                presentationId=presentation_id, body={"requests": requests}
            ).execute()
            return  # success
        except HttpError as e:
            if e.resp.status in {500, 503} and attempt < retries:
                time.sleep(2 * attempt)  # simple backoff
                continue
            raise


def make_public(drive_service, file_id: str) -> str:
    drive_service.permissions().create(
        fileId=file_id, body={"role": "reader", "type": "anyone"}, fields="id"
    ).execute()
    return drive_service.files().get(fileId=file_id, fields="webViewLink").execute()[
        "webViewLink"
    ]


def main():
    creds = get_credentials()
    drive_service = build("drive", "v3", credentials=creds)
    slides_service = build("slides", "v1", credentials=creds)

    print("Copying template…", flush=True)
    pres_id = copy_presentation(drive_service)
    print(f"  New presentation ID: {pres_id}")

    print("Replacing placeholders…", flush=True)
    replace_text_with_retry(slides_service, pres_id)

    print("Setting public link…", flush=True)
    url = make_public(drive_service, pres_id)

    print("\n✅ Deck ready: " + url)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1) 