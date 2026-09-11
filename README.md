# NaviBot Flutter App

The NaviBot Flutter app has the user book a route, and then the
app sends the request to the NaviBot Coordinator.

The Coordinator receives the request and handles the robot side of the route.
The Flutter app does not control the robots directly.

## Connection flow

```text
Flutter tablet app
    -> HTTP request
Coordinator API on port 8000
```

When the visitor confirms the route in the app, Flutter sends:

```text
POST /route-requests
```

```json
{
  "destination": "DIGITAL_LIBRARY",
  "user_id": "visitor_001"
}
```

The request is made in:

```text
lib/screens/search_by_map_page.dart
```

At the start screen, the visitor enters their name. The app stores that value
in `SessionTracker.userId` and sends it to the API in the `user_id` field with
the selected destination after the user presses **Confirm booking** and
confirms again in the dialog.

## API address

For the normal tablet setup, `ROUTE_API_URL` should point to the Coordinator
Pi, which is on another device on the same Wi-Fi network. The value is passed
into Flutter when the APK is built:

```text
http://<COORDINATOR_PI_IP>:8000/route-requests
```

The app reads that value with:

```dart
const _routeApiUrl = String.fromEnvironment(
  'ROUTE_API_URL',
  defaultValue: 'http://localhost:8000/route-requests',
);
```

The `localhost` value is only a fallback for local development, where Flutter
and the API are running on the same computer. It is not the normal tablet
setup.

## Building the tablet app

Build the Android APK with the Coordinator Pi address:

```powershell
flutter build apk --release `
  --dart-define=ROUTE_API_URL=http://<COORDINATOR_PI_IP>:8000/route-requests
```

Example:

```powershell
flutter build apk --release `
  --dart-define=ROUTE_API_URL=http://192.168.1.50:8000/route-requests
```

## API endpoints

The relevant endpoints for Flutter are:

- `POST /route-requests` - starts the visitor task and Jarvis's first route.
- `GET /ux-state/latest` - reads the current visitor-task state.
- `POST /visitor-ready` - starts Gem's final route after handover.
- `POST /task-reset` - clears the task for the next visitor.

The current Flutter booking page uses `POST /route-requests`.

## Current two-robot flow

The Flutter tablet sends the booking request, polls for `task_complete`, and
sends the reset request for the next participant. `Faces/faces.py` handles the
elevator handover and sends `POST /visitor-ready` when the visitor is ready to
continue with Gem. Keep those responsibilities separate unless the Controller
API and both clients are changed together.
