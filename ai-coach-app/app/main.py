# COM3610 Dissertation Project
# AI Driving Coach on Edge
# Authors: Weixiang Han (Ray)
# Date: 2025-05-14

import os
import threading
import asyncio
import socket
import pandas as pd
import numpy as np
import base64
import matplotlib.pyplot as plt
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from telemetry_recorder import TelemetryRecorder
from aicoach import AICoach
from datetime import datetime
import uvicorn
import fastf1
import io

# Setup FastF1 cache
cache_path = os.path.abspath("./cache")
if not os.path.exists(cache_path):
    os.makedirs(cache_path)
fastf1.Cache.enable_cache(cache_path)

# Preload FastF1 session
def preload_fastf1_data():
    print("📥 Preloading FastF1 session data for Silverstone 2024 Qualifying...")
    session = fastf1.get_session(2024, 'Silverstone', 'Q')
    session.load()
    print("✅ FastF1 session data loaded and cached!")

preload_fastf1_data()

# Initialise FastAPI app
app = FastAPI()

# Define and mount paths
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend"))
race_data_path = os.path.abspath("race_data")

app.mount("/static", StaticFiles(directory=frontend_path), name="static")
app.mount("/race_data", StaticFiles(directory=race_data_path), name="race_data")

# Telemetry recorder instance
recorder = TelemetryRecorder()

# Start telemetry listener
telemetry_thread = threading.Thread(target=recorder.run, daemon=True)
telemetry_thread.start()

