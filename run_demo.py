"""
All-in-One Demo Launcher for SIH26124 Urban Intelligence Platform.
Automatically starts FastAPI (8000), Node Gateway (5000), Vite Frontend (3000),
and Cloudflare HTTPS Tunnel for instant phone camera & GPS connection.
"""

import os
import sys
import time
import subprocess
import threading
import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
os.chdir(ROOT_DIR)

processes = []


def kill_all():
    print("\n[Launcher] Shutting down all services...")
    for p in processes:
        try:
            p.terminate()
            p.kill()
        except Exception:
            pass
    print("[Launcher] All services stopped.")


def main():
    print("==================================================================")
    print("  SIH26124 — AI-POWERED URBAN INTELLIGENCE PLATFORM (D-FINE)")
    print("  Starting all services: AI Engine, Gateway, Web GIS, & Mobile PWA")
    print("==================================================================\n")

    # 1. Start FastAPI AI Service (port 8000)
    print("[1/4] Starting FastAPI AI & D-FINE Fusion Service on port 8000...")
    fastapi_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.ai_service.main:app", "--port", "8000", "--host", "0.0.0.0", "--reload"],
        cwd=str(ROOT_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    processes.append(fastapi_proc)
    time.sleep(1.5)

    # 2. Start Node Gateway (port 5000)
    print("[2/4] Starting Node.js API Gateway & WebSocket Server on port 5000...")
    gateway_proc = subprocess.Popen(
        ["node", "server.js"],
        cwd=str(ROOT_DIR / "backend" / "gateway"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=True
    )
    processes.append(gateway_proc)
    time.sleep(1.5)

    # 3. Start React GIS Frontend (port 3000)
    print("[3/4] Starting React 18 GIS Command Center on port 3000...")
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(ROOT_DIR / "frontend"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=True
    )
    processes.append(frontend_proc)
    time.sleep(1.5)

    # 4. Start Cloudflare Tunnel for Phone Camera HTTPS
    tunnel_url = None
    cloudflared_bin = ROOT_DIR / "cloudflared.exe"
    if cloudflared_bin.exists():
        print("[4/4] Starting Cloudflare HTTPS Tunnel for Mobile Phone Camera...")
        tunnel_proc = subprocess.Popen(
            [
                str(cloudflared_bin), "tunnel",
                "--url", "http://localhost:5000",
                "--ha-connections", "4",
                "--protocol", "quic",
                "--edge-ip-version", "auto"
            ],
            cwd=str(ROOT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        processes.append(tunnel_proc)

        # Read tunnel output to extract trycloudflare URL
        start_wait = time.time()
        while time.time() - start_wait < 10:
            line = tunnel_proc.stdout.readline()
            if line:
                match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
                if match:
                    tunnel_url = match.group(0)
                    break
            time.sleep(0.1)

    print("\n==================================================================")
    print("  🚀 PLATFORM IS FULLY OPERATIONAL!")
    print("==================================================================")
    print("  💻 GIS Command Center:    http://localhost:3000")
    print("  ⚙️  AI REST API & Docs:    http://localhost:8000/docs")
    if tunnel_url:
        print(f"  📱 Phone Camera PWA:      {tunnel_url}/pwa/?device_id=BUS_LIVE_01")
    else:
        print("  📱 Local Wi-Fi PWA:       http://localhost:5000/pwa/?device_id=BUS_LIVE_01")
    print("==================================================================")
    print("  • Open the Phone Camera PWA link on your mobile browser.")
    print("  • Tap 'START SENSING' to stream your live phone camera to the map!")
    print("  • Live YOLO neural perception runs in real-time directly on camera frames.")
    print("==================================================================")
    print("\nCommands:")
    print("  [r] Run automated multi-bus corroboration replay simulation")
    print("  [q] Quit and stop all servers\n")

    try:
        while True:
            cmd = input("Command [r: Replay, q: Quit] > ").strip().lower()
            if cmd == "r":
                print("\n[Simulation] Running 3-bus corroboration replay...")
                subprocess.run(
                    [sys.executable, "replay_engine/player.py", "--multi", "--speed", "2.0"],
                    cwd=str(ROOT_DIR)
                )
            elif cmd == "q":
                break
    except KeyboardInterrupt:
        pass
    finally:
        kill_all()


if __name__ == "__main__":
    main()
