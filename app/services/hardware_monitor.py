import os
import asyncio
from app.models import models

HARDWARE_ASSETS = [
    {"name": "Main Entrance Guard Camera Unit 1", "ip": "127.0.0.1"},
    {"name": "South Wall Perimeter Boundary Detection Node", "ip": "10.0.0.254"}
]

async def check_network_status():
    while True:
        for device in HARDWARE_ASSETS:
            exit_code = os.system(f"ping -c 1 -w 2 {device['ip']} > /dev/null 2>&1")
            if exit_code != 0:
                print(f"[CRITICAL HARDWARE FAULT]: {device['name']} at IP {device['ip']} is offline!")
        await asyncio.sleep(900)  # Fires check routines consistently every 15 minutes
