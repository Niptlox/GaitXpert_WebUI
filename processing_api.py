from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict
from threading import Thread
import time
import random

app = FastAPI()

# pip install fastapi uvicorn
# Запуск сервера: uvicorn processing_api:app --host 0.0.0.0 --port 8081

# Хранилище состояния обработки
processings: Dict[int, Dict] = {}
processing_counter = 1

def fake_processing(processing_id: int):
    """Имитация обработки видео с прогрессом"""
    for i in range(1, 11):
        processings[processing_id]['progress'] = i / 10
        time.sleep(0.5)  # имитируем задержку
    # Генерируем случайный результат
    result = random.choice([
        "Нормальная походка",
        "Аномальная походка",
        "Болезнь Паркинсона"
    ])
    processings[processing_id]['is_finish'] = True
    processings[processing_id]['result'] = result

@app.post("/api/processing/start")
async def start_processing(file: UploadFile = File(...)):
    global processing_counter
    processing_id = processing_counter
    processing_counter += 1
    # Сохраняем начальное состояние
    processings[processing_id] = {
        "progress": 0,
        "is_finish": False,
        "result": ""
    }
    # Запускаем имитацию обработки в отдельном потоке
    thread = Thread(target=fake_processing, args=(processing_id,))
    thread.start()
    return {"processing_id": processing_id}

@app.get("/api/processing/get")
async def get_processing(processing_id: int):
    data = processings.get(processing_id)
    if not data:
        raise HTTPException(status_code=404, detail="processing_id not found")
    return {
        "progress": data["progress"],
        "is_finish": data["is_finish"],
        "result": data["result"]
    }

@app.get("/api/processing/all")
async def get_all_processings():
    return {
        str(pid): {
            "progress": data["progress"],
            "is_finish": data["is_finish"],
            "result": data["result"]
        }
        for pid, data in processings.items()
    }
