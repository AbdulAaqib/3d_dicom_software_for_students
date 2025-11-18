"""MCP tooling surface."""

from __future__ import annotations

import streamlit as st

from backend.mcp_registry import list_registered_tools


def render_mcp_tools_page() -> None:
    """Render the MCP tools catalog."""

    st.title("MCP Tools & Automations")
    st.write(
        "These tools are available to the GPT assistant via OpenAI function calling. "
        "They expose STL metadata, conversion summaries, and saved snapshots."
    )

    tools = list_registered_tools()
    if not tools:
        st.info("No tools registered yet.")
        return

    for tool in tools:
        with st.expander(f"{tool.name}", expanded=True):
            st.write(tool.description)
            st.json(tool.parameters, expanded=False)

