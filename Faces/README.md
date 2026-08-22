# Robot Face Screens

`faces.py` runs the screen shown on each robot during the handover.
It starts on a white **Idle** screen and switches to the robot face after the
Coordinator accepts a visitor booking.

## Run on the robots

Run this on Jarvis's screen:

```bash
python3 faces.py --role jarvis --api-base-url http://<COORDINATOR_PI_IP>:8000
```

Run this on Gem's screen:

```bash
python3 faces.py --role gem --api-base-url http://<COORDINATOR_PI_IP>:8000
```

When handover is ready, Jarvis tells the visitor to enter the elevator. Gem
shows a Continue button. Tapping Gem's button sends the visitor-ready request
to the Coordinator so Gem can continue the route.

## Test without robots

Install pygame:

```powershell
python -m pip install pygame
```

Test the screens only:

```powershell
python faces.py --role jarvis --demo-handover
python faces.py --role gem --demo-handover
```

To test Gem's HTTP request as well, start the local mock in one terminal:

```powershell
python mock_coordinator.py
```

Then run Gem in another terminal:

```powershell
python faces.py --role gem --api-base-url http://127.0.0.1:8000
```
