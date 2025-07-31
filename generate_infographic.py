# Generate Infographic
import re
import datetime
import pathlib
from typing import Dict, Tuple

import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import json
import io
import html  # for escaping strings in clipboard button
import streamlit.components.v1 as components
import zipfile
import requests
import os
from google.oauth2 import service_account
import urllib.parse
from google_auth_oauthlib.flow import Flow

print("Current working directory:", os.getcwd())
print("Files in current directory:", os.listdir())

# ---------------------------------------------------------------------------
# Streamlit rerun helper (must be defined early) ----------------------------
# ---------------------------------------------------------------------------

if "_rerun" not in globals():
    def _rerun():
        """Streamlit rerun compatible with different versions."""
        if hasattr(st, "experimental_rerun"):
            st.experimental_rerun()
        else:
            st.rerun()

# ---------------------------------------------------------------------------
# Utility to build slide thumbnails ZIP -------------------------------------
# ---------------------------------------------------------------------------

def build_slide_images_zip(
    creds: Credentials, slides_svc, presentation_id: str
) -> io.BytesIO:
    """Return an in-memory ZIP containing PNGs for each slide."""
    pres_meta = slides_svc.presentations().get(
        presentationId=presentation_id, fields="slides.objectId"
    ).execute()
    slide_ids = [s["objectId"] for s in pres_meta.get("slides", [])]

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, slide_id in enumerate(slide_ids, 1):
            # Attempt LARGE → MEDIUM → SMALL thumbnail sizes
            for size in ("LARGE", "MEDIUM", "SMALL"):
                try:
                    thumb = (
                        slides_svc.presentations()
                        .pages()
                        .getThumbnail(
                            presentationId=presentation_id,
                            pageObjectId=slide_id,
                            thumbnailProperties_thumbnailSize=size,
                            thumbnailProperties_mimeType="PNG",
                        )
                        .execute()
                    )
                    img_url = thumb["contentUrl"]

                    headers = {"Authorization": f"Bearer {creds.token}"}

                    # Retry network fetch up to 3 times
                    success = False
                    for attempt in range(3):
                        try:
                            resp = requests.get(img_url, headers=headers, timeout=30)
                            resp.raise_for_status()
                            zf.writestr(f"slide_{idx:02d}.png", resp.content)
                            success = True
                            break
                        except requests.exceptions.HTTPError as http_err:
                            # Retry on server-side errors (>=500)
                            if resp.status_code >= 500 and attempt < 2:
                                continue
                            else:
                                raise http_err

                    if success:
                        break  # thumbnail saved, proceed to next slide
                except Exception:
                    # Try next size or raise after SMALL fails
                    if size == "SMALL":
                        raise
                    continue

    zip_buf.seek(0)
    return zip_buf

# ---------------------------------------------------------------------------
# Clipboard helper ----------------------------------------------------------
# ---------------------------------------------------------------------------


def clipboard_button(text: str, label: str = "Copy", key: str | None = None):
    """Render an HTML/JS button that copies *text* to the browser clipboard.

    This works entirely client-side, so it does not require any server-side
    clipboard library. The *key* ensures unique element IDs when the function
    is used multiple times on the same page.
    """
    if key is None:
        # Fallback to a simple hash for uniqueness
        key = str(abs(hash(text)) % 10_000_000)

    safe_text = html.escape(text)
    btn_id = f"btn_{key}"
    txt_id = f"txt_{key}"

    # Inline JS copies the hidden textarea content to clipboard and gives UX
    # feedback by temporarily changing the button label. Basic CSS makes it look
    # close to Streamlit's default button style.
    components.html(
        f"""
        <style>
        .copy-btn {{
            background-color: #05F283 !important;
            color: #002B56 !important;
            border: none;
            border-radius: 0.25rem;
            padding: 0.4rem 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: background-color 0.2s ease;
        }}
        .copy-btn:hover {{
            background-color: #05c26a !important;
        }}
        </style>
        <textarea id='{txt_id}' style='position:absolute; left:-1000px; top:-1000px;'>{safe_text}</textarea>
        <button class='copy-btn' id='{btn_id}'>{label}</button>
        <script>
        const btn = document.getElementById('{btn_id}');
        btn.addEventListener('click', () => {{
            const txt = document.getElementById('{txt_id}');
            txt.select();
            document.execCommand('copy');
            const original = btn.innerText;
            btn.innerText = '✔ Copied!';
            setTimeout(() => btn.innerText = original, 2000);
        }});
        </script>
        """,
        height=40,
    )

# ---------------------------------------------------------------------------
# Configuration --------------------------------------------------------------
# ---------------------------------------------------------------------------
import os as _os  # Added for env-var overrides
# ⚠️  Replace this with the ID of your own Tuesday-Tips template deck that
# contains all of the placeholders listed in TEMPLATE_PLACEHOLDERS.
# Template configurations
TEMPLATE_CONFIGS = {
    "Template Version 1": {
        "id": _os.getenv(
            "TEMPLATE_PRESENTATION_ID",
            "1xQTez0asRJzxstqW8zCUtIGpFRlPUH-RtMVL533N1Qs",
        ),
        "name": "Template Version 1"
    },
    "Template Number 2": {
        "id": "1CgiUM_6ZSkbwDMfKCbvPD3UYL5-7Tirw8_lVAFGA17g",
        "name": "Template Number 2"
    }
}

