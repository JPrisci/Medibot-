# NaviBot Face Screens

`faces.py` runs the screen shown on each robot during the handover.
It starts on a white **Idle** screen and switches to the robot face after the
Coordinator accepts a visitor booking.

## Run on the robots

Run this on Jarvis's screen:

```bash
python3 faces.py --role jarvis --api-base-url http://10.11.29.129:8000
```

Run this on Gem's screen:

```bash
python3 faces.py --role gem --api-base-url http://10.11.29.129:8000
```

When handover is ready, Jarvis tells the visitor to enter the elevator and press
the second-floor button. A second NaviBot, Gem, meets the visitor upstairs and
shows a **Ready to follow NaviBot?** button. Tapping Gem's button sends the visitor-ready request
to the Coordinator so Gem can continue the route.

When the Coordinator reports `task_complete`, the display shows an arrival message with a Confirm button.
It returns to Idle after the button is pressed or after ten seconds of inactivity.

## Error fallbacks

If the Coordinator cannot be reached, the face shows a reconnecting message
instead of a raw network exception and continues polling. After three failed
polls it also shows a non-functional **Call staff - we'll be with you shortly**
button. Both disappear automatically after the next successful poll.

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
