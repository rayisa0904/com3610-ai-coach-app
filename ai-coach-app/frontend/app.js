/*
COM3610 Dissertation Project
AI Driving Coach on Edge
Authors: Weixiang Han (Ray)
Date: 2025-05-14 
*/

// Connect to WebSocket dynamically
const socket = new WebSocket(`ws://${location.host}/ws`);

// Establish WebSocket connection
socket.onopen = () => {
    console.log("✅ WebSocket connection established!");
};

// Handle incoming WebSocket messages
socket.onmessage = (event) => {
    const data = JSON.parse(event.data);

    // Show dashboard when first telemetry packet received
    if (data.first_packet_received) {
        document.getElementById("loading-screen").style.display = "none";
        showTab('main');
    }

    // Update the Lap Times Table with lap history data
    const lapTimesTable = document.querySelector("#lap-times tbody");
    lapTimesTable.innerHTML = "";

    let lastValidLapIndex = -1;

    if (Array.isArray(data.lap_history)) {
        data.lap_history.forEach((lap, index) => {
            const row = document.createElement("tr");
            row.classList.add(lap.valid === false ? "invalid-lap" : "valid-lap");

            const isBestLap = lap.total != null && lap.total === data.best_lap_time;
            if (isBestLap) row.classList.add("best-lap");

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
            
            // Fetch coaching tip after processing lap history
            if (lap.valid) lastValidLapIndex = index;
        });

        if (lastValidLapIndex >= 0) fetchCoachingTip();
    }

    // Update live car data (speed, throttle, brake)
    document.getElementById("speed").textContent = data.current_speed?.toFixed(1) ?? "0.0";
    document.getElementById("throttle").textContent = data.current_throttle != null ? (data.current_throttle * 100).toFixed(1) : "0.0";
    document.getElementById("brake").textContent = data.current_brake != null ? (data.current_brake * 100).toFixed(1) : "0.0";

    // Update personal bests (lap time and sector times)
    document.getElementById("best-lap").textContent = data.best_lap_time != null ? formatTime(data.best_lap_time) : "-";
    document.getElementById("best-s1").textContent = data.best_sector_times?.[0] != null ? formatTime(data.best_sector_times[0]) : "-";
    document.getElementById("best-s2").textContent = data.best_sector_times?.[1] != null ? formatTime(data.best_sector_times[1]) : "-";
    document.getElementById("best-s3").textContent = data.best_sector_times?.[2] != null ? formatTime(data.best_sector_times[2]) : "-";
};

// Fetch oaching tip from the server
function fetchCoachingTip() {
    document.getElementById("coaching-tip").textContent = "🧠 Analysing your lap now...";
    fetch("/coaching-tip")
        .then(res => res.json())
        .then(data => {
            if (data.tip && data.tip !== "No tip generated yet!" && data.tip !== "Telemetry data is not available yet. Please complete a lap!") {
                document.getElementById("coaching-tip").textContent = data.tip;
            } else {
                console.log("No new valid tip, keeping previous displayed.");
            }
        })
        .catch(err => {
            console.error("Error fetching coaching tip:", err);
            document.getElementById("coaching-tip").textContent = "Unable to get coaching tip.";
        });
}

// Format time in seconds to M:SS.sss format
function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = (seconds % 60).toFixed(3).padStart(6, "0");
    return `${m}:${s}`;
}

// Export lap data to a CSV file
function exportData() {
    fetch("/export")
        .then(res => res.json())
        .then(data => {
            alert(data.message);

            if (data.view_url) {
                showTab('data');

                fetch(data.view_url)
                    .then(res => res.text())
                    .then(csv => {
                        const rows = csv.trim().split("\n").map(r => r.split(","));
                        const table = document.createElement("table");
                        table.className = "table table-striped table-dark text-center";

                        const thead = document.createElement("thead");
                        thead.innerHTML = "<tr>" + rows[0].map(h => `<th>${h}</th>`).join("") + "</tr>";
                        table.appendChild(thead);

                        const tbody = document.createElement("tbody");
                        for (let i = 1; i < rows.length; i++) {
                            const row = document.createElement("tr");
                            row.innerHTML = rows[i].map(cell => `<td>${cell}</td>`).join("");
                            tbody.appendChild(row);
                        }
                        table.appendChild(tbody);

                        const container = document.getElementById("lap-data-table-container");
                        container.innerHTML = "";
                        container.appendChild(table);
                    })
                    .catch(err => {
                        console.error("❌ Failed to load CSV:", err);
                        document.getElementById("lap-data-table-container").innerHTML = "<p class='text-danger'>❌ Failed to load exported data.</p>";
                    });
            }
        })
        .catch(err => {
            console.error('Export error:', err);
            alert("❌ Failed to export lap data.");
        });
}

