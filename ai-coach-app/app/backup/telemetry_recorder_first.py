import sys
import os

# Add project root to Python sys.path
sys.path.append(os.path.abspath("../.."))

from src.telemetry_manager import F1TelemetryManager
from lib.f1_types.common import F1PacketType

import pandas as pd
import time

class TelemetryRecorder(F1TelemetryManager):
    def __init__(self, port_number=20777):
        super().__init__(port_number=port_number)

        self.recording = False
        self.lap_data = []
        self.lap_times = []
        self.current_lap_start_time = None

        self.sector_times = {0: None, 1: None, 2: None}
        self.sector_start_time = None
        self.current_sector = 0

        self.best_lap_time = None
        self.best_sector_times = {0: None, 1: None, 2: None}

        self.first_packet_received = False

    def start_recording(self):
        print("🚦 Starting Telemetry Recording...")
        self.recording = True
        self.lap_data = []
        self.lap_times = []
        self.sector_times = {0: None, 1: None, 2: None}
        self.sector_start_time = time.time()
        self.current_sector = 0
        self.current_lap_start_time = time.time()

    def stop_recording(self):
        print("🛑 Stopping Telemetry Recording...")
        self.recording = False

    def onTelemetryDataReceived(self, packet):
        if not self.recording:
            return

        if not self.first_packet_received:
            print("✅ First UDP telemetry packet received!")
            self.first_packet_received = True

        # --- Print packet type received ---
        print(f"📦 Packet ID received: {packet.header.packetId}")

        if packet.header.packetId == F1PacketType.CAR_TELEMETRY:
            car = packet.carTelemetryData[0]
            frame = {
                "timestamp": time.time(),
                "speed": car.speed,
                "throttle": car.throttle,
                "brake": car.brake,
                "steer": car.steer,
                "rpm": car.engineRPM,
                "gear": car.gear
            }
            self.lap_data.append(frame)

            print(f"➡️  Car Telemetry | Speed: {car.speed} km/h | Throttle: {car.throttle:.2f} | Brake: {car.brake:.2f}")

        if packet.header.packetId == F1PacketType.LAP_DATA:
            car_lap_data = packet.lapData[0]
            sector = car_lap_data.currentSector
            now = time.time()

            if sector != self.current_sector:
                if self.sector_start_time is not None:
                    sector_time = now - self.sector_start_time
                    sector_time = round(sector_time, 2)
                    self.sector_times[self.current_sector] = sector_time

                    if self.best_sector_times[self.current_sector] is None or sector_time < self.best_sector_times[self.current_sector]:
                        self.best_sector_times[self.current_sector] = sector_time

                    print(f"🏁 Sector {self.current_sector + 1} completed: {sector_time:.2f} seconds")

                self.current_sector = sector
                self.sector_start_time = now

            if car_lap_data.currentLapNum > len(self.lap_times):
                if self.current_lap_start_time:
                    lap_time = now - self.current_lap_start_time
                    lap_time = round(lap_time, 2)
                    self.lap_times.append(lap_time)

                    if self.best_lap_time is None or lap_time < self.best_lap_time:
                        self.best_lap_time = lap_time

                    print(f"🏎️ New Lap Completed! Lap Time: {lap_time:.2f} seconds")
                    self.current_lap_start_time = now
                    self.sector_start_time = now
                    self.sector_times = {0: None, 1: None, 2: None}
                    self.current_sector = 0

    def export_lap_data(self, filename="lap_telemetry.csv"):
        df = pd.DataFrame(self.lap_data)
        df.to_csv(filename, index=False)
        print(f"💾 Lap data exported to {filename}")
        return filename

    def get_lap_times(self):
        return self.lap_times

    def get_sector_times(self):
        return self.sector_times

    def get_best_lap_time(self):
        return self.best_lap_time

    def get_best_sector_times(self):
        return self.best_sector_times