# Default template for backwards compatibility
TEMPLATE_PRESENTATION_ID: str = TEMPLATE_CONFIGS["Template Version 1"]["id"]
# ID of the Google Drive folder where new slide decks should be saved
DESTINATION_FOLDER_ID: str = _os.getenv("DESTINATION_FOLDER_ID", "1y-f2hHLl102Wj1ff6cURa7GLT5oaOwpt")

# The placeholders we expect in the template deck.  These keys are parsed from
# the user-supplied text and then sent to the Google Slides API in a single
# batchUpdate request.
TEMPLATE_PLACEHOLDERS = [
    "{{Title}}",
    "{{Subtitle}}",
    "{{Lesson 1 Title}}",
    "{{Lesson 1 Subtitle}}",
    "{{Lesson 1 Explainer 1}}",
    "{{Lesson 1 Explainer 2}}",
    "{{Lesson 1 List Title}}",
    "{{Lesson 1 List Point 1}}",
    "{{Lesson 1 List Point 2}}",
    "{{Lesson 1 List Point 3}}",
    "{{Lesson 1 List Point 4}}",
    "{{Lesson 1 List Point 5}}",
    "{{Lesson 1 Case Title}}",
    "{{Lesson 1 Case Description}}",
    "{{Lesson 2 Title}}",
    "{{Lesson 2 Subtitle}}",
    "{{Lesson 2 Explainer 1}}",
    "{{Lesson 2 Explainer 2}}",
    "{{Lesson 2 List Title}}",
    "{{Lesson 2 List Point 1}}",
    "{{Lesson 2 List Point 2}}",
    "{{Lesson 2 List Point 3}}",
    "{{Lesson 2 List Point 4}}",
    "{{Lesson 2 List Point 5}}",
    "{{Lesson 2 Case Title}}",
    "{{Lesson 2 Case Description}}",
    "{{Lesson 3 Title}}",
    "{{Lesson 3 Subtitle}}",
    "{{Lesson 3 Explainer 1}}",
    "{{Lesson 3 Explainer 2}}",
    "{{Lesson 3 List Title}}",
    "{{Lesson 3 List Point 1}}",
    "{{Lesson 3 List Point 2}}",
    "{{Lesson 3 List Point 3}}",
    "{{Lesson 3 List Point 4}}",
    "{{Lesson 3 List Point 5}}",
    "{{Lesson 3 Case Title}}",
    "{{Lesson 3 Case Description}}",
    "{{Lesson 4 Title}}",
    "{{Lesson 4 Subtitle}}",
    "{{Lesson 4 Explainer 1}}",
    "{{Lesson 4 Explainer 2}}",
    "{{Lesson 4 List Title}}",
    "{{Lesson 4 List Point 1}}",
    "{{Lesson 4 List Point 2}}",
    "{{Lesson 4 List Point 3}}",
    "{{Lesson 4 List Point 4}}",
    "{{Lesson 4 List Point 5}}",
    "{{Lesson 4 Case Title}}",
    "{{Lesson 4 Case Description}}",
    "{{Activity Title}}",
    "{{Activity Instructions}}",
]

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/presentations",
]

# ---------------------------------------------------------------------------
# Helper functions -----------------------------------------------------------
# ---------------------------------------------------------------------------

