from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs, urlparse

import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)


@dataclass(frozen=True)
class TranscriptResult:
    video_id: str
    text: str


_YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_video_id(raw_url: str) -> Optional[str]:
    raw_url = (raw_url or "").strip()
    if not raw_url:
        return None

    # Allow pasting a bare video id.
    if _YT_ID_RE.match(raw_url):
        return raw_url

    try:
        parsed = urlparse(raw_url)
    except Exception:
        return None

    host = (parsed.hostname or "").lower()

    # youtu.be/<id>
    if host in {"youtu.be"}:
        candidate = (parsed.path or "").lstrip("/").split("/")[0]
        return candidate if _YT_ID_RE.match(candidate) else None

    # youtube.com/watch?v=<id>
    if host.endswith("youtube.com"):
        if parsed.path == "/watch":
            vid = parse_qs(parsed.query).get("v", [None])[0]
            return vid if vid and _YT_ID_RE.match(vid) else None

        # youtube.com/shorts/<id>, /embed/<id>
        for prefix in ("/shorts/", "/embed/", "/v/"):
            if parsed.path.startswith(prefix):
                candidate = parsed.path[len(prefix) :].split("/")[0]
                return candidate if _YT_ID_RE.match(candidate) else None

    return None


@st.cache_data(show_spinner=False, ttl=60 * 60)
def fetch_transcript_text(video_id: str) -> TranscriptResult:
    # Prefer English if present, but fall back to whatever is available.
    #
    # `youtube-transcript-api` v1+ switched from classmethods like
    # `YouTubeTranscriptApi.get_transcript(...)` to an instance API:
    # `YouTubeTranscriptApi().fetch(...).to_raw_data()`.
    languages = [
        "en",
        "en-US",
        "en-GB",
        "de",
        "de-DE",
        "de-AT",
        "de-CH",
    ]

    if hasattr(YouTubeTranscriptApi, "get_transcript"):
        # Older `youtube-transcript-api` versions
        transcript_items = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
    else:
        # `youtube-transcript-api` v1+ (instance API)
        api = YouTubeTranscriptApi()
        try:
            transcript_items = api.fetch(
                video_id,
                languages=languages,
                preserve_formatting=False,
            ).to_raw_data()
        except NoTranscriptFound:
            # If a transcript exists but not in our preferred languages, fall back
            # to the first available transcript language for this video.
            transcript_list = api.list(video_id)
            first_transcript = next(iter(transcript_list), None)
            if first_transcript is None:
                raise
            transcript_items = first_transcript.fetch(preserve_formatting=False).to_raw_data()

    text = "\n".join(item.get("text", "").strip() for item in transcript_items if item.get("text"))
    return TranscriptResult(video_id=video_id, text=text.strip())


def main() -> None:
    st.set_page_config(page_title="YouTube Transcript", page_icon="📝", layout="centered")

    st.title("YouTube transcript")
    st.caption("Paste a YouTube link (or video id), then click **Get transcript**.")

    url = st.text_input("YouTube URL or video id", placeholder="https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    col1, col2 = st.columns([1, 2])
    with col1:
        get_clicked = st.button("Get transcript", type="primary")
    with col2:
        st.write("")

    if not get_clicked:
        st.info("Waiting for input.")
        return

    video_id = extract_video_id(url)
    if not video_id:
        st.error("Could not parse a valid YouTube video id from that input.")
        return

    try:
        with st.spinner("Fetching transcript…"):
            result = fetch_transcript_text(video_id)

        if not result.text:
            st.warning("Transcript was retrieved but appears empty.")
            return

        st.success(f"Transcript fetched for video id: {result.video_id}")
        st.text_area("Transcript", value=result.text, height=360)

    except TranscriptsDisabled:
        st.error("Transcripts are disabled for this video.")
    except NoTranscriptFound:
        st.error("No transcript was found for this video (try another one).")
    except VideoUnavailable:
        st.error("This video is unavailable (private/removed/region blocked).")
    except Exception as exc:
        st.exception(exc)


if __name__ == "__main__":
    main()
