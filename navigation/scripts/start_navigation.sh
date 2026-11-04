#!/usr/bin/env bash
# Shared study launcher. Default: checks only.
set -eo pipefail

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

robot=${1:-}
mode=${2:---check}

case "$robot" in
    jarvis) expected_host=jarvis-pi ;;
    gem) expected_host=gem-desktop ;;
    *) fail 'Usage: bash scripts/start_navigation.sh jarvis|gem [--check|--run]' ;;
esac

[[ $# -le 2 ]] || fail 'Too many arguments'
case "$mode" in
    --check|--run) ;;
    *) fail 'Use --check or --run' ;;
esac

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
bridge="$repo/scripts/navigation_bridge.py"
profile="$repo/config/robots/$robot.json"
overlay=${MEDIBOT_ROS_SETUP:-"$HOME/medibot_ws/install/setup.bash"}

[[ $(id -un) == "$robot" ]] || fail "Run as $robot"
[[ $(hostname) == "$expected_host" ]] || fail "Expected host: $expected_host"

for file in /opt/ros/jazzy/setup.bash "$overlay" "$bridge" \
    "$profile" "$repo/scripts/gblock_route_runner.py"; do
    [[ -r "$file" ]] || fail "Missing file: $file"
done

python3 - "$repo" "$profile" <<'PY'
import json
import sys
from pathlib import Path
root = Path(sys.argv[1])
profile = json.loads(Path(sys.argv[2]).read_text())
data = json.loads((root / profile["map_file"]).read_text())
assert profile["start_node"] in data["nodes"], "Invalid start node"
print("Selected start:", profile["start_node"])
print("Selected map:", profile["map_file"])
PY

systemctl is-active --quiet medibot-create3-usb.service ||
    fail 'Existing USB service is not active'
ip -o -4 addr show dev usb0 |
    grep -Eq 'inet 192\.168\.186\.3/24([[:space:]]|$)' ||
    fail 'USB address is not 192.168.186.3/24'
ip -o -4 addr show dev wlan0 | grep -q ' inet ' ||
    fail 'Wi-Fi has no IPv4 address'
ping -c 1 -W 2 -I usb0 192.168.186.2 >/dev/null ||
    fail 'Create 3 did not answer USB ping'

source /opt/ros/jazzy/setup.bash
source "$overlay"

export ROS_DOMAIN_ID=0
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
unset ROS_LOCALHOST_ONLY ROS_STATIC_PEERS
export CYCLONEDDS_URI='<CycloneDDS><Domain><General><Interfaces><NetworkInterface name="wlan0" /></Interfaces><AllowMulticast>true</AllowMulticast></General></Domain></CycloneDDS>'

ros2 pkg prefix rmw_cyclonedds_cpp >/dev/null ||
    fail 'CycloneDDS is unavailable'
python3 -c 'import rclpy; from irobot_create_msgs.action import RotateAngle, DriveDistance, WallFollow' ||
    fail 'Required ROS Python packages are unavailable'

printf '%s\n' 'Local prerequisites PASS; physical navigation remains unverified.'
[[ "$mode" != --check ]] || exit 0

if pgrep -af '[n]avigation_bridge.*[.]py|[e]ds_navigation_bridge.*[.]py|[g]block_route_runner.*[.]py'; then
    fail 'Existing navigation process found'
fi

[[ -t 0 ]] || fail 'Real mode requires an attended terminal'
printf '%s\n' \
    "Confirm $robot is at its calibrated study start and heading." \
    'Keep the route clear and physical stop available.' \
    'A pending Coordinator command can cause movement immediately.'
read -r -p "Type START $robot: " confirmation
[[ "$confirmation" == "START $robot" ]] || fail 'Cancelled'

cd "$repo"
exec python3 -u "$bridge" --robot "$robot" --run