# --- New OAuth web redirect flow ---
def get_credentials() -> Credentials:
    """Return valid user credentials (Service Account if USE_SERVICE_ACCOUNT=1, else OAuth 2.0 web flow)."""
    import os, json
    from pathlib import Path
    from google_auth_oauthlib.flow import Flow

    # 1) Service-account flow (unchanged)
    if os.environ.get("USE_SERVICE_ACCOUNT") == "1":
        sa_json_env = os.environ.get("SERVICE_ACCOUNT_JSON")
        if sa_json_env:
            info = json.loads(sa_json_env)
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=SCOPES
            )
        else:
            creds = service_account.Credentials.from_service_account_file(
                "service_account.json", scopes=SCOPES
            )
        return creds

    # 2) Web app OAuth flow
    token_path = Path("token.json")
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(token_path.as_posix(), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        if creds and creds.valid:
            return creds

    # --- Begin OAuth web flow ---
    client_json_env = os.environ.get("OAUTH_CLIENT_JSON")
    if not client_json_env:
        st.error("OAUTH_CLIENT_JSON environment variable is not set. Please provide your OAuth client config as a JSON string.")
        st.stop()
    try:
        client_cfg = json.loads(client_json_env)
    except json.JSONDecodeError as exc:
        st.error(f"Invalid OAUTH_CLIENT_JSON: {exc}")
        st.stop()

    redirect_uri = os.environ.get(
        "OAUTH_REDIRECT_URI",
        "https://tuesdaytips-937927832386.europe-west1.run.app/"
    )

    # Check for ?code= in the URL (Google redirect)
    params = st.experimental_get_query_params()
    code = params.get("code", [None])[0]

    if code:
        # Phase 2: Google redirected back with code
        state = st.session_state.pop("oauth_state", None)
        flow = Flow.from_client_config(client_cfg, SCOPES, state=state)
        flow.redirect_uri = redirect_uri
        flow.fetch_token(code=code)
        creds = flow.credentials
        token_path.write_text(creds.to_json())
        st.experimental_set_query_params()  # clear ?code=...
        st.success("Google authorisation complete! Reloading …")
        _rerun()
        st.stop()

    # Phase 1: need authorisation
    flow = Flow.from_client_config(client_cfg, SCOPES)
    flow.redirect_uri = redirect_uri
    auth_url, state = flow.authorization_url(prompt="consent")
    st.session_state["oauth_state"] = state
    st.info("First-time Google authorisation required.")
    st.markdown(f"[Click here to authorise with Google]({auth_url})")
    st.stop()


def copy_template_presentation(
    drive_service,
    title: str,
    parent_folder_id: str | None = None,
    template_id: str | None = None,
) -> str:
    """Create a copy of the template deck with *title*.

    If *parent_folder_id* is provided, the new file will be placed inside that
    Google Drive folder. If *template_id* is provided, that template will be
    used instead of the default. Returns the ID of the newly created slide deck.
    """
    # Use provided template_id or fall back to default
    template_to_use = template_id or TEMPLATE_PRESENTATION_ID
    
    # Create the copy first (without parents) to avoid potential 404 errors if
    # the destination folder is not accessible. We will move it in a second
    # call using files.update.
    new_file = (
        drive_service.files()
        .copy(
            fileId=template_to_use,
            body={"name": title},
            fields="id",
            supportsAllDrives=True,
        )
        .execute()
    )

    file_id: str = new_file["id"]

    # Move the new file into the destination folder if provided.
    if parent_folder_id:
        try:
            drive_service.files().update(
                fileId=file_id,
                addParents=parent_folder_id,
                supportsAllDrives=True,
                fields="id",
            ).execute()
        except Exception as move_exc:
            # Log or surface a warning in Streamlit but don't block deck creation
            st.warning(
                f"Could not move slide deck into the destination folder: {move_exc}. "
                "The deck was still created in your Drive root."
            )

    return file_id


def replace_placeholders(slides_service, presentation_id: str, mapping: Dict[str, str]) -> None:
    """Replace all placeholders in *mapping* inside the presentation."""
    requests = [
        {
            "replaceAllText": {
                "containsText": {"text": ph, "matchCase": True},
                "replaceText": mapping[ph],
            }
        }
        for ph in mapping
    ]
    slides_service.presentations().batchUpdate(
        presentationId=presentation_id, body={"requests": requests}
    ).execute()


def make_deck_public(drive_service, file_id: str) -> str:
    """Make the slide deck viewable by anyone with the link and return it.

    The additional *supportsAllDrives* flag ensures that this works even when the
    file lives in a shared drive.
    """

    drive_service.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"},
        fields="id",
        supportsAllDrives=True,
    ).execute()

    meta = (
        drive_service.files()
        .get(fileId=file_id, fields="webViewLink", supportsAllDrives=True)
        .execute()
    )
    return meta["webViewLink"]


def parse_user_content(text: str) -> Tuple[Dict[str, str], list[str]]:
    """Parse the pasted AI output into a mapping of placeholder → value.

    Returns a (mapping, errors) tuple where *errors* is a list of placeholder
    keys that were missing from the user-supplied text.
    """
    mapping: Dict[str, str] = {}

    # Pattern to match {+ [^}]+ }+
    pattern = re.compile(r"(\{{1,}[^}]+\}{1,})\s*(.*)")
    for idx, line in enumerate(text.splitlines()):
        m = pattern.match(line.strip())
        if m:
            raw_key, val = m.groups()
            # Normalize to double braces without extra spaces
            inner = re.sub(r'^\{+', '', raw_key)
            inner = re.sub(r'\}+$', '', inner).strip()
            key = "{{" + inner + "}}"
            if key in TEMPLATE_PLACEHOLDERS:
                if val.strip():
                    mapping[key] = val.strip()
                else:
                    # If value is on the next non-empty line, capture it.
                    next_val = ""
                    for nxt in text.splitlines()[idx + 1 :]:
                        if nxt.strip():
                            next_val = nxt.strip()
                            break
                    mapping[key] = next_val

    missing = [ph for ph in TEMPLATE_PLACEHOLDERS if ph not in mapping]
    return mapping, missing


# ---------------------------------------------------------------------------
# Streamlit UI --------------------------------------------------------------
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Generate Infographic", page_icon="💡", layout="centered")

def check_password():
    """Returns `True` if the user has the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == "generateamazingtipsALX":
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password.
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password.
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error.
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Password incorrect")
        return False
    else:
        # Password correct.
        return True

if not check_password():
    st.stop()

st.title("Generate Tuesday Tips Infographic")

st.markdown("""
Welcome! This mini-app helps you turn your AI-generated content into a polished Google Slides deck in just **four easy steps**.

You will be using Gemini 2.5 Pro to generate the content.

You can access gemini pro here: https://gemini.google.com/
""")

# Template selection
st.subheader("📋 Choose Slide Template")
selected_template = st.selectbox(
    "Select a slide template to use for your infographic:",
    options=list(TEMPLATE_CONFIGS.keys()),
    index=0,
    help="Choose between different slide templates. Template Version 1 is the original template, Template Number 2 provides an alternative design."
)

# Store selected template in session state
if "selected_template" not in st.session_state:
    st.session_state["selected_template"] = selected_template
else:
    st.session_state["selected_template"] = selected_template

st.markdown("---")  # Add separator

topic = st.text_input("Enter the Topic of the Infographic:")

# Step 1
st.header("Step 1: Defining Topics and Subtopics")

prompt1 = f"""
You’re an instructional designer with experience in creating learning content for online courses designed for young adults. For the following theme, define the list of topics and subtopics that need to be covered by the learners in order to completely understand and apply the theme. Create this as a list (with sublists if needed). 

