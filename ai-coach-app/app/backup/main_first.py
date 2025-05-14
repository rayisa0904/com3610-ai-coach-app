from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from telemetry_recorder import TelemetryRecorder
import uvicorn
import asyncio
import threading
import socket
import os

app = FastAPI()

frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend"))
app.mount("/static", StaticFiles(directory=frontend_path), name="static")

recorder = TelemetryRecorder()

telemetry_thread = threading.Thread(target=recorder.run, daemon=True)
telemetry_thread.start()

@app.get("/")
async def get():
    # Serve the frontend HTML manually
    with open(os.path.join(frontend_path, "index.html")) as f:
        return HTMLResponse(content=f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    recorder.start_recording()

    try:
        while True:
            data = {
                "lap_times": recorder.get_lap_times()[-10:],
                "sector_times": recorder.get_sector_times(),
                "best_lap_time": recorder.get_best_lap_time(),
                "best_sector_times": recorder.get_best_sector_times(),
                "current_speed": recorder.lap_data[-1]["speed"] if recorder.lap_data else 0,
                "current_throttle": recorder.lap_data[-1]["throttle"] if recorder.lap_data else 0,
                "current_brake": recorder.lap_data[-1]["brake"] if recorder.lap_data else 0,
                "first_packet_received": recorder.first_packet_received,
            }
            await websocket.send_json(data)
            await asyncio.sleep(0.1)
    except Exception as e:
        print(f"WebSocket connection closed: {e}")

@app.get("/export")
async def export_data():
    filename = recorder.export_lap_data()
    return {"message": f"Data exported to {filename}"}

def get_local_ip_addresses() -> set[str]:
    """Get local IP addresses including '172.20.10.2' and 'localhost'."""
    ip_addresses = {'172.20.10.2', 'localhost'}

    try:
        hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
        ip_addresses.update(ips)
    except socket.gaierror as e:
        print(f"⚠️ Error detecting local IPs: {e}")

    return ip_addresses
print(get_local_ip_addresses())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
