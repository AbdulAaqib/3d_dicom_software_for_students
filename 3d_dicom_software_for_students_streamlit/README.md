# 3D DICOM Studio (Streamlit)

This Streamlit app mirrors the React prototype but keeps everything in a single
Python workflow: upload DICOM studies, convert them to STL meshes with
`dicom2stl`, inspect the geometry, capture annotated snapshots, and ask ChatGPT
questions with full access to the local artifacts.

---

## Features

- **Upload or sample selection** – drop a zipped DICOM series or pick from the
  bundled datasets in `dcm_examples/big_dicom/series-*`.
- **dicom2stl pipeline** – choose tissue presets, smoothing, reduction, and more,
  then run conversions that are cached under `.cache/dicom_sessions/<job_id>`.
- **Interactive STL viewer** – Plotly renders the latest mesh, and you can save
  webcam photos or uploaded renders as snapshots with notes. Click directly on the
  mesh to place labeled markers/arrows for in-app annotations.
- **MCP-style chatbot** – ChatGPT (OpenAI or Azure OpenAI) calls local tools like
  `list_conversions`, `get_conversion_detail`, `list_snapshots`, and `get_snapshot`
  to reason about meshes and annotations.
- **Tool catalog** – The MCP Tools tab surfaces the same schemas so you can debug
  what GPT can access or add new automation hooks.

---

## Quickstart

```bash
cd /Users/abdulaaqib/Developer/Github/3d_dicom_software_for_students
python3 -m venv 3d_dicom_software_for_students_streamlit/venv
source 3d_dicom_software_for_students_streamlit/venv/bin/activate
pip install -r 3d_dicom_software_for_students_streamlit/requirements.txt
streamlit run 3d_dicom_software_for_students_streamlit/streamlit/src/frontend/app.py
```

The app auto-loads environment variables from `3d_dicom_software_for_students/.env`
when available. Use the sidebar to switch between `Upload & Convert`, `Workspace`
(viewer + GPT + annotations), and `MCP Tools`.

---

## Environment variables

| Purpose | Variables |
| --- | --- |
| **Standard OpenAI** | `OPENAI_API_KEY`, `OPENAI_MODEL` (default `gpt-4o-mini`), `OPENAI_BASE_URL` (optional) |
| **Azure OpenAI** | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_KEY`, `AZURE_OPENAI_API_VERSION`, `AZURE_OPENAI_CHAT_DEPLOYMENT` |

Provide either the standard OpenAI key or the Azure quartet. When both are set,
Azure takes precedence.

### Local vs Streamlit Cloud

- **Local dev**: add keys to `../.env` (repo root) or export them in your shell.
- **Streamlit Community Cloud**: create `3d_dicom_software_for_students_streamlit/.streamlit/secrets.toml`:

  ```toml
  OPENAI_API_KEY = "sk-..."
  # or, for Azure:
  AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"
  AZURE_OPENAI_KEY = "..."
  AZURE_OPENAI_API_VERSION = "2024-08-01-preview"
  AZURE_OPENAI_CHAT_DEPLOYMENT = "gpt-4o-mini"
  ```

The app checks `os.environ` first, then `st.secrets`, so the same code works locally
and after deploying to Streamlit Cloud.

---

## Directory layout

```
3d_dicom_software_for_students_streamlit/
  ├── requirements.txt      # Streamlit + dicom2stl + openai deps
  └── streamlit/
      ├── src/
      │   ├── backend/
      │   │   ├── config.py          # Cache paths, sample discovery
      │   │   ├── dicom_pipeline.py  # Upload ingestion + dicom2stl orchestration
      │   │   └── mcp_registry.py    # Chatbot-accessible tool registry
      │   └── frontend/
      │       ├── app.py             # Streamlit entrypoint + navigation
      │       └── components/
      │           ├── workspace.py   # Upload + conversion UI
      │           ├── viewer.py      # Plotly STL viewer + snapshots
      │           ├── chatbot.py     # ChatGPT panel
      │           ├── mcp_tools.py   # Tool inspector
      │           └── intro/navigation helpers…
```

---

## Workflow overview

1. **Workspace tab**
   - Upload or choose a sample series.
   - Tune dicom2stl options (tissue type, smoothing, reduction, anisotropic smoothing).
   - Run the conversion and inspect logs/metadata recorded in `metadata.json`.
   - Preview the STL and save snapshots for later discussion.

2. **Chatbot tab**
   - The conversation history persists in `st.session_state`.
   - Each prompt can include previously saved snapshots (sent as multimodal inputs).
   - GPT automatically calls the registered MCP tools to fetch up-to-date stats and
     respond with accurate references to job IDs, STL paths, and annotations.

3. **MCP Tools tab**
   - Lists the same tool schemas so you can verify their parameters/descriptions.
   - Extend `backend/mcp_registry.py` with new actions (e.g., re-run dicom2stl,
     summarize metadata, or fetch annotations) and they become available both here
     and in the chatbot.

---

## Adding new capabilities

- **New sample datasets** – drop folders of `.dcm` slices under
  `dcm_examples/big_dicom/series-<id>`; they appear automatically.
- **Custom dicom2stl flags** – extend `ConversionOptions.to_cli_args()` in
  `backend/dicom_pipeline.py` and surface the inputs in `components/workspace.py`.
- **Extra MCP tools** – register them in `backend/mcp_registry.py` so GPT can call
  them via function-calling and they show up in the MCP Tools tab.
- **Additional viewers** – swap Plotly for PyVista, VTK.js, or any other renderer;
  `components/viewer.py` centralizes the rendering pipeline.

---

## Troubleshooting

- **dicom2stl missing** – ensure the virtualenv has `dicom2stl` installed
  (`pip install -r requirements.txt`). The CLI path is resolved automatically.
- **Plotly or numpy-stl errors** – install the optional deps listed in
  `requirements.txt`; they are required for the viewer.
- **Chatbot disabled** – verify the relevant OpenAI/Azure environment variables are
  set and that the `openai` Python package is up to date.

Happy scanning! 🎛️🧠

