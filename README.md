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

When the user confirms a booking, the app sends this request to
`POST /route-requests`:

```json
{"destination":"DIGITAL_LIBRARY","user_id":"[Entered by user at the start of kiosk session]"}
```

The included API stores requests in memory while it is running. It provides:

- `POST /route-requests` to submit a route request.
- `GET /route-requests` to retrieve all requests received since the API started.
- `GET /route-requests/latest` to retrieve the newest request.

### Start and test the API

In a PowerShell terminal, start the API and leave the terminal open:

```powershell
cd C:\Users\jacku\Capstone\medibot
py route_api.py
```

It should print:

```text
Route API listening on http://0.0.0.0:8000/route-requests
```

To test the API without the Flutter app, run this in another PowerShell
terminal:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/route-requests `
  -ContentType 'application/json' `
  -Body '{"destination":"DIGITAL_LIBRARY","user_id":"test-user"}'

Invoke-RestMethod http://localhost:8000/route-requests/latest
```

A successful request is logged by the API with status `201`, for example:

```text
127.0.0.1 - "POST /route-requests HTTP/1.1" 201 -
```

### Confirming a booking in the app

The request is only sent after a route is active and the user presses both
confirmation buttons:

1. Select the Room 2.31 destination marker to make the route active.
2. Press **Confirm booking**.
3. In the dialog, press **Confirm**.

The app returns to the session summary after a successful `201` response.

### Run on Windows desktop

When the Flutter app and API run on the same Windows computer, the default
`localhost` API address works:

```powershell
flutter run -d windows
```

### Run on an Android emulator

`localhost` inside an Android emulator refers to the emulator, not the host
computer. Use Android's special host address, `10.0.2.2`:

```powershell
flutter run --dart-define=ROUTE_API_URL=http://10.0.2.2:8000/route-requests
```

The Android manifest permits local HTTP connections for this prototype. Fully
stop and restart the Flutter app after changing the `--dart-define` value;
hot reload does not apply it.

### Run on a physical Android tablet

1. Connect the tablet and API computer to the same Wi-Fi network.
2. Start the API on the computer with `py route_api.py`.
3. Run `ipconfig` and find the IPv4 address of the computer's active Wi-Fi
   adapter, for example `192.168.1.20`.
4. Launch the app using that LAN address:

```powershell
flutter run --dart-define=ROUTE_API_URL=http://192.168.1.20:8000/route-requests
```

If Windows Firewall asks, allow Python network access on **Private networks**.

### Google Chrome testing

Chrome is supported for local testing. Start the API with `py route_api.py`,
then run:

```powershell
flutter run -d chrome
```

The default `localhost` URL works when Chrome and the API run on the same
computer. The API includes the CORS headers required for browser requests.
