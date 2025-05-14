# AI Driving Coach on Edge

**COM3610 Dissertation Project**  
**AI Driving Coach on Edge**  
**Author:** Weixiang Han (Ray)
**Date:** 14 May 2025  

---

## Overview

The **AI Coach App** is a real-time telemetry analysis and coaching tool designed for drivers that want to improve their lap performance. It processes telemetry data from the PlayStation F1 24 game, compares it with reference data, and provides actionable insights to improve driving performance. The app leverages FastAPI for the backend, FastF1 library for telemetry referencing, and an AI model for generating coaching tips and analysis.

The app is built over pits-n-giggles repo, special thanks to Ashwin Natarajan for making the amazing tool public. 

---

## Features

- **Real-Time Telemetry Recording**: Captures and processes telemetry data such as speed, throttle, brake, and sector times.
- **Lap Analysis**: Compares player laps with reference laps to identify areas for improvement.
- **AI-Driven Coaching Tips**: Uses an AI model to generate personalized coaching tips based on telemetry data.
- **Live WebSocket Updates**: Sends live telemetry data to the frontend for visualization.
- **Data Export**: Exports lap telemetry and player data to CSV files for further analysis.
- **Graph-Based Insights**: Generates visual comparisons of laps and provides AI insights.

---
## Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/rayisa0904/com3610-ai-coach-app.git
    ```
2. Navigate to the project directory:
    ```bash
    cd ai-coach-app
    ```
3. Install dependencies:
    ```bash
    npm install
    ```

## Usage

1. Start the development server:
    ```bash
    npm start
    ```
2. Open your browser and navigate to `http://localhost:3000` (edit to your local host).


## Contact

For questions or feedback, please contact [whan5@sheffield.ac.uk] or [hanweixiang@gmail.com].