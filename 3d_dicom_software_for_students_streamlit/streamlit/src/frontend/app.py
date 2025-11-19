from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import streamlit as st

# Ensure sibling `backend/` modules are importable when Streamlit runs from frontend/
PROJECT_SRC = Path(__file__).resolve().parents[1]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from components import (
    render_chatbot_page,
    render_mcp_tools_page,
    render_navigation,
    render_workspace_page,
)

dotenv_spec = importlib.util.find_spec("dotenv")
if dotenv_spec is not None:  # pragma: no cover - runtime import
    from dotenv import load_dotenv  # type: ignore[import]
else:  # pragma: no cover - optional dependency
    load_dotenv = None  # type: ignore[assignment]

if load_dotenv:  # pragma: no cover - executed at runtime
    current_file = Path(__file__).resolve()
    candidate_envs = [
        current_file.parents[4] / ".env",  # repo root
        current_file.parents[3] / ".env",  # streamlit sub-project root
    ]
    for env_path in candidate_envs:
        if env_path.exists():
            load_dotenv(env_path)

st.set_page_config(
    page_title="3D DICOM Studio",
    page_icon="🧱",
    layout="wide",
    initial_sidebar_state="expanded",
)

pending_redirect = st.session_state.pop("pending_workspace_redirect", False)
active_page = render_navigation()
if pending_redirect and active_page != "Workspace":
    st.session_state["active_page"] = "Workspace"
    st.rerun()

if active_page == "Uploader":
    render_workspace_page()
elif active_page == "Workspace":
    render_chatbot_page()
else:
    render_mcp_tools_page()
