# Tuesday Tips Slide Generator

A Streamlit app to generate Google Slides decks for instructional content, designed for online courses for young adults. The app helps you turn AI-generated content into a polished Google Slides deck in just a few steps.

## Features
- Generates instructional design prompts for topic breakdown, lesson planning, and slide content
- Integrates with Google Slides and Google Drive APIs
- Automatically creates and publishes a new slide deck from your content
- Exports slide images as a ZIP file

## Authentication modes

The app supports **two** authentication modes for Google APIs:

1. **User OAuth (default)** – Each user authenticates with their own Google account.  Files are created in the user’s Google Drive and their personal quota applies.
2. **Service Account** – A robot account owns the files.  Enable by setting the `USE_SERVICE_ACCOUNT=1` environment variable (and providing credentials).

If you do **not** set `USE_SERVICE_ACCOUNT`, the app automatically starts the OAuth flow the first time it needs Drive/Slides access and stores `token.json`.  This is the simplest setup for internal users.

### Switching back to user OAuth from a service account

1. **Unset** the `USE_SERVICE_ACCOUNT` environment variable in your environment or hosting platform.
2. **Remove** `SERVICE_ACCOUNT_JSON` or any `service_account.json` file if present (optional).
3. Make sure `credentials.json` (OAuth client ID for *Desktop App*) is in the project root.
4. On first run, users will be prompted to log in with their Google account and grant permissions. The app caches the token in `token.json`.

```sh
# Example (local)
# Ensure no service-account env vars are set
unset USE_SERVICE_ACCOUNT
unset SERVICE_ACCOUNT_JSON

# Run the app
streamlit run generate_infographic.py
```

## Usage
1. Enter your topic and follow the step-by-step prompts to generate instructional content.
2. Paste the AI-generated content into the app.
3. Click "Generate Slide Deck" to create and publish your Google Slides deck.
4. Use the provided links to view, share, or download slide images.

## Notes
- Your Google account must have access to Google Slides and Drive APIs.
- Do **not** commit your `credentials.json` or `token.json` to version control.

## License
MIT 