import os
import threading
import asyncio
import socket
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from telemetry_recorder import TelemetryRecorder
import uvicorn

app = FastAPI()

frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend"))
app.mount("/static", StaticFiles(directory=frontend_path), name="static")

recorder = TelemetryRecorder()

telemetry_thread = threading.Thread(target=recorder.run, daemon=True)
telemetry_thread.start()

@app.get("/")
async def serve_index():
    with open(os.path.join(frontend_path, "index.html")) as f:
        return HTMLResponse(content=f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    recorder.start_recording()

    try:
        while True:
            data = {
                "lap_history": recorder.get_lap_history(),
                "best_lap_time": recorder.get_best_lap_time(),
                "best_sector_times": recorder.get_best_sector_times(),
                "current_speed": recorder.get_latest_speed(),
                "current_throttle": recorder.get_latest_throttle(),
                "current_brake": recorder.get_latest_brake(),
                "first_packet_received": recorder.is_first_packet_received(),
            }
            await websocket.send_json(data)
            await asyncio.sleep(0.1)
    except Exception as e:
        print(f"⚡ WebSocket connection closed: {e}")

@app.get("/export")
async def export():
    filename = recorder.export_lap_data()
    return {"message": f"Exported to {filename}"}

def get_local_ip_addresses():
    ips = {'172.20.10.2', 'localhost'}
    try:
        _, _, ip_list = socket.gethostbyname_ex(socket.gethostname())
        ips.update(ip_list)
    except socket.gaierror as e:
        print(f"⚠️ Failed to get IPs: {e}")
    return ips

print(f"📡 Available IPs: {get_local_ip_addresses()}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
