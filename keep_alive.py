from flask import Flask
from threading import Thread
import time

app = Flask('')

@app.route('/')
def home():
    return "Welcome Bot is running! 🤖"

@app.route('/status')
def status():
    return {
        "status": "online",
        "timestamp": time.time(),
        "message": "Bot is healthy and running!"
    }

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