The topic is: {topic} 
"""

st.markdown(
    "<div style='display: flex; justify-content: flex-end; margin-bottom: -10px;'>",
    unsafe_allow_html=True,
)
clipboard_button(prompt1, label="Copy Step 1 Prompt", key="p1")
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("1️⃣ This prompt will be used to generate the topics and subtopics for the infographic.")
with st.expander("View Step 1 Prompt", expanded=False):
    st.code(prompt1, language="text")

# Step 1 output box removed – keep placeholder variable
step1_output = ""

# Step 2
st.header("Step 2: Define and Refine the List")

prompt2 = f"""
You’re an instructional designer with experience in creating learning content for online courses designed for young adults. For the theme {topic}, redefine the topics and subtopics generated in the previous step into 4 lessons. Create 4 lesson outlines in a logical order, limiting each lesson to 3–4 topics or subtopics that are most relevant to the theme.
"""

st.markdown(
    "<div style='display: flex; justify-content: flex-end; margin-bottom: -10px;'>",
    unsafe_allow_html=True,
)
clipboard_button(prompt2, label="Copy Step 2 Prompt", key="p2")
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("2️⃣ This prompt will be used to generate the lessons for the infographic.")
with st.expander("View Step 2 Prompt", expanded=False):
    st.code(prompt2, language="text")

# Step 2 output box removed – keep placeholder variable
step2_output = ""

# Step 3
st.header("Step 3: Generating Main Content")

prompt3 = f"""
You’re an instructional designer with experience in creating learning content for online courses designed for young adults. For the lessons outlined above for {topic}, create a detailed set of content that will help learners fully understand the concepts and be able to apply them. Create this content as a series of lessons set up in a logical sequence. Make use of questions, interesting facts, relevant examples and case studies to keep learners engaged.
"""

st.markdown(
    "<div style='display: flex; justify-content: flex-end; margin-bottom: -10px;'>",
    unsafe_allow_html=True,
)
clipboard_button(prompt3, label="Copy Step 3 Prompt", key="p3")
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("3️⃣ This prompt will be used to generate the content for the lessons. Make sure you use *Deep Research* to generate the content.")
with st.expander("View Step 3 Prompt", expanded=False):
    st.code(prompt3, language="text")

# Step 3 output box removed – keep placeholder variable
step3_output = ""

# Helper to escape curly braces inside f-strings so that the final output keeps double braces

def _esc_dbl(text: str) -> str:
    """Return *text* with every '{' -> '{{' and '}' -> '}}'.

    This lets us embed placeholder tokens like {{Title}} inside an f-string
    and still have them appear with double braces in the final string.
    """
    return text.replace('{', '{{').replace('}', '}}')

# ---------------------------------------------------------------------------
# After STEP 3 content collection, build Step 4 prompt ----------------------
# ---------------------------------------------------------------------------

# -- Build the template/examples section and output example -----------------
_template_examples_raw = """Templates and Examples
Title Slide
{{Title}}
Max 30 Characters
Example: Knowing Yourself

{{Subtitle}}
Max 75 Characters
Example: Why is self awareness important and how to do it?

Lesson 1: Segment Slide
{{Lesson 1 Title}} Max 30 Characters Example: What is PICS?
{{Lesson 1 Subtitle}} Max 450 Characters Example: PICS is a simple, powerful tool for self-reflection and building self-awareness. It helps you uncover what drives you (Passions), what excites your curiosity (Interests), what you care deeply about (Causes), and what you naturally do well (Strengths). It’s your personal compass for finding meaningful direction.

Lesson 1: Explanation Slide
{{Lesson 1 Explainer 1}} Max 240 characters Example: Instead of just reacting, you recognize “I’m thinking this” or “I’m feeling that,” and you can see how those inner states influence what you say and do. In short, it’s being conscious of yourself as an observer and actor in the moment.
{{Lesson 1 Explainer 2}} Max 180 characters Example: Self-awareness is a lifelong journey, and the “picture of you” in your mind becomes clearer and clearer as you collect more experiences and continue on your personal journey.

Lesson 1: List Slide
{{Lesson 1 List Title}} Max 30 Characters Example: Using PICS
{{Lesson 1 List Point 1}} Max 150 characters Example: Repeat this process at least once every month to track your personal growth.
{{Lesson 1 List Point 2}} Max 150 characters Example: It’s fine if your answers change over time as you continue to learn about yourself.
{{Lesson 1 List Point 3}} Max 150 characters Example: Be honest with yourself, as genuine self-reflection is the key to progress.
{{Lesson 1 List Point 4}} Max 150 characters 
{{Lesson 1 List Point 5}} Max 150 characters 
{{Lesson 1 Case Title}} Max 30 Characters Example: Using PICS
{{Lesson 1 Case Description}} Max 640 Characters Example: Maria felt adrift in her job. Using the PICS self-reflection tool, she journaled to build self-awareness. Passion: She realized she loses track of time when mentoring junior colleagues. Interest: She loves reading about sustainable farming in her free time. Cause: The lack of green spaces in her city frustrates her. Strength: Friends always ask for her help to organize trips, a natural skill for her. This exercise gave her a clearer picture of what truly drives her.

