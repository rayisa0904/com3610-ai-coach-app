# COM3610 Dissertation Project
# AI Driving Coach on Edge
# Authors: Weixiang Han (Ray)
# Date: 2025-05-14

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
    """
    A class to record and process telemetry data from F1 telemetry packets.
    """

    def __init__(self, port_number=20778):
        """
        Initialise the TelemetryRecorder with default values and register callbacks for telemetry packets.

        Args:
            port_number (int): The port number to listen for telemetry data (default: 20778).
        """
        super().__init__(port_number=port_number)

        # Recording state and lap data
        self.recording = False
        self.lap_history = []
        self.best_lap_time = None
        self.best_sector_times = {0: None, 1: None, 2: None}

        # Current lap and sector data
        self.current_sector = 0
        self.current_lap_start_time = None
        self.sector_start_time = None

        # Latest telemetry data
        self.latest_speed = 0
        self.latest_throttle = 0
        self.latest_brake = 0
        self.latest_lap_distance = 0.0
        self.latest_top_speed = 0.0

        # Telemetry for the current lap
        self.current_lap_telemetry = []

        # Flags and session data
        self.first_packet_received = False
        self.session_top_speed = 0

        # Current lap info
        self._current_lap_info = {
            "total": None,
            "sectors": [None, None, None],
            "valid": True,
            "top_speed": 0,
        }

        # Register callbacks for telemetry packets
        self.registerCallbacks({
            F1PacketType.LAP_DATA: self.on_lap_data_packet,
            F1PacketType.CAR_TELEMETRY: self.on_car_telemetry_packet,
        })

    def start_recording(self):
        """
        Start recording telemetry data and reset all relevant state variables.
        """
        print("🚦 Starting telemetry recording...")
        self.recording = True
        self.lap_history.clear()
        self.best_lap_time = None
        self.best_sector_times = {0: None, 1: None, 2: None}
        self.current_sector = 0
        self.current_lap_start_time = time.time()
        self.sector_start_time = time.time()
        self.session_top_speed = 0
        self.current_lap_telemetry.clear()

    def on_car_telemetry_packet(self, packet: PacketCarTelemetryData):
        """
        Process car telemetry data packets to update speed, throttle, brake, and top speed.

        Args:
            packet (PacketCarTelemetryData): The car telemetry data packet.
        """
        try:
            if not self.first_packet_received:
                print("✅ First telemetry packet received!")
                self.first_packet_received = True

            player_idx = 0 # Time Trial mode only has one player
            car = packet.m_carTelemetryData[player_idx]

            # Update latest telemetry data
            self.latest_speed = car.m_speed
            self.latest_throttle = car.m_throttle
            self.latest_brake = car.m_brake

            # Update top speeds
            if car.m_speed > self._current_lap_info["top_speed"]:
                self._current_lap_info["top_speed"] = car.m_speed
            if car.m_speed > self.session_top_speed:
                self.session_top_speed = car.m_speed
            if self.latest_speed > self.latest_top_speed:
                self.latest_top_speed = self.latest_speed

            print(f"➡️ Speed: {self.latest_speed:.1f} km/h | Throttle: {self.latest_throttle:.2f} | Brake: {self.latest_brake:.2f}")

        except Exception as e:
            print(f"⚠️ Error in on_car_telemetry_packet: {e}")

    def on_lap_data_packet(self, packet: PacketLapData):
        """
        Process lap data packets to update lap distance, sector times, and lap validity.

        Args:
            packet (PacketLapData): The lap data packet.
        """
        try:
            player_idx = 0
            lap = packet.m_lapData[player_idx]

            # Update lap distance
            self.latest_lap_distance = lap.m_lapDistance

            # Log telemetry data with accurate distance
            self.current_lap_telemetry.append({
                "Distance": self.latest_lap_distance,
                "Speed": self.latest_speed,
                "Throttle": self.latest_throttle,
                "Brake": self.latest_brake,
            })

            # Update sector times
            current_sector = lap.m_sector.value if hasattr(lap.m_sector, "value") else int(lap.m_sector)
            is_invalid = lap.m_currentLapInvalid 

            if current_sector != self.current_sector:
                now = time.time()
                if self.sector_start_time is not None:
                    sector_time = round(now - self.sector_start_time, 3)
                    self._current_lap_info["sectors"][self.current_sector] = sector_time
                    print(f"✅ Sector {self.current_sector + 1} completed: {sector_time:.3f} seconds")
                self.current_sector = current_sector
                self.sector_start_time = now

            # Check if the lap is completed
            if lap.m_lapDistance < 10.0 and any(self._current_lap_info["sectors"]):
                now = time.time()
                lap_time = round(now - self.current_lap_start_time, 3)

                sectors_complete = all(s is not None for s in self._current_lap_info["sectors"])
                is_valid = sectors_complete and not is_invalid

                self._current_lap_info["total"] = lap_time
                self._current_lap_info["valid"] = is_valid
                self._current_lap_info["top_speed"] = self.latest_top_speed

                # Attach telemetry data for this lap
                lap_with_telemetry = self._current_lap_info.copy()
                lap_with_telemetry["telemetry"] = self.current_lap_telemetry.copy()
                lap_with_telemetry["lap_index"] = len(self.lap_history)
                self.lap_history.append(lap_with_telemetry)

                self.current_lap_telemetry.clear()

                # Update best lap and sector times
                if is_valid:
                    if self.best_lap_time is None or lap_time < self.best_lap_time:
                        self.best_lap_time = lap_time
                    for i, sector_time in enumerate(self._current_lap_info["sectors"]):
                        if sector_time is not None:
                            if self.best_sector_times[i] is None or sector_time < self.best_sector_times[i]:
                                self.best_sector_times[i] = sector_time

                print(f"🏁 Lap completed (valid={is_valid}): {lap_time:.3f} sec, top speed: {self.latest_top_speed:.1f} km/h")

                # Reset for next lap
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

    def get_last_lap_telemetry(self):
        """
        Retrieve telemetry data for the last valid lap.

        Returns:
            pd.DataFrame: Telemetry data for the last valid lap.
        """
        for lap in reversed(self.lap_history):
            if lap.get("valid") and "telemetry" in lap:
                return pd.DataFrame(lap["telemetry"])
        return pd.DataFrame()

    def get_telemetry_for_lap(self, lap_index):
        """
        Retrieve telemetry data for a specific lap by its index.

        Args:
            lap_index (int): The index of the lap to retrieve telemetry data for.

        Returns:
            pd.DataFrame: A DataFrame containing telemetry data for the specified lap if valid.
            None: If the lap index is invalid or the lap does not have telemetry data.
        """
        if 0 <= lap_index < len(self.lap_history):
            lap = self.lap_history[lap_index]
            if lap.get("valid") and "telemetry" in lap:
                return pd.DataFrame(lap["telemetry"])
        return None

    def export_lap_data(self, filename="lap_telemetry.csv"):
        """
        Export lap history data to a CSV file.

        Args:
            filename (str): The name of the CSV file (default: "lap_telemetry.csv").

        Returns:
            str: The filename of the exported CSV.
        """
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

