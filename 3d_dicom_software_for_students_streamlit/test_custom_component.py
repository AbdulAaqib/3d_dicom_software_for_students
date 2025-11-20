#!/usr/bin/env python3
"""Quick test to verify the custom canvas component loads correctly."""

from __future__ import annotations

import base64
import sys
from io import BytesIO
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "streamlit" / "src"))

import streamlit as st
from PIL import Image, ImageDraw

# Import the custom component
from frontend.components.custom_canvas import render_snapshot_canvas, render_model_capture


def create_test_image(width: int = 400, height: int = 300) -> str:
    """Create a simple test image and return as base64."""
    img = Image.new("RGB", (width, height), color="#f0f0f0")
    draw = ImageDraw.Draw(img)
    
    # Draw a simple pattern
    draw.rectangle([50, 50, 150, 150], fill="#3498db", outline="#2980b9", width=3)
    draw.ellipse([200, 100, 300, 200], fill="#e74c3c", outline="#c0392b", width=3)
    draw.text((width // 2 - 40, height - 40), "Test Image", fill="#2c3e50")
    
    # Convert to base64
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    img_bytes = buffer.getvalue()
    return base64.b64encode(img_bytes).decode("ascii")


st.set_page_config(page_title="Custom Component Test", layout="wide")

st.title("🧪 Custom Component Test")
st.markdown("---")

st.header("Test 1: Snapshot Canvas (New PictogramLLM-inspired UI)")
st.markdown("""
This test verifies that the improved `render_snapshot_canvas` component loads correctly.

**✨ New Features You Should See:**
- 🎨 **Floating Toolbar** at the top center with backdrop blur
- **Color Palette** button with 9 preset colors (including white)
- **Brush Size Slider** with live preview (1-20px)
- **Undo/Redo** buttons for drawing history
- **Eraser Tool** toggle with visual feedback
- **Modern Action Buttons** with gradient backgrounds and smooth animations
- **Dark Theme** optimized for medical imaging

**Try these:**
1. Click the palette button to change colors
2. Adjust the brush size slider
3. Draw some annotations
4. Use undo/redo to navigate history
5. Toggle eraser mode
6. Save your annotations
""")

with st.expander("Test Annotator Component", expanded=True):
    test_image_b64 = create_test_image()
    
    result = render_snapshot_canvas(
        background_base64=test_image_b64,
        mime_type="image/png",
        initial_annotations={"objects": []},
        stroke_color="#FF4136",
        default_tool="marker",
        label_text="Test",
        width=400,
        height=300,
        show_toolbar=True,
        key="test-canvas-1",
    )
    
    if result:
        st.success("✅ Component returned data!")
        st.json({
            "reason": result.reason,
            "annotations_count": len(result.annotations.get("objects", [])),
            "has_image_data": result.image_data_url is not None,
        })
        
        if result.image_data_url:
            st.image(result.image_data_url, caption="Annotated Image", width=400)

st.markdown("---")

st.header("Test 2: Model Capture (Plotly Viewer)")
st.markdown("""
This test verifies that the `render_model_capture` component loads correctly.
You should see:
- A 3D Plotly visualization
- Notes input field
- Capture snapshot button
""")

with st.expander("Test Model Capture Component", expanded=True):
    # Create a simple test figure
    test_figure = {
        "data": [
            {
                "type": "scatter3d",
                "x": [0, 1, 2, 0],
                "y": [0, 1, 0, 0],
                "z": [0, 0, 1, 0],
                "mode": "lines+markers",
                "marker": {"size": 8, "color": "#3498db"},
                "line": {"color": "#2980b9", "width": 2},
            }
        ],
        "layout": {
            "scene": {
                "xaxis": {"title": "X"},
                "yaxis": {"title": "Y"},
                "zaxis": {"title": "Z"},
            },
            "height": 400,
            "margin": {"l": 0, "r": 0, "t": 24, "b": 0},
        },
    }
    
    capture_result = render_model_capture(
        figure=test_figure,
        width=800,
        height=600,
        key="test-capture-1",
    )
    
    if capture_result:
        st.success("✅ Component captured snapshot!")
        image_data = capture_result.get("image_data")
        notes = capture_result.get("notes", "")
        
        if image_data:
            st.image(image_data, caption=f"Captured Image - Notes: {notes}", width=600)

st.markdown("---")

st.header("Diagnostic Information")
with st.expander("Component Configuration", expanded=False):
    from frontend.components.custom_canvas import _COMPONENT_ROOT
    
    st.code(f"""
Component Root: {_COMPONENT_ROOT}
Root Exists: {_COMPONENT_ROOT.exists()}
    
Directory Contents:
{list(_COMPONENT_ROOT.iterdir()) if _COMPONENT_ROOT.exists() else 'N/A'}

Assets Directory:
{list((_COMPONENT_ROOT / 'assets').iterdir()) if (_COMPONENT_ROOT / 'assets').exists() else 'N/A'}
    """, language="text")

st.markdown("---")
st.caption("If you see the components above without errors, the custom component is working correctly! ✨")