Lesson 2: Segment Slide
{{Lesson 2 Title}} Max 30 Characters Example: Aligning Actions
{{Lesson 2 Subtitle}} Max 450 Characters Example: Now that you have your PICS, the next step is to see how your daily life matches up. This lesson is about auditing your time and commitments to ensure you're living in alignment with what truly matters to you. It's about bridging the gap between who you are and what you do.

Lesson 2: Explanation Slide
{{Lesson 2 Explainer 1}} Max 240 characters Example: Think of your values (from PICS) as a destination and your daily actions as the path. If your actions don't point toward your destination, you'll feel lost. Alignment brings a sense of purpose and reduces inner conflict.
{{Lesson 2 Explainer 2}} Max 180 characters Example: Alignment isn't about a massive, overnight change. It starts with small shifts: choosing a hobby that matches an Interest, or dedicating one hour a week to a Cause you care about. These small steps build momentum.

Lesson 2: List Slide
{{Lesson 2 List Title}} Max 30 Characters Example: Weekly Alignment Check
{{Lesson 2 List Point 1}} Max 150 characters Example: At the end of the week, review your calendar to see how much time was dedicated to your PICS.
{{Lesson 2 List Point 2}} Max 150 characters Example: Identify one activity that drained you and did not align with your values.
{{Lesson 2 List Point 3}} Max 150 characters Example: Schedule one activity in the coming week that directly fuels a Passion, Interest, or Cause.
{{Lesson 2 List Point 4}} Max 150 characters 
{{Lesson 2 List Point 5}} Max 150 characters 
{{Lesson 2 Case Title}} Max 30 Characters Example: Jamal's Realignment
{{Lesson 2 Case Description}} Max 640 Characters Example: Jamal identified 'Creative Writing' as a Passion but realized he spent all his evenings watching TV shows he didn't even like. He felt misaligned and unfulfilled. Audit: He saw 10+ hours of TV and 0 hours of writing in his week. Small Shift: He decided to replace the first 30 minutes of TV time with journaling and story-writing. Result: After a month, he had a new routine, felt more energized, and had the first chapter of a story written. This small alignment had a huge impact on his well-being.

Lesson 3: Segment Slide
{{Lesson 3 Title}} Max 30 Characters Example: Limiting Beliefs
{{Lesson 3 Subtitle}} Max 450 Characters Example: Sometimes, the biggest obstacle to living our PICS is our own mindset. Limiting beliefs are the stories we tell ourselves about why we can't do something (e.g., "I'm not creative," or "It's too late to change"). This lesson helps you identify these internal barriers and reframe them into empowering ones.

Lesson 3: Explanation Slide
{{Lesson 3 Explainer 1}} Max 240 characters Example: A limiting belief often sounds like a fact. For example, "I'm just not good with numbers." Recognizing it as a belief—a thought you can question and change—is the first step to dismantling its power over you.
{{Lesson 3 Explainer 2}} Max 180 characters Example: The goal isn't to never have negative thoughts. It's to build a stronger, more empowering inner voice that can challenge them. Think of it as training a mental muscle to focus on possibilities, not just obstacles.

Lesson 3: List Slide
{{Lesson 3 List Title}} Max 30 Characters Example: The 3 R's of Reframing
{{Lesson 3 List Point 1}} Max 150 characters Example: Recognize and write down a limiting thought that holds you back.
{{Lesson 3 List Point 2}} Max 150 characters Example: Re-examine the thought by questioning if it is 100% true and finding counter-evidence.
{{Lesson 3 List Point 3}} Max 150 characters Example: Reframe the statement into an empowering one that focuses on your strengths.
{{Lesson 3 List Point 4}} Max 150 characters 
{{Lesson 3 List Point 5}} Max 150 characters 
{{Lesson 3 Case Title}} Max 30 Characters Example: Priya's Breakthrough
{{Lesson 3 Case Description}} Max 640 Characters Example: Priya's Cause was environmental protection, but she believed, "I'm just one person, I can't make a difference." This thought stopped her from taking any action. Identification: She recognized this thought made her feel helpless and prevented her from volunteering. Reframe: She challenged it by researching local activists and changed her belief to, "My actions can inspire others and contribute to a larger movement." Action: This new belief empowered her to join a local community garden project, where she found her contributions were valued and impactful.

Lesson 4: Segment Slide
{{Lesson 4 Title}} Max 30 Characters Example: Growth Through Feedback
{{Lesson 4 Subtitle}} Max 450 Characters Example: Self-awareness isn't built in a vacuum. To truly understand our Strengths and blind spots, we must be open to how others see us. This lesson is about cultivating a growth mindset and learning how to seek and use constructive feedback to accelerate your personal development.

Lesson 4: Explanation Slide
{{Lesson 4 Explainer 1}} Max 240 characters Example: Think of feedback not as criticism, but as data. It's valuable information that can help you adjust your course and grow more effectively. The key is to separate the feedback from your sense of self-worth.
{{Lesson 4 Explainer 2}} Max 180 characters Example: A growth mindset means believing your abilities can be developed through dedication and hard work. When you see challenges and feedback as opportunities to learn, you unlock your potential for continuous improvement.

