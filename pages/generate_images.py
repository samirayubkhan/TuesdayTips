import re
import streamlit as st
from googleapiclient.discovery import build

# Import utilities from the main app
from app import build_slide_images_zip, get_credentials

st.set_page_config(page_title="Generate Images from Google Slide", layout="centered")

st.markdown(
    """
    Paste a Google Slides **share link** (or just the presentation ID) below, then click
    **Download Images** to get a ZIP file containing PNG thumbnails of every slide.
    """
)


def _extract_presentation_id(url_or_id: str) -> str:
    """Return the presentation ID from a full Slides URL or raw ID string."""
    url_or_id = url_or_id.strip()
    if not url_or_id:
        raise ValueError("The input is empty.")

    # If the user already provided a 44-character ID (common length), accept as-is.
    if "/" not in url_or_id and len(url_or_id) >= 25:
        return url_or_id

    # Try to pull the ID from a typical URL pattern …/d/{presentationId}/…
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url_or_id)
    if match:
        return match.group(1)

    raise ValueError("Could not find a presentation ID in the provided link.")


# -- UI ---------------------------------------------------------------------

slide_link = st.text_input("Google Slides link or ID:")

# Initialize session state for the generated ZIP bytes
if "img_zip" not in st.session_state:
    st.session_state["img_zip"] = None

if st.button("Download Images", disabled=not slide_link.strip()):
    try:
        pres_id = _extract_presentation_id(slide_link)
        with st.spinner("Generating slide thumbnails…"):
            creds = get_credentials()
            slides_svc = build("slides", "v1", credentials=creds)
            zip_buf = build_slide_images_zip(creds, slides_svc, pres_id)
            st.session_state["img_zip"] = zip_buf.getvalue()
    except Exception as exc:
        st.error(f"⚠️ Could not generate images: {exc}")

# Offer the download button if we have data ready
if st.session_state.get("img_zip"):
    st.download_button(
        label="Click to download ZIP",
        data=st.session_state["img_zip"],
        file_name="Google Slides Images.zip",
        mime="application/zip",
        key="download_zip_btn_generate_images_page",
    ) 