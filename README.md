# 3d_dicom_software_for_students

A playground for turning classroom DICOM datasets into interactive STL meshes and
chatting with GPT about the resulting anatomy. The React prototype now has a
Streamlit twin that:

- Ingests zipped DICOM studies or bundled samples and runs `dicom2stl`.
- Caches conversion logs/metadata for future analysis.
- Renders the STL in-browser (Plotly) and lets you capture annotated snapshots.
- Exposes MCP-style tools so ChatGPT can inspect meshes, metadata, and snapshots.
- Supports in-app mesh annotations (markers/arrows/labels) that sync with the chatbot.

## Streamlit workspace quickstart

```bash
cd /Users/abdulaaqib/Developer/Github/3d_dicom_software_for_students
python3 -m venv 3d_dicom_software_for_students_streamlit/venv
source 3d_dicom_software_for_students_streamlit/venv/bin/activate
pip install -r 3d_dicom_software_for_students_streamlit/requirements.txt
streamlit run 3d_dicom_software_for_students_streamlit/streamlit/src/frontend/app.py
```

### dicom2stl conversion flow

1. Open the `Workspace` tab.
2. Upload a `.zip` containing all slices (or drop multiple `.dcm` files).  
   Built-in samples live under `dcm_examples/big_dicom/series-*`.
3. Pick the tissue preset, smoothing, and reduction options.
4. Click `Convert` – the app stages files in `.cache/dicom_sessions/<job_id>` and
   invokes `dicom2stl --meta` to produce `output.stl` + `metadata.json`.
5. After a successful run, hop to the `Workspace` tab to inspect, annotate, and chat
   about the generated STL.

All conversions stay local; reruns reuse cached directories so you can share the
paths with the chatbot/tools.

### STL viewer & snapshots

The latest mesh renders with Plotly’s `Mesh3d`. After inspecting the mesh you can:

- Click directly on the mesh to drop labeled markers with colored arrows. These annotations
  stay attached to each STL and are queryable via MCP tools.
- Capture a webcam photo (`st.camera_input`) or upload an annotated PNG/JPG.
- Add notes describing what the snapshot highlights.
- Save it to session storage so the chatbot or MCP tools can retrieve both the
  image (base64) and its notes.
- Open the new **snapshot canvas** (custom Streamlit component backed by Fabric.js) to draw markers,
  arrows, labels, or freehand marks directly on the captured still. Saving produces both structured
  annotation JSON and a flattened PNG preview that the chatbot can reference later.

### ChatGPT + MCP tools

The `Chatbot` tab wires OpenAI function-calling to local tools:

| Tool | Purpose |
| --- | --- |
| `list_conversions` | Summaries of each dicom2stl run (paths, metadata). |
| `get_conversion_detail` | Deep dive on a single job ID. |
| `list_snapshots` | Enumerate saved renders/photos with optional job filter. |
| `get_snapshot` | Return a specific snapshot (base64 + notes). |
| `list_annotations` | List mesh annotations (markers/arrows) per job. |
| `get_annotation` | Fetch details for a specific annotation ID. |

Set either:

- Standard OpenAI: `OPENAI_API_KEY` (+ optional `OPENAI_MODEL`, `OPENAI_BASE_URL`)
- GPT: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_KEY`,
  `AZURE_OPENAI_API_VERSION`, `AZURE_OPENAI_CHAT_DEPLOYMENT`

Place them in `3d_dicom_software_for_students/.env` (auto-loaded at startup) or
export them in your shell before launching Streamlit. When you send a chat message
you can also attach saved snapshots—the assistant receives them as multimodal inputs.

### Environment configuration (local vs Streamlit Cloud)

- **Local development** – create `3d_dicom_software_for_students/.env`:

  ```
  OPENAI_API_KEY=sk-your-key
  # or Azure:
  AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
  AZURE_OPENAI_KEY=***
  AZURE_OPENAI_API_VERSION=2024-08-01-preview
  AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o-mini
  ```

- **Streamlit Community Cloud / sharing** – add a `secrets.toml` next to the app:

  ```
  3d_dicom_software_for_students_streamlit/.streamlit/secrets.toml
  ```

  ```toml
  OPENAI_API_KEY = "sk-your-key"
  # or the Azure quartet:
  AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"
  AZURE_OPENAI_KEY = "..."
  AZURE_OPENAI_API_VERSION = "2024-08-01-preview"
  AZURE_OPENAI_CHAT_DEPLOYMENT = "gpt-4o-mini"
  ```

The app automatically checks `os.environ` first, then `st.secrets`, so the same code
works locally and when deployed to Streamlit Cloud.

- **Azure attachment tips** – GPT deployments currently limit multimodal inputs to five
  inline images per request. The chatbot now packages annotated snapshots as inline `data:` URLs;
  if a request with attachments fails, re-run with fewer images or verify the deployment supports
  GPT‑4o style multimodal prompts.

### MCP tools catalog

The `MCP Tools` tab lists the same tool schemas that the chatbot can call. Use it
as a debugging surface to verify what metadata is exposed to GPT or to prototype
new tools (e.g., re-running dicom2stl with different thresholds).