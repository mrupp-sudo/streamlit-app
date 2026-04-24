from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs, urlparse

import streamlit as st
import requests

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)


# =========================
# GLOBAL SESSION (reused)
# =========================
SESSION = requests.Session()

# lighter + compressed requests
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Accept-Encoding": "gzip, deflate",
})


def configure_proxy_once():
    """
    Configure proxy once per app run (reuses TCP + TLS connection)
    """
    if "proxy_configured" in st.session_state:
        return

    proxy_user = st.secrets["WEBshare_username"]
    proxy_pass = st.secrets["WEBshare_password"]
    proxy_host = st.secrets["WEBshare_host"]
    proxy_port = st.secrets["WEBshare_port"]

    proxy = f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}"

    SESSION.proxies.update({
        "http": proxy,
        "https": proxy,
    })

    st.session_state["proxy_configured"] = True


def build_api():
    configure_proxy_once()
    return YouTubeTranscriptApi(http_client=SESSION)


# =========================
# DATA STRUCTURES
# =========================
@dataclass(frozen=True)
class TranscriptResult:
    video_id: str
    text: str


_YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


# =========================
# HELPERS
# =========================
def extract_video_id(raw_url: str) -> Optional[str]:
    raw_url = (raw_url or "").strip()
    if not raw_url:
        return None

    if _YT_ID_RE.match(raw_url):
        return raw_url

    try:
        parsed = urlparse(raw_url)
    except Exception:
        return None

    host = (parsed.hostname or "").lower()

    if host in {"youtu.be"}:
        candidate = (parsed.path or "").lstrip("/").split("/")[0]
        return candidate if _YT_ID_RE.match(candidate) else None

    if host.endswith("youtube.com"):
        if parsed.path == "/watch":
            vid = parse_qs(parsed.query).get("v", [None])[0]
            return vid if vid and _YT_ID_RE.match(vid) else None

        for prefix in ("/shorts/", "/embed/", "/v/"):
            if parsed.path.startswith(prefix):
                candidate = parsed.path[len(prefix):].split("/")[0]
                return candidate if _YT_ID_RE.match(candidate) else None

    return None


# =========================
# CORE LOGIC
# =========================
@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)  # 24h cache
def fetch_transcript_text(video_id: str) -> TranscriptResult:
    languages = [
        "en", "en-US", "en-GB",
        "de", "de-DE", "de-AT", "de-CH",
    ]

    api = build_api()

    # 🔁 smarter retry (only 2 attempts)
    for attempt in range(2):
        try:
            transcript_items = api.fetch(
                video_id,
                languages=languages,
                preserve_formatting=False,
            ).to_raw_data()
            break

        except NoTranscriptFound:
            transcript_list = api.list(video_id)
            first_transcript = next(iter(transcript_list), None)
            if first_transcript is None:
                raise

            transcript_items = first_transcript.fetch(
                preserve_formatting=False
            ).to_raw_data()
            break

        except (requests.exceptions.ProxyError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout):
            # retry only on network issues
            if attempt == 1:
                raise

        except Exception:
            # don't retry unknown logic errors
            raise

    text = "\n".join(
        item.get("text", "").strip()
        for item in transcript_items
        if item.get("text")
    )

    return TranscriptResult(video_id=video_id, text=text.strip())


# =========================
# UI
# =========================
def main() -> None:
    st.set_page_config(page_title="YouTube Transcript", page_icon="📝", layout="centered")

    st.title("YouTube transcript")
    st.caption("Paste a YouTube link (or video id), then click **Get transcript**.")

    url = st.text_input(
        "YouTube URL or video id",
        placeholder="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )

    col1, col2 = st.columns([1, 2])
    with col1:
        get_clicked = st.button("Get transcript", type="primary")

    if not get_clicked:
        st.info("Waiting for input.")
        return

    video_id = extract_video_id(url)
    if not video_id:
        st.error("Could not parse a valid YouTube video id.")
        return

    try:
        with st.spinner("Fetching transcript…"):
            result = fetch_transcript_text(video_id)

        if not result.text:
            st.warning("Transcript was retrieved but empty.")
            return

        st.success(f"Transcript fetched for video id: {result.video_id}")
        st.text_area("Transcript", value=result.text, height=360)

    except TranscriptsDisabled:
        st.error("Transcripts are disabled for this video.")
    except NoTranscriptFound:
        st.error("No transcript found for this video.")
    except VideoUnavailable:
        st.error("Video unavailable (private/removed/region blocked).")
    except Exception as exc:
        st.exception(exc)


if __name__ == "__main__":
    main()
