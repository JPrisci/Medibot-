# Unified study navigation

Status: offline route comparisons and Python syntax checks passed.
Physical robot and Coordinator integration testing remain pending.
The shared Bash launcher still needs validation on Linux.

## Shared entry points
- scripts/navigation_bridge.py
- scripts/gblock_route_runner.py
- scripts/start_navigation.sh

Robot settings are selected from config/robots/jarvis.json or gem.json.
Both profiles retain the study routes. Driving speed remains 0.30 m/s.
Gem retains its starting roll and calibrated first-edge adjustment.

## On the matching Pi
Check prerequisites:
bash scripts/start_navigation.sh jarvis --check
bash scripts/start_navigation.sh gem --check

After confirming physical placement and stopping competing controllers,
use --run instead of --check on the matching robot.

Gem readiness reporting assumes physical staging; it is not localisation.
Coordinator, interface and face processes must be started separately.

## Before merging into main
1. Compare this branch with any uncommitted changes on both Pis.
2. Validate the launcher and ROS/USB setup on each Pi.
3. Test each study route, final turn, abort and process cleanup.
4. Test the complete Coordinator/Jarvis/Gem handover.
5. Retire the legacy specialised launchers after successful testing.

The original study branches remain the reference versions.
Keep the working NerdFest installation unchanged during preparation.