Lesson 4: List Slide
{{Lesson 4 List Title}} Max 30 Characters Example: Seeking Great Feedback
{{Lesson 4 List Point 1}} Max 150 characters Example: Be specific with your questions when asking for feedback to get actionable advice.
{{Lesson 4 List Point 2}} Max 150 characters Example: Choose your sources carefully, asking people you trust and who have a relevant perspective.
{{Lesson 4 List Point 3}} Max 150 characters Example: Listen to understand, not to defend, and thank the person for their input.
{{Lesson 4 List Point 4}} Max 150 characters 
{{Lesson 4 List Point 5}} Max 150 characters 
{{Lesson 4 Case Title}} Max 30 Characters Example: David's Development
{{Lesson 4 Case Description}} Max 640 Characters Example: David knew 'leadership' was one of his Strengths, but he felt he had stopped improving. He decided to actively seek feedback on it. Specific Question: He asked a trusted colleague, "What's one thing I could start or stop doing to make our project check-ins more productive for the team?" The Feedback: His colleague shared that sometimes he gets so excited he jumps in with solutions before everyone has had a chance to speak. Application: David made a conscious effort to listen first in the next meeting. Not only did the team come up with better ideas, but they also told him it was one of the most collaborative sessions they'd had.

Activity Slide
{{Activity Title}}
Max 30 Characters
Example: Your Challenge

{{Activity Instructions}}
Max 640 Characters
Example: In the chat, share at least one thing that you’re really passionate about, one thing that piques your interest, one cause that you’re willing to take action on, and one strength that you’re proud of yourself for. Look at what others are sharing to get inspired!
"""

_output_example_raw = """{{Title}} Knowing Yourself
{{Subtitle}} Why is self awareness important and how to do it?

{{Lesson 1 Title}} What is PICS?
{{Lesson 1 Subtitle}} PICS is a simple, powerful tool for self-reflection and building self-awareness. It helps you uncover what drives you (Passions), what excites your curiosity (Interests), what you care deeply about (Causes), and what you naturally do well (Strengths). It’s your personal compass for finding meaningful direction.
{{Lesson 1 Explainer 1}} Instead of just reacting, you recognize “I’m thinking this” or “I’m feeling that,” and you can see how those inner states influence what you say and do. In short, it’s being conscious of yourself as an observer and actor in the moment.
{{Lesson 1 Explainer 2}} Self-awareness is a lifelong journey, and the “picture of you” in your mind becomes clearer and clearer as you collect more experiences and continue on your personal journey.
{{Lesson 1 List Title}} Using PICS
{{Lesson 1 List Point 1}} Repeat this process at least once every month to track your personal growth.
{{Lesson 1 List Point 2}} It’s fine if your answers change over time as you continue to learn about yourself.
{{Lesson 1 List Point 3}} Be honest with yourself, as genuine self-reflection is the key to progress.
{{Lesson 1 List Point 4}} 
{{Lesson 1 List Point 5}} 
{{Lesson 1 Case Title}} Using PICS
{{Lesson 1 Case Description}} Maria felt adrift in her job. Using the PICS self-reflection tool, she journaled to build self-awareness. Passion: She realized she loses track of time when mentoring junior colleagues. Interest: She loves reading about sustainable farming in her free time. Cause: The lack of green spaces in her city frustrates her. Strength: Friends always ask for her help to organize trips, a natural skill for her. This exercise gave her a clearer picture of what truly drives her.

{{Lesson 2 Title}} Aligning Actions
{{Lesson 2 Subtitle}} Now that you have your PICS, the next step is to see how your daily life matches up. This lesson is about auditing your time and commitments to ensure you're living in alignment with what truly matters to you. It's about bridging the gap between who you are and what you do.
{{Lesson 2 Explainer 1}} Think of your values (from PICS) as a destination and your daily actions as the path. If your actions don't point toward your destination, you'll feel lost. Alignment brings a sense of purpose and reduces inner conflict.
{{Lesson 2 Explainer 2}} Alignment isn't about a massive, overnight change. It starts with small shifts: choosing a hobby that matches an Interest, or dedicating one hour a week to a Cause you care about. These small steps build momentum.
{{Lesson 2 List Title}} Weekly Alignment Check
{{Lesson 2 List Point 1}} At the end of the week, review your calendar to see how much time was dedicated to your PICS.
{{Lesson 2 List Point 2}} Identify one activity that drained you and did not align with your values.
{{Lesson 2 List Point 3}} Schedule one activity in the coming week that directly fuels a Passion, Interest, or Cause.
{{Lesson 2 List Point 4}} Reflect on previous similar activities to inform your starting points for these activities.
{{Lesson 2 List Point 5}} 
{{Lesson 2 Case Title}} Jamal's Realignment
{{Lesson 2 Case Description}} Jamal identified 'Creative Writing' as a Passion but realized he spent all his evenings watching TV shows he didn't even like. He felt misaligned and unfulfilled. Audit: He saw 10+ hours of TV and 0 hours of writing in his week. Small Shift: He decided to replace the first 30 minutes of TV time with journaling and story-writing. Result: After a month, he had a new routine, felt more energized, and had the first chapter of a story written. This small alignment had a huge impact on his well-being.

