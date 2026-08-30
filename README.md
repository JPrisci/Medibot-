# MediBot Flutter App

This tablet app lets a visitor choose a route and confirm a booking. It then
sends the route request to the MediBot Coordinator.

## What Flutter sends

After the visitor enters their name and confirms the route, the app sends:

```json
{
  "destination": "DIGITAL_LIBRARY",
  "user_id": "visitor_001"
}
```

to:

```text
POST /route-requests
```

The request is in `lib/screens/search_by_map_page.dart`. The name entered on
the start screen is stored as `SessionTracker.userId` and sent as `user_id`.

## Building for the tablet

The tablet must use the Coordinator Pi address, not `localhost`.

```powershell
flutter build apk --release `
  --dart-define=ROUTE_API_URL=http://10.11.29.155:8000/route-requests
```

Install the APK on the tablet. The tablet and Coordinator Pi must be on the
same Wi-Fi network. The Pi needs a stable IP address.

After a booking starts, the tablet waits for the Coordinator to report
`task_complete`. The **Start Again** button stays grey while the route is in
progress. Once it becomes available, it sends `POST /task-reset` before
returning to the main menu for the next participant.

## Testing with an Android emulator

Start the local test API on the computer running the emulator:

```powershell
python route_api.py
```

Then run Flutter with Android's special address for the host computer:

```powershell
flutter run --dart-define=ROUTE_API_URL=http://10.0.2.2:8000/route-requests
```

Complete a booking in the emulator. A successful request moves the app to
**Route in Progress** and the terminal running `route_api.py` shows a `201`
response.

`10.0.2.2` is the Android emulator address for the computer running it. Do not
use `localhost` from the emulator.

For a real Controller test, use:

```powershell
flutter run --dart-define=ROUTE_API_URL=http://10.11.29.155:8000/route-requests
```

Only use the real Controller when the robot team says it is safe, because the
request can start a real route. The local `route_api.py` test only checks the
initial booking request, so **Start Again** remains grey. Testing task
completion and reset requires the real Controller API.

## Local testing

`route_api.py` is a simple local test server for testing the Flutter booking
request without the full robot system:

```powershell
python route_api.py
```

For the real demo, the Flutter app sends requests to the Coordinator API.