// Load race analysis data and display it
function loadRaceAnalysis() {
    showTab('analysis');
    const imgContainer = document.getElementById("analysis-image-wrapper");
    const chatbotContainer = document.getElementById("analysis-chatbot");

    imgContainer.innerHTML = "⏳ Generating live analysis...";
    chatbotContainer.innerHTML = "🧠 Processing insights...";

    fetch("/generate-live-analysis")
        .then(res => res.json())
        .then(data => {
            // 🔥 Image
            if (data.image_base64) {
                imgContainer.innerHTML = `<img src="data:image/png;base64,${data.image_base64}" class="img-fluid" alt="Race Analysis Graph">`;
            } else {
                imgContainer.innerHTML = `<p class="text-danger">❌ ${data.error || 'Error loading analysis graph.'}</p>`;
            }

            if (data.ai_insights) {
                let formatted = data.ai_insights
                    .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')  // bold
                    .replace(/\n/g, '<br>');                 // linebreaks

                chatbotContainer.innerHTML = formatted;
            } else {
                chatbotContainer.innerHTML = "<p class='text-warning'>❌ No AI insights generated.</p>";
            }
        })
        .catch(err => {
            console.error("Race analysis error:", err);
            imgContainer.innerHTML = `<p class="text-danger">❌ Failed to load analysis graph.</p>`;
            chatbotContainer.innerHTML = `<p class="text-danger">❌ Failed to generate AI insights.</p>`;
        });
}

// Export all data (lap data, player data, analysis, and coaching tips)
function exportAll() {
    Promise.all([
        fetch("/export").then(res => res.json()),
        fetch("/export-player-data").then(res => res.json()),
        fetch("/generate-live-analysis").then(res => res.json()),
        fetch("/coaching-tip").then(res => res.json())
    ])
    .then(([exportLapData, exportPlayerData, analysisData, coachingTipData]) => {
        alert(
            "✅ All data exported!\n" +
            exportLapData.message + "\n" +
            exportPlayerData.message + "\n" +
            (analysisData.saved_path ? `Analysis saved to ${analysisData.saved_path}` : "Analysis failed.") + "\n" +
            "Coaching tip saved."
        );

        // Optionally auto switch tab to 'data'
        showTab('data');

        // Optionally refresh Lap Data table view
        fetch(exportLapData.view_url)
            .then(res => res.text())
            .then(csv => {
                const rows = csv.trim().split("\n").map(r => r.split(","));
                const table = document.createElement("table");
                table.className = "table table-striped table-dark text-center";

                const thead = document.createElement("thead");
                thead.innerHTML = "<tr>" + rows[0].map(h => `<th>${h}</th>`).join("") + "</tr>";
                table.appendChild(thead);

                const tbody = document.createElement("tbody");
                for (let i = 1; i < rows.length; i++) {
                    const row = document.createElement("tr");
                    row.innerHTML = rows[i].map(cell => `<td>${cell}</td>`).join("");
                    tbody.appendChild(row);
                }
                table.appendChild(tbody);

                const container = document.getElementById("lap-data-table-container");
                container.innerHTML = "";
                container.appendChild(table);
            })
            .catch(err => {
                console.error("❌ Failed to reload CSV after export:", err);
                document.getElementById("lap-data-table-container").innerHTML = "<p class='text-danger'>❌ Failed to load exported data.</p>";
            });
    })
    .catch(err => {
        console.error("❌ Error exporting all data:", err);
        alert("❌ Failed to export all data.");
    });
}

// WebSocket error handler
socket.onerror = (event) => {
    console.error("❌ WebSocket error:", event);
};

// WebSocket connection closed handler
socket.onclose = (event) => {
    console.warn("⚠️ WebSocket connection closed:", event);
};
