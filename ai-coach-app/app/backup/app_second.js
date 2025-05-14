// Connect to WebSocket dynamically
const socket = new WebSocket(`ws://${location.host}/ws`);

socket.onopen = () => {
    console.log("✅ WebSocket connection established!");
};

socket.onmessage = (event) => {
    const data = JSON.parse(event.data);

    // Show dashboard when first packet received
    if (data.first_packet_received) {
        document.getElementById("loading-screen").style.display = "none";
        document.getElementById("dashboard").style.display = "block";
    }

    // Update Lap Times Table
    const lapTimesTable = document.querySelector("#lap-times tbody");
    lapTimesTable.innerHTML = "";

    if (Array.isArray(data.lap_history)) {
        data.lap_history.forEach((lap, index) => {
            const row = document.createElement("tr");
        
            // Add class based on validity
            row.classList.add(lap.valid === false ? "invalid-lap" : "valid-lap");
        
            // Check if it's the best lap
            const isBestLap = lap.total != null && lap.total === data.best_lap_time;
            if (isBestLap) {
                row.classList.add("best-lap");
            }
        
            // Compose label for lap number
            let lapLabel = `${index + 1}`;
            if (!lap.valid) lapLabel += " (Invalid)";
            else if (isBestLap) lapLabel += " (PB)";
        
            const sector1 = lap.sectors?.[0] != null ? formatTime(lap.sectors[0]) : "-";
            const sector2 = lap.sectors?.[1] != null ? formatTime(lap.sectors[1]) : "-";
            const sector3 = lap.sectors?.[2] != null ? formatTime(lap.sectors[2]) : "-";
            const lapTime = lap.total != null ? formatTime(lap.total) : "-";
            const topSpeed = lap.top_speed != null ? `${lap.top_speed.toFixed(1)} km/h` : "-";
        
            row.innerHTML = `
                <td>${lapLabel}</td>
                <td>${sector1}</td>
                <td>${sector2}</td>
                <td>${sector3}</td>
                <td>${lapTime}</td>
                <td>${topSpeed}</td>
            `;
            lapTimesTable.appendChild(row);
        });        
    }

    // Update Live Telemetry
    document.getElementById("speed").textContent = data.current_speed?.toFixed(1) ?? "0.0";
    document.getElementById("throttle").textContent = data.current_throttle != null ? (data.current_throttle * 100).toFixed(1) : "0.0";
    document.getElementById("brake").textContent = data.current_brake != null ? (data.current_brake * 100).toFixed(1) : "0.0";

    // Only valid laps should influence personal bests (server-side already filters)
    document.getElementById("best-lap").textContent = data.best_lap_time != null ? formatTime(data.best_lap_time) : "-";
    document.getElementById("best-s1").textContent = data.best_sector_times?.[0] != null ? formatTime(data.best_sector_times[0]) : "-";
    document.getElementById("best-s2").textContent = data.best_sector_times?.[1] != null ? formatTime(data.best_sector_times[1]) : "-";
    document.getElementById("best-s3").textContent = data.best_sector_times?.[2] != null ? formatTime(data.best_sector_times[2]) : "-";
};

// Format time to M:SS.sss
function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = (seconds % 60).toFixed(3).padStart(6, "0");
    return `${m}:${s}`;
}

// Export button click
function exportData() {
    fetch("/export")
        .then(res => res.json())
        .then(data => alert(data.message))
        .catch(err => console.error("Export Error:", err));
}

socket.onerror = (event) => {
    console.error("❌ WebSocket error:", event);
};

socket.onclose = (event) => {
    console.warn("⚠️ WebSocket connection closed:", event);
};
