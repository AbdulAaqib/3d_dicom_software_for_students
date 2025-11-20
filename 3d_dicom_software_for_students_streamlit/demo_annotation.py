"""
Demo script for the improved annotation canvas
Shows how to annotate captured medical images with the new PictogramLLM-inspired UI
"""

import streamlit as st
import base64
from pathlib import Path
from streamlit.src.frontend.components.custom_canvas import render_snapshot_canvas

st.set_page_config(
    page_title="Medical Image Annotation Demo",
    page_icon="🖌️",
    layout="wide"
)

st.title("🖌️ Medical Image Annotation Tool")
st.markdown("""
### Draw annotations directly on your captured medical images
This demo showcases the improved annotation canvas with a modern UI inspired by PictogramLLM.

**Features:**
- 🎨 9 color options including white for dark images
- 📏 Adjustable brush size (1-20px)
- ↩️ Undo/Redo support
- 🧹 Eraser tool
- 💾 Save annotations with transparent background
- 🗑️ Clear canvas or save & clear in one action
""")

# Initialize session state
if 'annotation_result' not in st.session_state:
    st.session_state.annotation_result = None

# Sample image selector
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📸 Select or Upload an Image")
    
    # Option to use sample or upload
    image_source = st.radio(
        "Image source:",
        ["Sample Medical Image", "Upload Your Own"],
        horizontal=True
    )
    
    if image_source == "Sample Medical Image":
        # Create a simple sample image (you can replace with actual medical image)
        import numpy as np
        from PIL import Image
        import io
        
        # Create a sample grayscale "medical" image
        sample_image = np.random.randint(0, 256, (400, 600), dtype=np.uint8)
        # Add some structure to make it look more medical
        sample_image[100:150, 200:400] = 200  # Bright region
        sample_image[250:300, 150:250] = 50   # Dark region
        
        img = Image.fromarray(sample_image, mode='L')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        image_bytes = buffer.getvalue()
        background_b64 = base64.b64encode(image_bytes).decode()
        
        st.image(img, caption="Sample Medical Image", width="stretch")
    else:
        uploaded_file = st.file_uploader(
            "Upload an image (PNG, JPG, JPEG)",
            type=['png', 'jpg', 'jpeg']
        )
        
        if uploaded_file is not None:
            image_bytes = uploaded_file.read()
            background_b64 = base64.b64encode(image_bytes).decode()
            st.image(image_bytes, caption="Uploaded Image", width="stretch")
        else:
            st.info("👆 Please upload an image to annotate")
            background_b64 = None

with col2:
    st.subheader("⚙️ Settings")
    
    # Annotation settings
    default_color = st.color_picker("Default Color", "#FF0000")
    canvas_width = st.slider("Canvas Width", 400, 1200, 900, 50)
    canvas_height = st.slider("Canvas Height", 300, 800, 600, 50)

# Annotation canvas
if 'background_b64' in locals() and background_b64 is not None:
    st.markdown("---")
    st.subheader("✏️ Annotation Canvas")
    
    st.markdown("""
    **Instructions:**
    - Use the **color palette** button at the top to change colors
    - Adjust **brush size** with the slider
    - Use **Undo/Redo** to fix mistakes
    - Toggle **Eraser** to remove annotations
    - Click **Clear All** to start over
    - Click **Save Annotations** when done
    """)
    
    # Render the annotation canvas
    result = render_snapshot_canvas(
        background_base64=background_b64,
        mime_type="image/png",
        stroke_color=default_color,
        width=canvas_width,
        height=canvas_height,
        show_toolbar=True,
        key="annotation_canvas"
    )
    
    # Display results
    if result is not None:
        st.session_state.annotation_result = result
        
        if result.reason == "save":
            st.success("✅ Annotations saved!")
        elif result.reason == "clear":
            st.info("🗑️ Canvas cleared and saved!")
        
        # Show the annotated image
        if result.image_data_url:
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.markdown("### 📊 Annotated Image")
                st.image(result.image_data_url, width="stretch")
            
            with col_b:
                st.markdown("### 📝 Annotation Data")
                st.json({
                    "reason": result.reason,
                    "annotations_count": len(result.annotations.get("paths", [])),
                    "has_image": result.image_data_url is not None
                })
                
                # Download button
                if result.image_data_url:
                    # Extract base64 data from data URL
                    if "," in result.image_data_url:
                        base64_data = result.image_data_url.split(",")[1]
                        image_data = base64.b64decode(base64_data)
                        
                        st.download_button(
                            label="⬇️ Download Annotated Image",
                            data=image_data,
                            file_name="annotated_medical_image.png",
                            mime="image/png"
                        )

else:
    st.warning("⚠️ Please select or upload an image to begin annotation")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 2rem;'>
    <p>🎨 <strong>Modern Medical Image Annotation Tool</strong></p>
    <p>Powered by react-sketch-canvas with a PictogramLLM-inspired UI</p>
</div>
""", unsafe_allow_html=True)



