# backend/main.py
import json
import logging
import os
import sqlite3
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path=ENV_FILE)

from backend.database import DB_PATH, init_db, save_generation
from services.validator import validate_and_draw

logger = logging.getLogger(__name__)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class CircuitRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)

system_instruction = """
You are an electrical engineer. Convert the user's prompt into a strict JSON object with exactly TWO keys: "schemdraw_code" and "visual_json".

1. "schemdraw_code" (String): Python script using `schemdraw` to draw the professional schematic.
- Assume `import schemdraw` and `import schemdraw.elements as elm`.
- Instantiate exactly: `d = schemdraw.Drawing()`.
- Use `.up()`, `.down()`, `.left()`, `.right()` to route the circuit cleanly.
- Do NOT call `d.draw()` or `d.save()`.

2. "visual_json" (Object): A blueprint for an interactive drag-and-drop EDA canvas.
- "components": Array of objects (id, type, value, x, y). Space coordinates by 100 units. Types must be generic (e.g., "resistor", "capacitor", "opamp", "diode", "nmos", "ground", "source").
- "wires": Array of objects (source_id, target_id) matching component ids.
"""

_client = None

def _get_client():
    global _client
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="API Key not configured.")
    if _client is None:
        _client = genai.Client(api_key=api_key)
    return _client

init_db()

@app.post("/generate")
async def generate_circuit(request: CircuitRequest):
    client = _get_client()
    
    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=request.prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
            ),
        )
        
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.replace('```json', '').replace('```', '')
            
        circuit_data = json.loads(raw)
        schemdraw_code = circuit_data.get("schemdraw_code")
        visual_json = circuit_data.get("visual_json")
        
        if not schemdraw_code or not visual_json:
            raise HTTPException(status_code=400, detail="LLM did not return both Schemdraw code and Visual JSON.")

        is_valid, svg_result = validate_and_draw(schemdraw_code)
        
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Schemdraw Error: {svg_result}")
            
        payload = json.dumps({
            "svg": svg_result, 
            "interactive": visual_json
        }, ensure_ascii=False)
        
        save_generation(request.prompt, schemdraw_code, payload)
        
        return {
            "status": "success",
            "svg_string": svg_result,
            "interactive_data": visual_json
        }

    except Exception as error:
        logger.exception("Generation failed.")
        raise HTTPException(status_code=500, detail=str(error))

@app.get("/history")
async def get_history():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, user_prompt, visual_json FROM history ORDER BY id ASC"
        ).fetchall()
    
    return [
        {
            "id": row["id"],
            "prompt": row["user_prompt"],
            "visual_data": json.loads(row["visual_json"]) if row["visual_json"] else {}
        }
        for row in rows
    ]

FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")