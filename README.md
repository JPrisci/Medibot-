# medibot

A new Flutter project.

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Learn Flutter](https://docs.flutter.dev/get-started/learn-flutter)
- [Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Flutter learning resources](https://docs.flutter.dev/reference/learning-resources)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.

## Route request API

On confirmation, the app posts this JSON to `POST /route-requests`:

```json
{"destination":"DIGITAL_LIBRARY","user_id":"[Entered by user at the start of kiosk session]"}
```

Start the included API on the robot:

```powershell
python route_api.py
```

Can retrieve all requests with `GET /route-requests`, or only
the newest with `GET /route-requests/latest`. The API listens on port 8000.
When the Flutter app runs on a different machine, point it at that machine's
LAN IP when launching it:

```powershell
flutter run --dart-define=ROUTE_API_URL=http://YOUR_API_MACHINE_IP:8000/route-requests
```