{{Lesson 3 Title}} Limiting Beliefs
{{Lesson 3 Subtitle}} Sometimes, the biggest obstacle to living our PICS is our own mindset. Limiting beliefs are the stories we tell ourselves about why we can't do something (e.g., "I'm not creative," or "It's too late to change"). This lesson helps you identify these internal barriers and reframe them into empowering ones.
{{Lesson 3 Explainer 1}} A limiting belief often sounds like a fact. For example, "I'm just not good with numbers." Recognizing it as a belief—a thought you can question and change—is the first step to dismantling its power over you.
{{Lesson 3 Explainer 2}} The goal isn't to never have negative thoughts. It's to build a stronger, more empowering inner voice that can challenge them. Think of it as training a mental muscle to focus on possibilities, not just obstacles.
{{Lesson 3 List Title}} The 3 R's of Reframing
{{Lesson 3 List Point 1}} Recognize and write down a limiting thought that holds you back.
{{Lesson 3 List Point 2}} Re-examine the thought by questioning if it is 100% true and finding counter-evidence.
{{Lesson 3 List Point 3}} Reframe the statement into an empowering one that focuses on your strengths.
{{Lesson 3 List Point 4}} 
{{Lesson 3 List Point 5}} 
{{Lesson 3 Case Title}} Priya's Breakthrough
{{Lesson 3 Case Description}} Priya's Cause was environmental protection, but she believed, "I'm just one person, I can't make a difference." This thought stopped her from taking any action. Identification: She recognized this thought made her feel helpless and prevented her from volunteering. Reframe: She challenged it by researching local activists and changed her belief to, "My actions can inspire others and contribute to a larger movement." Action: This new belief empowered her to join a local community garden project, where she found her contributions were valued and impactful.

{{Lesson 4 Title}} Growth Through Feedback
{{Lesson 4 Subtitle}} Self-awareness isn't built in a vacuum. To truly understand our Strengths and blind spots, we must be open to how others see us. This lesson is about cultivating a growth mindset and learning how to seek and use constructive feedback to accelerate your personal development.
{{Lesson 4 Explainer 1}} Think of feedback not as criticism, but as data. It's valuable information that can help you adjust your course and grow more effectively. The key is to separate the feedback from your sense of self-worth.
{{Lesson 4 Explainer 2}} A growth mindset means believing your abilities can be developed through dedication and hard work. When you see challenges and feedback as opportunities to learn, you unlock your potential for continuous improvement.
{{Lesson 4 List Title}} Seeking Great Feedback
{{Lesson 4 List Point 1}} Be specific with your questions when asking for feedback to get actionable advice.
{{Lesson 4 List Point 2}} Choose your sources carefully, asking people you trust and who have a relevant perspective.
{{Lesson 4 List Point 3}} Listen to understand, not to defend, and thank the person for their input.
{{Lesson 4 List Point 4}} Pay attention to what they’re saying and make them feel comfortable.
{{Lesson 4 List Point 5}} Don’t interrupt as they speak.
{{Lesson 4 Case Title}} David's Development
{{Lesson 4 Case Description}} David knew 'leadership' was one of his Strengths, but he felt he had stopped improving. He decided to actively seek feedback on it. Specific Question: He asked a trusted colleague, "What's one thing I could start or stop doing to make our project check-ins more productive for the team?" The Feedback: His colleague shared that sometimes he gets so excited he jumps in with solutions before everyone has had a chance to speak. Application: David made a conscious effort to listen first in the next meeting. Not only did the team come up with better ideas, but they also told him it was one of the most collaborative sessions they'd had.

