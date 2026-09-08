"""
Continuous replay loop for live demo — keeps GIS map populated indefinitely.
Runs multi-bus corroboration replay in a loop with a 5s gap between cycles.
"""
import subprocess, sys, time

url = "http://127.0.0.1:8000"
speed = "1.5"
cycle = 0

print("=" * 60)
print("  LIVE DEMO REPLAY LOOP — Press Ctrl+C to stop")
print(f"  Target: {url}  |  Speed: {speed}x")
print("=" * 60)

while True:
    cycle += 1
    print(f"\n[Loop] Starting cycle #{cycle}...")
    subprocess.run(
        [sys.executable, "replay_engine/player.py", "--multi", "--speed", speed, "--url", url],
        check=False
    )
    print(f"[Loop] Cycle #{cycle} done. Waiting 5s before next cycle...")
    time.sleep(5)