@app.get("/")
async def serve_index():
    """
    Serve the main HTML page for the frontend.
    """
    with open(os.path.join(frontend_path, "index.html")) as f:
        return HTMLResponse(content=f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint to send live telemetry data to the frontend.

    Args:
        websocket (WebSocket): The WebSocket connection object.
    """
    await websocket.accept()
    recorder.start_recording()
    try:
        while True:
            # Telemetry data to send to the frontend
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

@app.get("/coaching-tip")
async def get_coaching_tip():
    """
    Generate a coaching tip for the player based on their last lap telemetry data.

    Returns:
        dict: A dictionary containing the coaching tip.
    """
    player_laps = recorder.get_lap_history()
    if not player_laps:
        return {"tip": "No lap data available yet. Complete a valid lap first!"}

    last_lap = player_laps[-1]
    if not last_lap["valid"] and (last_lap.get("total") is None or last_lap["total"] < 85.0):
        return {"tip": "Last lap was invalid and incomplete. Complete a full lap first!"}

    lap_completed_but_invalid = not last_lap["valid"]
    player_lap_df = recorder.get_last_lap_telemetry()
    if player_lap_df is None or player_lap_df.empty:
        return {"tip": "Telemetry data is not available yet. Please complete a lap!"}

    coach = AICoach()
    tip = coach.compare_laps(player_lap_df, lap_invalid_but_completed=lap_completed_but_invalid)
    if lap_completed_but_invalid:
        tip = ("⚠️ Oops! Looks like you exceeded track limits or made a mistake, "
               "but you still completed a lap. Let's help you improve! 🛠️\n\n" + tip)
    
    # Save the coaching tip to coach_output.txt
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.join("race_data", "coach_output.txt"), "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {tip}\n\n")
    
    return {"tip": tip}

@app.get("/generate-live-analysis")
async def generate_live_analysis():
    """
    Generate a player's laps telemetry graph, analysis of the graph compare them with FastF1's reference lap.

    Returns:
        dict: A dictionary containing the analysis image (base64) and AI insights.
    """
    laps = recorder.get_lap_history()
    if len(laps) < 2:
        return {"insight": "❌ At least 2 valid laps are needed to generate race analysis."}

    valid_laps = [lap for lap in laps if lap["valid"] and lap.get("total") is not None]
    if len(valid_laps) < 2:
        return {"insight": "❌ Not enough valid lap telemetry data to generate analysis."}

    # Process and interpolate telemetry data for comparison
    sorted_laps = sorted(valid_laps, key=lambda x: x["total"])
    lap1 = recorder.get_telemetry_for_lap(sorted_laps[0]["lap_index"])
    lap2 = recorder.get_telemetry_for_lap(sorted_laps[1]["lap_index"])

    if lap1 is None or lap2 is None or lap1.empty or lap2.empty:
        return {"insight": "❌ Missing telemetry for one or both laps."}

    # Generate comparison plots and AI insights
    # Sort by distance for interpolation
    lap1 = lap1.sort_values("Distance")
    lap2 = lap2.sort_values("Distance")
    
    common_distance = np.linspace(0, min(lap1["Distance"].max(), lap2["Distance"].max()), 1000)
    interp1 = pd.DataFrame({col: np.interp(common_distance, lap1["Distance"], lap1[col]) for col in ["Speed", "Throttle", "Brake"]})
    interp2 = pd.DataFrame({col: np.interp(common_distance, lap2["Distance"], lap2[col]) for col in ["Speed", "Throttle", "Brake"]})
    interp1["Distance"] = common_distance
    interp2["Distance"] = common_distance

    delta_time_player = np.cumsum((1 / interp1["Speed"].replace(0, 1)) - (1 / interp2["Speed"].replace(0, 1)))

    # Load Russell’s lap
    session = fastf1.get_session(2024, 'Silverstone', 'Q')
    session.load()
    rus_lap = session.laps.pick_drivers('RUS').pick_fastest()
    rus_tel = rus_lap.get_car_data().add_distance()
    rus_tel = rus_tel.sort_values("Distance")

    common_distance_rus = np.linspace(0, min(interp1["Distance"].max(), rus_tel["Distance"].max()), 1000)
    interp_rus = pd.DataFrame({col: np.interp(common_distance_rus, rus_tel["Distance"], rus_tel[col]) for col in ["Speed", "Throttle", "Brake"]})
    interp_you = pd.DataFrame({col: np.interp(common_distance_rus, interp1["Distance"], interp1[col]) for col in ["Speed", "Throttle", "Brake"]})
    interp_rus["Distance"] = common_distance_rus
    interp_you["Distance"] = common_distance_rus

    delta_time_rus = np.cumsum((1 / interp_you["Speed"].replace(0, 1)) - (1 / interp_rus["Speed"].replace(0, 1)))

    # === Plot ===
    fig, axs = plt.subplots(8, 1, figsize=(14, 20))

    axs[0].plot(interp1["Distance"], interp1["Speed"], label=f"Lap {sorted_laps[0]['lap_index']}", color="red")
    axs[0].plot(interp2["Distance"], interp2["Speed"], label=f"Lap {sorted_laps[1]['lap_index']}", color="blue")
    axs[0].set_title("Player Speed Comparison")
    axs[0].set_ylabel("Speed (km/h)")
    axs[0].legend()
    axs[0].grid(True)

    axs[1].plot(interp1["Distance"], interp1["Throttle"], color="red")
    axs[1].plot(interp2["Distance"], interp2["Throttle"], color="blue")
    axs[1].set_title("Player Throttle Comparison")
    axs[1].set_ylabel("Throttle (%)")
    axs[1].grid(True)

    axs[2].plot(interp1["Distance"], interp1["Brake"], color="red")
    axs[2].plot(interp2["Distance"], interp2["Brake"], color="blue")
    axs[2].set_title("Player Brake Comparison")
    axs[2].set_ylabel("Brake (%)")
    axs[2].grid(True)

    axs[3].plot(common_distance, delta_time_player, color="purple")
    axs[3].axhline(0, linestyle="--", color="black")
    axs[3].set_title(f"Delta Time: Lap {sorted_laps[0]['lap_index']} - Lap {sorted_laps[1]['lap_index']}")
    axs[3].set_xlabel("Distance (m)")
    axs[3].set_ylabel("Time Delta (s)")
    axs[3].grid(True)

    axs[4].plot(interp_you["Distance"], interp_you["Speed"], label="You", color="red")
    axs[4].plot(interp_rus["Distance"], interp_rus["Speed"], label="Russell", color="blue")
    axs[4].set_title("Speed Comparison vs Russell")
    axs[4].set_ylabel("Speed (km/h)")
    axs[4].legend()
    axs[4].grid(True)

    axs[5].plot(interp_you["Distance"], interp_you["Throttle"] * 100, color="red")
    axs[5].plot(interp_rus["Distance"], interp_rus["Throttle"], color="blue")
    axs[5].set_title("Throttle Comparison vs Russell")
    axs[5].set_ylabel("Throttle (%)")
    axs[5].grid(True)

    axs[6].plot(interp_you["Distance"], interp_you["Brake"], color="red")
    axs[6].plot(interp_rus["Distance"], interp_rus["Brake"], color="blue")
    axs[6].set_title("Brake Comparison vs Russell")
    axs[6].set_ylabel("Brake (%)")
    axs[6].grid(True)

    axs[7].plot(common_distance_rus, delta_time_rus, color="purple")
    axs[7].axhline(0, linestyle="--", color="black")
    axs[7].set_title("Delta Time (You - Russell)")
    axs[7].set_xlabel("Distance (m)")
    axs[7].set_ylabel("Time Delta (s)")
    axs[7].grid(True)

    plt.tight_layout()

    # Save + encode telemetry graph as player_analysis.png
    os.makedirs(race_data_path, exist_ok=True)
    output_image_path = os.path.join(race_data_path, "player_analysis.png")
    plt.savefig(output_image_path)
    plt.close()

    with open(output_image_path, "rb") as img_file:
        encoded = base64.b64encode(img_file.read()).decode("utf-8")

    # Call AI coach for analysis
    coach = AICoach()
    ai_insights = coach.analyze_graph_image(output_image_path)

    # Save AI insights to player_analysis_coach.txt
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    insights_path = os.path.join(race_data_path, "player_analysis_coach.txt")
    with open(insights_path, "w", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {ai_insights}\n\n")

    return {
        "image_base64": encoded,
        "ai_insights": ai_insights
    }

@app.get("/export")
async def export():
    """
    Export lap telemetry data to a CSV file.

    Returns:
        dict: A dictionary containing the export message and file URL.
    """
    os.makedirs("race_data", exist_ok=True)
    filename = "lap_telemetry.csv"
    filepath = os.path.join("race_data", filename)
    recorder.export_lap_data(filepath)

    return {
        "message": f"Lap data exported to {filepath}",
        "view_url": f"/race_data/{filename}"
    }

@app.get("/export-player-data")
async def export_player_data():
    """
    Export player lap data (sector times, total time, top speed) to a CSV file.

    Returns:
        dict: A dictionary containing the export message.
    """
    os.makedirs(race_data_path, exist_ok=True)
    filename = os.path.join(race_data_path, "player_data.csv")
    
    laps = recorder.get_lap_history()
    data = []
    for idx, lap in enumerate(laps):
        data.append({
            "Lap": idx + 1,
            "S1": lap["sectors"][0],
            "S2": lap["sectors"][1],
            "S3": lap["sectors"][2],
            "Total": lap["total"],
            "Top Speed": lap["top_speed"]
        })
    df = pd.DataFrame(data)
    df.to_csv(filename, index=False)
    
    return {"message": f"Player data exported to {filename}"}

def get_local_ip_addresses():
    """
    Retrieve the local IP addresses of the machine.

    Returns:
        set: A set of local IP addresses.
    """
    ips = {'172.20.10.2', 'localhost'} # Replace with your local IP address
    try:
        _, _, ip_list = socket.gethostbyname_ex(socket.gethostname())
        ips.update(ip_list)
    except socket.gaierror as e:
        print(f"⚠️ Failed to get IPs: {e}")
    return ips

print(f"📡 Available IPs: {get_local_ip_addresses()}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="172.20.10.2", port=8000, reload=True) # Replace with your local IP address
