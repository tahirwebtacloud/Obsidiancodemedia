import requests

payload = {
    "full_caption": "Google Stitch killed the blank canvas.\n\nThe infinite canvas runs on Gemini 2.5 Pro.\nYou feed it text or images.",
    "selected_text": "The infinite canvas runs on Gemini 2.5 Pro.\nYou feed it text or images.",
    "comment": "Latest model is 3.1 pro. Never liked the vocabularies either",
    "topic": "Test",
    "purpose": "Test"
}

# we can't test against the running server easily if it requires auth, but wait, auth is local?