{{Activity Title}} Your Challenge
{{Activity Instructions}} In the chat, share at least one thing that you’re really passionate about, one thing that piques your interest, one cause that you’re willing to take action on, and one strength that you’re proud of yourself for. Look at what others are sharing to get inspired!
"""

_template_examples = _template_examples_raw  # maintain double braces
_output_example = _output_example_raw

prompt4 = (
    "You’re an instructional designer with experience in creating learning content for online courses designed for young adults. "
    "The following is course content related to the topic: {{Topic}}, which is divided into 4 lessons. "
    "Use this content to create a set of slide content that will help learners review everything from the content. "
    "Follow these rules when creating this slide deck content, and format the output in line with the relevant slide type from the Templates and Examples Section:\n\n"
    "Start with a “Title Slide”. This should share the topic and a quick explainer of the idea / framework / tool that will be shared.\n\n"
    "Structure the slides in a logical manner.\n\n"
    "You MUST strictly follow all character count limits provided in the templates (e.g., Max 240 characters). This is not a suggestion but a mandatory rule for the output. Write very concisely to ensure your responses fit within these limits. Any output that exceeds the specified character count for a field is considered incorrect.\n\n"
    "For each lesson, start with a “Segment Slide”. This should include a question that peaks interest in the topic or poses the topic as a relatable question. This should follow a very brief description to help give context to the question, or create interest in what follows.\n\n"
    "For each lesson, create slide content in the “Explanation Slide” format. This is where you provide a more detailed explanation of the concept, in 2 paragraphs.\n\n"
    "For each lesson, create slide content in the “List Slide” format. This can contain further details about the lesson concept, tips, facts, or examples. For this slide, generate between 2 and 5 distinct points, with each point being a complete sentence.\n\n"
    "For each lesson, create slide content in the “Case or Example Slide” format. This is where you can provide details of an example of case study that further explains the concepts.\n\n"
    "At the end of the deck, add a challenge or activity that learners can use to apply, practice or reflect on their learning from the content. This needs to be a set of instructions on how to conduct the activity in the “Activity Slide” format.\n\n"
    
    f"{_template_examples}\n\n"
    "Before providing the final output, perform a final check to ensure every single field's content is under its specified character limit.\n\n"
    "Output requirements:\n"
    "For your output, you will ONLY share each of the required {{content}} sections followed by the exact content. Use double curly braces for all placeholders, like {{Title}}:\n\n"
    "Output Example:\n\n"
    f"{_output_example}\n"
)

# Step 4
st.header("Step 4: Generating Slide Content")

st.markdown("4️⃣ This prompt will be used to generate the slide content for the infographic.")
st.markdown(
    "<div style='display: flex; justify-content: flex-end; margin-bottom: -10px; margin-top: 4px;'>",
    unsafe_allow_html=True,
)
clipboard_button(prompt4, label="Copy Step 4 Prompt", key="p4")
st.markdown("</div>", unsafe_allow_html=True)

with st.expander("View Step 4 Prompt", expanded=False):
    st.code(prompt4, language="text")

# Step 5 – Paste AI output for slides
with st.expander("5️⃣ Paste the filled-in content", expanded=True):
    user_input = st.text_area(
        "Paste the LLM's answer here (placeholders + your new content)",
        height=300,
        placeholder="e.g.\n{{Title}} Knowing Yourself\n{{Subtitle}} Why is self awareness important and how to do it?\n…",
    )

# Step 6 – Generate the slide deck
if st.button("Generate Slide Deck", disabled=not user_input.strip()):
    with st.spinner("Parsing content…"):
        placeholder_map, missing = parse_user_content(user_input)

    if missing:
        st.error(
            "The following placeholders were not found in your text: "
            + ", ".join(missing)
        )
        st.stop()

    try:
        with st.spinner("Authorizing with Google…"):
            creds = get_credentials()
            drive_svc = build("drive", "v3", credentials=creds)
            slides_svc = build("slides", "v1", credentials=creds)

        with st.spinner("Copying template deck…"):
            # Use the topic as the slide deck title; if blank, fall back to a timestamped title
            title_placeholder = placeholder_map.get("{{Title}}", "").strip()
            if title_placeholder:
                deck_title = f"{title_placeholder} | {datetime.datetime.now(datetime.UTC):%Y-%m-%d}"
            elif topic.strip():
                deck_title = f"{topic.strip()} | {datetime.datetime.now(datetime.UTC):%Y-%m-%d}"
            else:
                deck_title = f"Tuesday Tips – {datetime.datetime.now(datetime.UTC):%Y-%m-%d %H:%M:%S}"
            
            # Get selected template from session state
            selected_template_key = st.session_state.get("selected_template", "Template Version 1")
            selected_template_id = TEMPLATE_CONFIGS[selected_template_key]["id"]
            
            new_id = copy_template_presentation(drive_svc, deck_title, DESTINATION_FOLDER_ID, selected_template_id)

        with st.spinner("Replacing placeholders…"):
            replace_placeholders(slides_svc, new_id, placeholder_map)

        with st.spinner("Publishing deck…"):
            share_link = make_deck_public(drive_svc, new_id)

    except Exception as exc:
        st.error(f"⚠️ Something went wrong: {exc}")
        st.stop()

    # Success! ---------------------------------------------------------------
    st.success("Your slide deck is ready! 🎉")

    # Persist info in session_state for later actions
    st.session_state["deck_id"] = new_id
    st.session_state["share_link"] = share_link
    st.session_state["deck_title"] = deck_title
    st.session_state["title_placeholder"] = title_placeholder

    # Inform user to use buttons below
    st.info("Use the buttons below to open the slides, open the folder, or download images.")

    _rerun() 

# ---------------------------------------------------------------------------
# Post-generation actions (if a deck exists) ---------------------------------
# ---------------------------------------------------------------------------

if "deck_id" in st.session_state:
    deck_id: str = st.session_state["deck_id"]
    share_link: str = st.session_state["share_link"]
    deck_title: str = st.session_state["deck_title"]
    title_placeholder: str = st.session_state.get("title_placeholder", "")

    st.markdown("### Your Slide Deck")

    # Embed the deck
    st.components.v1.html(
        f"<iframe src='{share_link}' width='100%' height='600' allowfullscreen frameborder='0'></iframe>",
        height=600,
    )

    folder_url = f"https://drive.google.com/drive/folders/{DESTINATION_FOLDER_ID}"

    # Button row
    col1, col2, col3 = st.columns(3)

    with col1:
        try:
            st.link_button("Open Slides", share_link)
        except AttributeError:
            st.markdown(
                f'<a href="{share_link}" target="_blank" style="text-decoration:none;"><button>Open Slides</button></a>',
                unsafe_allow_html=True,
            )

    with col2:
        try:
            st.link_button("Open Folder", folder_url)
        except AttributeError:
            st.markdown(
                f'<a href="{folder_url}" target="_blank" style="text-decoration:none;"><button>Open Folder</button></a>',
                unsafe_allow_html=True,
            )

    with col3:
        if "zip_ready" not in st.session_state:
            if st.button("Download Images"):
                with st.spinner("Generating images…"):
                    try:
                        creds = get_credentials()
                        slides_svc = build("slides", "v1", credentials=creds)
                        zip_buf = build_slide_images_zip(creds, slides_svc, deck_id)
                        st.session_state["zip_data"] = zip_buf.getvalue()
                        st.session_state["zip_ready"] = True
                        _rerun()
                    except Exception as img_exc:
                        st.error(f"Could not generate slide images: {img_exc}")
        else:
            st.download_button(
                label="Click to download ZIP",
                data=st.session_state["zip_data"],
                file_name=f"{title_placeholder or deck_title.split('|')[0].strip()} | Tuesday Tips Images.zip",
                mime="application/zip",
                key="download_zip_btn2",
            ) 