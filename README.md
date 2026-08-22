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
  --dart-define=ROUTE_API_URL=http://<COORDINATOR_PI_IP>:8000/route-requests
```

Install the APK on the tablet. The tablet and Coordinator Pi must be on the
same Wi-Fi network. The Pi needs a stable IP address.

## Local testing

`route_api.py` is a simple local test server for testing the Flutter booking
request without the full robot system:

```powershell
python route_api.py
```

For the real demo, the Flutter app sends requests to the Coordinator API.
