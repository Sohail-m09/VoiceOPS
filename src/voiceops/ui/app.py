
import requests
import streamlit as st

DEFAULT_API_URL = "http://localhost:8000/api/v1"


def initialize_session_state() -> None:
    """Initialize chat and authentication state."""

    defaults = {
        "messages": [
            {
                "role": "assistant",
                "content": (
                    "Hello! Welcome to VoiceOps.\n\n"
                    "I'm your warehouse operations assistant. "
                    "You can ask me about inventory, orders, shipments, "
                    "and warehouse SOPs."
                ),
            }
        ],
        "access_token": None,
        "user": None,
        "conversation_id": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_api_url() -> str:
    """Read the FastAPI base URL from the sidebar."""

    return st.sidebar.text_input(
        "FastAPI URL",
        value=DEFAULT_API_URL,
    ).strip().rstrip("/")


def render_login(api_url: str) -> None:
    """Display login and logout controls."""

    st.sidebar.subheader("Account")

    if st.session_state.access_token:
        user = st.session_state.user or {}

        st.sidebar.success(
            f"Logged in as {user.get('full_name', 'User')}"
        )
        st.sidebar.caption(f"Role: {user.get('role', 'unknown')}")

        if st.sidebar.button("Logout", use_container_width=True):
            st.session_state.access_token = None
            st.session_state.user = None
            st.session_state.messages = []
            st.session_state.conversation_id = None
            st.rerun()

        return

    with st.sidebar.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        submitted = st.form_submit_button(
            "Login",
            use_container_width=True,
        )

    if submitted:
        if not email.strip() or not password:
            st.sidebar.warning("Enter your email and password.")
            return

        try:
            response = requests.post(
                f"{api_url}/auth/login",
                json={
                    "email": email.strip(),
                    "password": password,
                },
                timeout=15,
            )
            response.raise_for_status()

            data = response.json()

            st.session_state.access_token = data["access_token"]
            st.session_state.user = data["user"]

            st.rerun()

        except requests.RequestException:
            st.sidebar.error(
                "Login failed. Check your credentials and API connection."
            )


def render_sidebar(api_url: str) -> None:
    """Display application information and authentication."""

    with st.sidebar:
        st.title("VoiceOps")
        st.caption("Warehouse & Supply Chain Assistant")
        st.divider()

    render_login(api_url)

    st.sidebar.divider()
    st.sidebar.caption("Text Chat: Available")
    st.sidebar.caption("Microphone Input: Available")
    st.sidebar.caption("Speech-to-Text: Available")
    st.sidebar.caption("VoiceOps Development Build")


def send_chat_message(api_url: str, message: str) -> dict:
    """Send an authenticated message within the current conversation."""

    response = requests.post(
        f"{api_url}/chat",
        json={
            "message": message,
            "conversation_id": st.session_state.conversation_id,
        },
        headers={
            "Authorization": f"Bearer {st.session_state.access_token}"
        },
        timeout=120,
    )

    response.raise_for_status()
    return response.json()


def request_audio_transcription(
    api_url: str,
    audio_bytes: bytes,
) -> str:
    """Upload a WAV recording and return its transcript."""

    response = requests.post(
        f"{api_url}/transcribe",
        files={
            "audio": (
                "recording.wav",
                audio_bytes,
                "audio/wav",
            )
        },
        headers={
            "Authorization": f"Bearer {st.session_state.access_token}"
        },
        timeout=(10, 300),
    )

    response.raise_for_status()

    data = response.json()
    transcript = data.get("transcript")

    if not isinstance(transcript, str) or not transcript.strip():
        raise ValueError("The backend returned an empty transcript.")

    return transcript.strip()



def render_audio_input(
    is_authenticated: bool,
    api_url: str,
) -> str | None:
    """Record audio, transcribe it, and let the user review the text."""

    st.subheader("Voice Input")

    recorded_audio = st.audio_input(
        "Record a voice message",
        sample_rate=16000,
        disabled=not is_authenticated,
        key="voice_recording",
    )

    if recorded_audio is not None:
        st.audio(recorded_audio, format="audio/wav")

        if st.button(
            "Transcribe recording",
            disabled=not is_authenticated,
            key="transcribe_recording_button",
        ):
            audio_bytes = recorded_audio.getvalue()

            with st.spinner("Converting speech to text..."):
                try:
                    transcript = request_audio_transcription(
                        api_url,
                        audio_bytes,
                    )

                    st.session_state.audio_transcript_editor = transcript
                    st.session_state.audio_transcript = transcript

                except requests.Timeout:
                    st.error(
                        "Transcription timed out. "
                        "The backend took too long to respond."
                    )

                except requests.ConnectionError as exc:
                    st.error(
                        f"Could not connect to FastAPI: {exc}"
                    )

                except requests.HTTPError as exc:
                    status_code = (
                        exc.response.status_code
                        if exc.response is not None
                        else "unknown"
                    )
                    st.error(
                        f"Transcription failed (HTTP {status_code})."
                    )

                except requests.RequestException as exc:
                    st.error(
                        f"Transcription request failed: {exc}"
                    )

                except (KeyError, ValueError):
                    st.error(
                        "The backend returned an invalid transcription."
                    )

    if "audio_transcript" not in st.session_state:
        return None

    st.subheader("Review Transcription")

    transcript = st.text_area(
        "You can correct the transcript before sending it:",
        key="audio_transcript_editor",
        height=120,
    )

    if st.button(
        "Send transcript",
        type="primary",
        key="send_audio_transcript_button",
    ):
        if not transcript.strip():
            st.warning("The transcript cannot be empty.")
            return None

        return transcript.strip()

    return None



def render_chat(api_url: str) -> None:
    """Display chat history and handle text and audio input."""

    st.title("VoiceOps Warehouse Assistant")
    st.caption(
        "Your AI-powered warehouse and supply chain operations assistant."
    )
    st.divider()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            if message.get("evidence"):
                with st.expander("Investigation evidence"):
                    st.json(message["evidence"])

    is_authenticated = bool(st.session_state.access_token)

    if not is_authenticated:
        st.info("Please log in from the sidebar to start chatting.")

    # Microphone recording and speech-to-text
    audio_prompt = render_audio_input(
        is_authenticated,
        api_url,
    )

    st.divider()

    # Text chat
    prompt = audio_prompt

    if prompt is None:
        prompt = st.chat_input(
            "Ask about inventory, orders, shipments, or SOPs...",
            disabled=not is_authenticated,
        )

    if audio_prompt is not None:
        st.session_state.pop("audio_transcript", None)

    if not prompt:
        return

    st.session_state.messages.append(
        {"role": "user", "content": prompt}
    )

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Investigating your request..."):
            try:
                result = send_chat_message(api_url, prompt)

                st.session_state.conversation_id = result["conversation_id"]

                answer = result["answer"]
                evidence = result.get("evidence", [])

                st.markdown(answer)

                if result.get("clarification_required"):
                    st.info(
                        "I need a little more information to continue."
                    )

                if evidence:
                    with st.expander("Investigation evidence"):
                        st.json(evidence)

                if result.get("status") in {"partial", "failed"}:
                    st.warning(
                        f"Investigation status: {result['status']}"
                    )

                assistant_message = {
                    "role": "assistant",
                    "content": answer,
                    "evidence": evidence,
                }

            except requests.HTTPError as exc:
                status_code = (
                    exc.response.status_code
                    if exc.response is not None
                    else "unknown"
                )

                answer = (
                    f"The backend returned an error "
                    f"(HTTP {status_code}). Please try again."
                )

                st.error(answer)

                assistant_message = {
                    "role": "assistant",
                    "content": answer,
                }

            except requests.RequestException:
                answer = (
                    "I couldn't connect to the VoiceOps backend. "
                    "Check that FastAPI is running and try again."
                )

                st.error(answer)

                assistant_message = {
                    "role": "assistant",
                    "content": answer,
                }

            except (KeyError, ValueError):
                answer = "The backend returned an unexpected response."
                st.error(answer)

                assistant_message = {
                    "role": "assistant",
                    "content": answer,
                }

    st.session_state.messages.append(assistant_message)



def main() -> None:
    """Run the VoiceOps Streamlit application."""

    st.set_page_config(
        page_title="VoiceOps",
        page_icon="📦",
        layout="wide",
    )

    initialize_session_state()

    api_url = get_api_url()

    render_sidebar(api_url)
    render_chat(api_url)


main()
