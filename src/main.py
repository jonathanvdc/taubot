from bot import run

def loop():
    while True:
        print("New loop iteration")
        try:
            run()
        except:
            pass

print("[Main] Launching")

loop()
