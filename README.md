# Tuesday Tips Slide Generator

A Streamlit app to generate Google Slides decks for instructional content, designed for online courses for young adults. The app helps you turn AI-generated content into a polished Google Slides deck in just a few steps.

## Features
- Generates instructional design prompts for topic breakdown, lesson planning, and slide content
- Integrates with Google Slides and Google Drive APIs
- Automatically creates and publishes a new slide deck from your content
- Exports slide images as a ZIP file

## Setup

1. **Clone the repository:**
   ```sh
   git clone https://github.com/<your-username>/<repo-name>.git
   cd <repo-name>
   ```

2. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```

3. **Google API Credentials:**
   - Download your `credentials.json` from Google Cloud Console (OAuth 2.0 Client ID for Desktop app)
   - Place `credentials.json` in the project root (it will generate `token.json` on first run)

4. **Run the app:**
   ```sh
   streamlit run app.py
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