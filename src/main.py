import asyncio
from bot import run

def loop():
    while True:
        print("New loop iteration")
        try:
            run()
        except:
            asyncio.set_event_loop(asyncio.new_event_loop())

print("[Main] Launching")

loop()
