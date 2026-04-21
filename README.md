# YouTube Transcript Streamlit Prototype

A minimal Streamlit app that accepts a YouTube URL and fetches the video's transcript.

## Setup (Windows / PowerShell)

```powershell
cd .\yt-transcript-streamlit

# Create venv
py -3 -m venv .venv

# Install dependencies (no activation required)
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Run
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Notes

- Works only if the video has transcripts available (manual or auto-generated) and they are not blocked/disabled.
- Some videos require cookies/authorization; this prototype does not handle that.
