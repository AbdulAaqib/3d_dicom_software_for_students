"""Intro/hero section for the DICOM Streamlit workspace."""

from __future__ import annotations

import streamlit as st


def render_intro_page() -> None:
    """Render an overview hero section with usage instructions."""

    st.markdown(
        """
        ### Welcome to the 3D DICOM Studio

        1. Upload a DICOM study or point to one of the bundled samples.
        2. Convert the volume to an STL mesh with `dicom2stl`.
        3. Inspect the mesh, capture annotated snapshots, and share with ChatGPT.
        4. Use the MCP-powered assistant to re-run processing, compare views, and answer clinical or technical questions.
        """
    )


