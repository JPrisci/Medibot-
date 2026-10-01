#!/usr/bin/env bash
# Jarvis only. Default: check configuration, without starting any ROS node.
# --run explicitly starts the existing Colin-route bridge after confirmation.
# No network configuration, ROS startup files, maps or bridge files are changed.
set -eo pipefail

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

if [[ $# -gt 1 ]]; then
    fail 'Use --check (default), --help, or --run.'
fi
mode=${1:---check}
case "$mode" in
    --help|-h)
        printf '%s\n' \
            'Usage: bash start_jarvis_usb.sh [--check | --run]' \
            'Default --check: validates local prerequisites and USB ping only.' \
            '--run: starts the REAL-ROBOT bridge after a typed confirmation.' \
            'A pending Coordinator command can cause movement immediately.' \
            'Uses the existing Colin-start bridge; it does not auto-start at boot.'
        exit 0
        ;;
    --check|--run) ;;
    *) fail "Unknown option: $mode" ;;
esac

[[ $(id -un) == jarvis ]] || fail 'Run this as jarvis on jarvis-pi, not on Gem or the Coordinator.'
[[ $(hostname) == jarvis-pi ]] || fail 'This launcher is specifically for jarvis-pi.'

repo=/home/jarvis/medibot-integration
bridge="$repo/scripts/navigation_bridge_colin_usb_test.py"
study_map="$repo/config/gblock_colin_study_map.json"
for required_file in \
    /opt/ros/jazzy/setup.bash \
    /home/jarvis/medibot_ws/install/setup.bash \
    "$bridge" "$repo/scripts/gblock_route_runner.py" "$study_map"; do
    [[ -r "$required_file" ]] || fail "Missing or unreadable file: $required_file"
done

systemctl is-enabled --quiet medibot-create3-usb.service || fail 'USB boot service is not enabled. No changes made.'
systemctl is-active --quiet medibot-create3-usb.service || fail 'USB boot service is not active. No changes made.'
ip -o -4 addr show dev usb0 | grep -Eq 'inet 192\.168\.186\.3/24([[:space:]]|$)' || fail 'usb0 does not have the expected USB address.'
ip -o -4 addr show dev wlan0 | grep -q ' inet ' || fail 'wlan0 has no IPv4 address.'
ping -c 1 -W 2 -I usb0 192.168.186.2 >/dev/null || fail 'Create 3 did not answer the USB ping.'

# Avoid nounset: ROS setup scripts may legitimately reference unset variables.
source /opt/ros/jazzy/setup.bash
source /home/jarvis/medibot_ws/install/setup.bash
export ROS_DOMAIN_ID=0
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
unset ROS_LOCALHOST_ONLY ROS_STATIC_PEERS

# Parent bridge: Wi-Fi discovery. The reviewed bridge sets its child's
# CYCLONEDDS_URI separately to usb0 with peer 192.168.186.2.
export CYCLONEDDS_URI='<CycloneDDS><Domain><General><Interfaces><NetworkInterface name="wlan0" /></Interfaces><AllowMulticast>true</AllowMulticast></General></Domain></CycloneDDS>'
ros2 pkg prefix rmw_cyclonedds_cpp >/dev/null || fail 'Cyclone DDS ROS middleware package is unavailable.'

printf '%s\n' \
    'Local prerequisites and USB ping: PASS' \
    'Parent bridge interface: wlan0 (Wi-Fi)' \
    'Child runner USB selection: supplied by the existing Colin bridge' \
    'Jarvis route start: G1.11; map: gblock_colin_study_map.json' \
    'This does NOT verify Coordinator discovery, hazard delivery, or route safety.'

if [[ "$mode" == --check ]]; then
    printf '%s\n' 'CHECK ONLY: no bridge or route runner was started; no settings were saved or changed.'
    exit 0
fi

[[ -t 0 ]] || fail '--run requires an attended foreground terminal.'
printf '%s\n' \
    'REAL-ROBOT MODE: a Coordinator command can start movement immediately.' \
    'Only continue after the supervised preflight, with Jarvis correctly placed' \
    'and oriented at G1.11, the route clear, and a stop method available.'
read -r -p 'Type START JARVIS to start the bridge: ' confirmation
[[ "$confirmation" == 'START JARVIS' ]] || fail 'Start cancelled.'

# Catch existing direct launches too. This is a check, not a safety interlock;
# do not launch another controller or bridge concurrently.
if pgrep -af '[n]avigation_bridge.*\.py|[g]block_route_runner.*\.py'; then
    fail 'An existing bridge or route runner was found. Do not start a duplicate.'
fi

cd "$repo"
exec python3 -u "$bridge" --robot jarvis --run
