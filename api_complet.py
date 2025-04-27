from fastapi import FastAPI
from fastapi.responses import JSONResponse
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d import Axes3D
import base64
import os
import requests
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import json
import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Inițializare FastAPI
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Încarcă variabile de mediu
load_dotenv()

# Conectare Google APIs
service_account_info = json.loads(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))
credentials = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]
)
gc = gspread.authorize(credentials)
drive_service = build('drive', 'v3', credentials=credentials)

@app.post("/genereaza-imagine/")
def genereaza_imagine():
    try:
        # Căutăm cel mai recent Sheet
        query = "name contains 'x' and mimeType = 'application/vnd.google-apps.spreadsheet'"
        results = drive_service.files().list(q=query, orderBy="createdTime desc", pageSize=1).execute()
        files = results.get('files', [])

        if not files:
            return JSONResponse(content={"error": "No sheet found"}, status_code=404)

        sheet_id = files[0]['id']
        sheet = gc.open_by_key(sheet_id)
        worksheet = sheet.sheet1

        # Verificăm dacă există masurare în progres (L2)
        masurare_in_progress = worksheet.acell('L2').value

        if masurare_in_progress != "1":
            return JSONResponse(content={"error": "No measurement in progress"}, status_code=404)

        # Luăm toate valorile
        all_values = worksheet.get_all_values()
        last_row = all_values[-1]
        x_sonda = float(last_row[0])
        y_sonda = float(last_row[1])
        z_masurat = float(last_row[2])

        # --- GENERĂM IMAGINEA ---
        magnet_length = float(worksheet.acell('I2').value)
        magnet_width = float(worksheet.acell('J2').value)
        magnet_height = float(worksheet.acell('K2').value)

        z_sonda = magnet_height + z_masurat

        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection='3d')

        # Magnet
        ax.bar3d(0, 0, 0, magnet_length, magnet_width, magnet_height, color='blue', alpha=0.3, shade=True)
        ax.plot([0, magnet_length], [0, 0], [magnet_height, magnet_height], color='black', linestyle='--', linewidth=2)
        ax.text(magnet_length/2, -3, magnet_height + 0.5, "Suprafață Magnet", color='black', fontsize=12)

        # Sonda
        ax.scatter(x_sonda, y_sonda, z_sonda, color='red', s=150)
        ax.plot([x_sonda, x_sonda], [y_sonda, y_sonda], [z_sonda, magnet_height], color='gray', linestyle='--')
        ax.scatter(x_sonda, y_sonda, magnet_height, color='black', s=50, alpha=0.7)
        ax.text(x_sonda + 1, y_sonda + 1, magnet_height, f"{z_masurat} mm", color='black', fontsize=12, bbox=dict(facecolor='white', alpha=0.8))

        ax.plot([x_sonda, x_sonda], [y_sonda, 0], [z_sonda, z_sonda], color='green', linestyle='--')
        ax.scatter(x_sonda, 0, z_sonda, color='green', s=50, alpha=0.7)
        ax.text(x_sonda + 1, 0, z_sonda + 1, f"{y_sonda}", color='green', fontsize=12, bbox=dict(facecolor='white', alpha=0.8))

        ax.plot([x_sonda, 0], [y_sonda, y_sonda], [z_sonda, z_sonda], color='purple', linestyle='--')
        ax.scatter(0, y_sonda, z_sonda, color='purple', s=50, alpha=0.7)
        ax.text(0, y_sonda + 1, z_sonda + 1, f"{x_sonda}", color='purple', fontsize=12, bbox=dict(facecolor='white', alpha=0.8))

        ax.text(x_sonda + 2, y_sonda + 2, z_sonda + 2, f"({x_sonda}, {y_sonda}, {z_masurat})", color='red', fontsize=14, bbox=dict(facecolor='white', alpha=0.8))

        ax.set_xlim(0, magnet_length)
        ax.set_ylim(0, magnet_width)
        ax.set_zlim(0, magnet_height + 30)
        ax.set_xlabel('X (mm)')
        ax.set_ylabel('Y (mm)')
        ax.set_zlabel('Distanță (mm)')

        z_ticks_real = [0, magnet_height] + [magnet_height + i for i in range(5, 31, 5)]
        z_tick_labels = ['Baza Magnet', 'Suprafață Magnet'] + [f'{i} mm' for i in range(5, 31, 5)]
        ax.set_zticks(z_ticks_real)
        ax.set_zticklabels(z_tick_labels)

        ax.set_title("Poziția sondei față de magnet")
        ax.view_init(elev=30, azim=45)

        output_file = "sonda_temp.png"
        plt.savefig(output_file)
        plt.close()

        with open(output_file, "rb") as img_file:
            encoded_string = base64.b64encode(img_file.read()).decode('utf-8')

        return JSONResponse(content={"image_base64": encoded_string})

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
