# MediBot study navigation

This folder contains the navigation implementation for the Gem and Jarvis

iRobot Create 3 robots used in the MediBot G Block study.

The supplied configuration is calibrated for the study robots, their

starting positions and the measured G Block routes. Adapting it to another

robot or location requires reviewing the settings described below.

## 1. Requirements

Each robot uses the following setup.

- An iRobot Create 3 base connected to its Raspberry Pi over USB Ethernet.

- Ubuntu 24.04 with ROS 2 Jazzy.

- CycloneDDS through `rmw_cyclonedds_cpp`.

- The Python packages `rclpy`, `std_msgs` and `irobot_create_msgs`.

- A working ROS overlay at `~/medibot_ws/install/setup.bash`.

- Wi-Fi connectivity to the Coordinator when using integrated operation.

The study deployment also uses an existing

`medibot-create3-usb.service` systemd service to configure the USB link.

Its installation is separate from this folder.

Use the official ROS installation instructions when preparing a new

computer. Verify that the Create 3 firmware and ROS interfaces are

compatible with the chosen ROS distribution.

- [ROS 2 Jazzy installation](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html)

- [Create 3 configuration](https://iroboteducation.github.io/create3_docs/setup/multi-robot/)

- [Create 3 ROS interfaces](https://iroboteducation.github.io/create3_docs/api/ros2/)

## 2. Get the code and open the navigation folder

Clone the repository if a checkout is not already available.

```bash
git clone https://github.com/JPrisci/Medibot-.git ~/Medibot-
cd ~/Medibot-/navigation
```

For a private repository, authenticate using your own Git credentials or

transfer a repository archive from your laptop.

All following commands assume the current directory is `navigation`.

Use the actual checkout path if it differs from `~/Medibot-`.

There is no navigation package build step. The scripts run directly

against an existing ROS installation and overlay.

## 3. Identify the correct robot and profile

| Setting | Jarvis | Gem |
| --- | --- | --- |
| Linux account | `jarvis` | `gem` |
| Hostname | `jarvis-pi` | `gem-desktop` |
| Profile | `config/robots/jarvis.json` | `config/robots/gem.json` |
| Create 3 namespace | `/jarvis` | `/gem` |
| Start node | `JARVIS_PARKED` | `LEVEL2_ELEVATOR` |
| Map | `config/gblock_colin_study_map.json` | `config/gem_study_map.json` |
| Study destination | `ELEVATOR_2` | `DIGITAL_LIBRARY` |
| Map starting heading | 0 degrees | 180 degrees |

The starting heading is measured relative to the study map. It is not a

compass bearing.

The profile namespace must match the namespace configured on the actual

Create 3 base.

## 4. Check the computer and network

On the matching robot computer, run the following commands.

```bash
hostname
id -un
ip -br -4 addr
systemctl is-active medibot-create3-usb.service
ping -c 1 -W 2 -I usb0 192.168.186.2
```

The supplied launcher expects these network settings.

| Connection | Expected setting |
| --- | --- |
| Computer Wi-Fi interface | `wlan0` |
| Computer USB interface | `usb0` |
| Computer USB address | `192.168.186.3/24` |
| Create 3 USB address | `192.168.186.2` |
| ROS domain | `0` |
| ROS middleware | `rmw_cyclonedds_cpp` |

Both robots can use the same USB addresses because each base has its own

physically separate USB connection.

Wi-Fi DHCP addresses can change. Use `ip -br -4 addr show wlan0` to obtain

the current address. Use that Wi-Fi address for SSH if `.local` hostname

resolution fails.

The bridge communicates over Wi-Fi. Its route-runner subprocess uses

the USB CycloneDDS XML stored in the selected profile.

## 5. Check ROS prerequisites

Source the base installation and the study overlay.

```bash
source /opt/ros/jazzy/setup.bash
source ~/medibot_ws/install/setup.bash
ros2 pkg prefix rmw_cyclonedds_cpp
python3 -c 'import rclpy; from std_msgs.msg import String; from irobot_create_msgs.action import RotateAngle, DriveDistance, WallFollow'
```

If the overlay is installed somewhere else, set its location before

running the launcher.

```bash
export MEDIBOT_ROS_SETUP=/absolute/path/to/install/setup.bash
```

If all required interfaces are supplied by the base ROS installation,

that setup file can also be used as the overlay.

```bash
export MEDIBOT_ROS_SETUP=/opt/ros/jazzy/setup.bash
```

## 6. Run the prerequisite check

On Jarvis, run the following command.

```bash
bash scripts/start_navigation.sh jarvis --check
```

On Gem, use the following command.

```bash
bash scripts/start_navigation.sh gem --check
```

The launcher checks the account, hostname, profile, start node, setup

files, USB service, network addresses, base ping and required ROS imports.

A successful check prints `Local prerequisites PASS`.

This check does not establish physical position or verify that a complete

route will succeed. Action-server discovery and sensor behaviour must

also be checked during supervised testing.

## 7. Preview the study route

Source ROS as shown in step 5. Preview the route on the matching robot

without adding `--run`.

For Jarvis, run the following command.

```bash
python3 scripts/gblock_route_runner.py \
  --namespace /jarvis \
  --map-file config/gblock_colin_study_map.json \
  --start-node JARVIS_PARKED \
  --destination ELEVATOR_2
```

For Gem, run the following command.

```bash
python3 scripts/gblock_route_runner.py \
  --namespace /gem \
  --map-file config/gem_study_map.json \
  --start-node LEVEL2_ELEVATOR \
  --destination DIGITAL_LIBRARY
```

Check the printed path, distances and turns against the intended study

route before proceeding.

## 8. Position the robot and start the real bridge

Place the robot at its calibrated start and heading. Clear the route,

stop competing navigation processes and keep the physical stop available.

Ensure the Coordinator is idle before starting the bridge. A pending

route command can start movement as soon as the bridge receives it.

Start Jarvis with the following command.

```bash
bash scripts/start_navigation.sh jarvis --run
```

Enter `START jarvis` at the confirmation prompt.

For Gem, run the following command and enter `START gem`.

```bash
bash scripts/start_navigation.sh gem --run
```

Leave the terminal open to observe navigation logs.

Starting Gem in real mode automatically reports receiving-point

readiness after five seconds. This assumes Gem was physically staged at

`LEVEL2_ELEVATOR`. The bridge also reports readiness for new tasks based

on UX state updates. It does not measure or verify Gem's location.

Before each new task, confirm the robot has been returned to its expected

start and heading. A task reset does not physically reposition a robot.

## 9. Request a supervised test route

For normal integrated operation, the Coordinator publishes route

commands. Its startup instructions belong to the communication component.

For a standalone test, open a second terminal on the matching robot and

prepare the same Wi-Fi ROS environment.

```bash
source /opt/ros/jazzy/setup.bash
source "${MEDIBOT_ROS_SETUP:-$HOME/medibot_ws/install/setup.bash}"
export ROS_DOMAIN_ID=0
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
unset ROS_LOCALHOST_ONLY ROS_STATIC_PEERS
export CYCLONEDDS_URI='<CycloneDDS><Domain><General><Interfaces><NetworkInterface name="wlan0" /></Interfaces><AllowMulticast>true</AllowMulticast></General></Domain></CycloneDDS>'
```

Check that the relevant bridge appears as a subscriber.

```bash
ros2 topic info -v /medibot/jarvis/navigation_command
```

Use `/medibot/gem/navigation_command` when testing Gem.

The following commands cause movement when the bridge is in real mode.

Send only the command for the robot being supervised.

Jarvis route request.

```bash
ros2 topic pub --once -w 1 /medibot/jarvis/navigation_command std_msgs/msg/String \
  'data: "{\"command\":\"start_route\",\"destination\":\"ELEVATOR_2\"}"'
```

Gem route request.

```bash
ros2 topic pub --once -w 1 /medibot/gem/navigation_command std_msgs/msg/String \
  'data: "{\"command\":\"start_route\",\"destination\":\"DIGITAL_LIBRARY\"}"'
```

Use a single command source during testing. Wait for the route result

before sending another request.

## 10. Observe results and stop

Watch the bridge terminal or inspect navigation events from another

terminal with the Wi-Fi ROS environment from step 9.

```bash
ros2 topic echo /medibot/navigation_event std_msgs/msg/String
```

| Result | Published event |
| --- | --- |
| Jarvis completes `ELEVATOR_2` | `arrived_at_transfer_point` |
| Gem reports staged readiness | `arrived_at_receiving_point` |
| Gem completes `DIGITAL_LIBRARY` | `arrived_at_destination` |
| Route runner fails | `route_failed` |
| Route runner returns its abort result | `route_aborted` |

Events contain `robot_name`, `navigation_event` and `destination`.

Interruption events also include a reason.

While a real route is active, its status page is available at

`http://ROBOT_WIFI_IP:8081`. Obtain the current Wi-Fi IP from step 4.

To request an abort from the robot computer, use the following command.

```bash
curl --max-time 2 http://127.0.0.1:8081/abort
```

Use the physical stop if the robot does not stop promptly. Press Ctrl+C

in the bridge terminal to shut the bridge down. Confirm the base has

stopped before leaving it.

After an abort, failure or successful route, inspect the robot's position

and physically restage it before another route. The bridge continues to

use the profile's configured start node for subsequent requests.

## 11. Adapt the implementation to another robot

The existing launcher and bridge explicitly support the identities

`jarvis` and `gem`. The base namespace is configurable through JSON, but

several deployment and role settings are still in Python and Bash.

To use a different base while retaining a study identity, keep the

chosen profile filename and bridge role, then adapt the following items.

| What changes | Where to edit |
| --- | --- |
| Base namespace | `namespace` in the selected robot JSON, plus the actual Create 3 configuration |
| Physical start | `start_node` in the selected robot JSON |
| Study map | `map_file` in the selected robot JSON |
| USB DDS interface and base address | `runner_dds_xml` in the selected robot JSON |
| Required Linux account | `id -un` check in `scripts/start_navigation.sh` |
| Required hostname | Robot-selection `case` in `scripts/start_navigation.sh` |
| USB service, interface, computer address and ping target | Prerequisite checks in `scripts/start_navigation.sh` |
| Wi-Fi DDS interface and ROS domain | Environment exports in `scripts/start_navigation.sh` and command terminals |

For a completely new robot identity, also review these bridge sections.

- `main()` restricts `--robot` to `jarvis` and `gem`.

- The profile filename and command topic are derived from that identity.

- Startup readiness and `receive_ux_state()` explicitly select Gem.

- `handle_receiving_ready()` uses Gem and `LEVEL2_ELEVATOR`.

- `publish_success_event()` maps Jarvis and Gem to their study destinations.

- The external Coordinator must agree on the identity, command topic and events.

Changing a namespace alone does not implement a new communication role.

## 12. Adapt the route to another location

The JSON maps define nodes, enabled corridor edges, measured distances

and headings. The robot must begin at a known physical start because

the controller does not localise itself in a building map.

The supplied runner also contains study-specific geometric rules in

`build_topological_route_steps()`.

- The `LEVEL2_ELEVATOR` to `DIGITAL_LIBRARY` route starts with a 0.10 m

  roll at 0.05 m/s.

- That route expects its first mapped edge to be 7.40 m at 0 degrees

  and applies a calibrated distance of 7.50 m.

- Its map starting heading must be 180 degrees.

- Arrivals at `ELEVATOR_2` and `DIGITAL_LIBRARY` include a 180-degree turn.

Review these rules when changing the map or reusing the same node IDs.

Ordinary guarded driving uses 0.30 m/s.

Measure and test new geometry under supervision. Reusing the study

configuration in another location does not establish valid distances,

turns or clearance.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| SSH hostname cannot resolve | Use the current Wi-Fi IP shown on the robot |
| Wrong user or hostname | Check the launcher identity checks |
| Missing setup file | Check `MEDIBOT_ROS_SETUP` and the ROS installation |
| USB check fails | Inspect the service, cable, interface, addresses and base ping |
| Unknown command topic | Check bridge startup, ROS domain, Wi-Fi DDS settings and discovery |
| Action servers unavailable | Check the actual base namespace, domain and USB DDS settings |
| Obstacle detected at start | Inspect physical clearance, bumper and IR readings before retrying |
| Unexpected route | Check the selected profile, start node, map and destination |
| No arrival event after another destination | Review `publish_success_event()` mappings |
| Gem reports readiness in the wrong position | Physically restage it before starting or resetting a task |

## Verification status

The earlier shared layout passed prerequisite checks on both study Pis.

Jarvis accepted a route request and planned the expected Elevator 2 path.

The supervised Jarvis run stopped during obstacle recovery on the first

segment after bumper contact. The complete physical route and full live

handover remain unverified for this consolidated version.

Mock Coordinator tests were performed separately. They do not establish

successful physical navigation or cross-computer ROS discovery.
