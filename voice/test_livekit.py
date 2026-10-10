import sys
import os
import time

# Add the A.V.I project root to Python's path
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from voice.livekit_client import AVILiveKitClient


avi = AVILiveKitClient()

avi.start()

print()
print("=" * 40)
print("       A.V.I LIVEKIT TEST")
print("=" * 40)
print()
print("LiveKit voice client starting...")
print("Press CTRL+C to stop.")
print()

try:
    while True:
        time.sleep(1)

except KeyboardInterrupt:

    print()
    print("[A.V.I] Shutting down...")

    avi.stop()

    time.sleep(1)

    print("[A.V.I] Voice client stopped.")