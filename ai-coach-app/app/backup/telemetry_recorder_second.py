import sys
import os
import time
import pandas as pd

# Add project root
sys.path.append(os.path.abspath("../.."))

from src.telemetry_manager import F1TelemetryManager
from lib.f1_types.packet_2_lap_data import PacketLapData
from lib.f1_types.packet_6_car_telemetry_data import PacketCarTelemetryData
from lib.f1_types.packet_14_time_trial_data import PacketTimeTrialData
from lib.f1_types.common import F1PacketType


class TelemetryRecorder(F1TelemetryManager):
    def __init__(self, port_number=20778):
        super().__init__(port_number=port_number)

        self.recording = False
        self.lap_history = []
        self.best_lap_time = None
        self.best_sector_times = {0: None, 1: None, 2: None}

        self.current_sector = 0
        self.current_lap_start_time = None
        self.sector_start_time = None

        self.latest_speed = 0
        self.latest_throttle = 0
        self.latest_brake = 0
        self.latest_top_speed = 0.0

        self.first_packet_received = False
        self.session_top_speed = 0
        
        self._current_lap_info = {
            "total": None,
            "sectors": [None, None, None],
            "valid": True,
            "top_speed": 0,
        }

        self.registerCallbacks({
            F1PacketType.LAP_DATA: self.on_lap_data_packet,
            F1PacketType.CAR_TELEMETRY: self.on_car_telemetry_packet,
            F1PacketType.TIME_TRIAL: self.on_time_trial_data_packet,
        })

    def start_recording(self):
        print("🚦 Starting telemetry recording...")
        self.recording = True
        self.lap_history.clear()
        self.best_lap_time = None
        self.best_sector_times = {0: None, 1: None, 2: None}
        self.current_sector = 0
        self.current_lap_start_time = time.time()
        self.sector_start_time = time.time()
        self.session_top_speed = 0

    def stop_recording(self):
        print("🛑 Stopping telemetry recording...")
        self.recording = False

    def on_car_telemetry_packet(self, packet: PacketCarTelemetryData):
        try:
            if not self.first_packet_received:
                print("✅ First telemetry packet received!")
                self.first_packet_received = True

            player_idx = 0 # Always 0 for Time Trial
            car = packet.m_carTelemetryData[player_idx]

            self.latest_speed = car.m_speed
            self.latest_throttle = car.m_throttle
            self.latest_brake = car.m_brake

            # 🔴 Live Debug Line
            print(f"➡️ Speed: {self.latest_speed:.1f} km/h | Throttle: {self.latest_throttle:.2f} | Brake: {self.latest_brake:.2f}")

            if car.m_speed > self._current_lap_info["top_speed"]:
                self._current_lap_info["top_speed"] = car.m_speed

            if car.m_speed > self.session_top_speed:
                self.session_top_speed = car.m_speed
            
            # Update top speed
            if self.latest_speed > self.latest_top_speed:
                self.latest_top_speed = self.latest_speed

        except Exception as e:
            print(f"⚠️ Error in on_car_telemetry_packet: {e}")

    def on_time_trial_data_packet(self, packet: PacketTimeTrialData):
        try:
            self.current_lap_valid_from_time_trial = packet.m_playerSessionBestDataSet.m_isValid
        except Exception as e:
            print(f"⚠️ Error in on_time_trial_data_packet: {e}")

    def on_lap_data_packet(self, packet: PacketLapData):
        try:
            player_idx = 0  # Always 0 for Time Trial
            lap = packet.m_lapData[player_idx]

            # Determine current sector safely
            current_sector = lap.m_sector.value if hasattr(lap.m_sector, "value") else int(lap.m_sector)
            is_invalid = lap.m_currentLapInvalid or (
                hasattr(self, "current_lap_valid_from_time_trial") and not self.current_lap_valid_from_time_trial
            )

            # Sector crossing logic
            if current_sector != self.current_sector:
                now = time.time()
                if self.sector_start_time is not None:
                    sector_time = round(now - self.sector_start_time, 3)
                    self._current_lap_info["sectors"][self.current_sector] = sector_time

                    print(f"✅ Sector {self.current_sector + 1} completed: {sector_time:.3f} seconds")

                self.current_sector = current_sector
                self.sector_start_time = now

            # Check for lap completion (lap reset & at least one sector completed)
            if lap.m_lapDistance < 10.0 and any(self._current_lap_info["sectors"]):
                now = time.time()
                lap_time = round(now - self.current_lap_start_time, 3)

                # Final validation: all 3 sectors must be filled and not flagged invalid
                sectors_complete = all(sector is not None for sector in self._current_lap_info["sectors"])
                is_valid = sectors_complete and not is_invalid

                self._current_lap_info["total"] = lap_time
                self._current_lap_info["valid"] = is_valid
                self._current_lap_info["top_speed"] = self.latest_top_speed

                self.lap_history.append(self._current_lap_info.copy())

                # ✅ Update bests ONLY IF lap is fully valid
                if is_valid:
                    if self.best_lap_time is None or lap_time < self.best_lap_time:
                        self.best_lap_time = lap_time

                    for i, sector_time in enumerate(self._current_lap_info["sectors"]):
                        if sector_time is not None:
                            if self.best_sector_times[i] is None or sector_time < self.best_sector_times[i]:
                                self.best_sector_times[i] = sector_time

                print(f"🏁 Lap completed (valid={is_valid}): {lap_time:.3f} sec, top speed: {self.latest_top_speed:.1f} km/h")

                # 🔁 Reset lap tracking
                self._current_lap_info = {
                    "total": None,
                    "sectors": [None, None, None],
                    "valid": True,
                    "top_speed": 0,
                }
                self.current_sector = 0
                self.current_lap_start_time = now
                self.sector_start_time = now
                self.latest_top_speed = 0.0

        except Exception as e:
            print(f"⚠️ Error in on_lap_data_packet: {e}")

    def export_lap_data(self, filename="lap_telemetry.csv"):
        df = pd.DataFrame(self.lap_history)
        df.to_csv(filename, index=False)
        print(f"💾 Exported lap data to {filename}")
        return filename

    def get_lap_history(self):
        return self.lap_history

    def get_best_lap_time(self):
        return self.best_lap_time

    def get_best_sector_times(self):
        return self.best_sector_times

    def get_latest_speed(self):
        return self.latest_speed

    def get_latest_throttle(self):
        return self.latest_throttle

    def get_latest_brake(self):
        return self.latest_brake

    def get_top_speed(self):
        return self.session_top_speed

    def is_first_packet_received(self):
        return self.first_packet_received
    
    def get_session_top_speed(self):
        return self.latest_top_speed

