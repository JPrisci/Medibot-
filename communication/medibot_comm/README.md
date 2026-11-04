# MediBot Communication

ROS 2 communication and high-level task coordination component for the MediBot multi-robot visitor guidance project.

This package coordinates the visitor task between:

* the UX/tablet interface;
* Jarvis Pi;
* Gem Pi;
* the Navigation component; and
* the central Coordinator Raspberry Pi.

The Communication component is responsible for **high-level coordination**. It determines which robot should perform each guidance leg, tracks the visitor-task state, coordinates robot handover, and provides interfaces between UX and Navigation.

It does **not** perform physical path planning, odometry, obstacle avoidance, `cmd_vel` control, or direct Create3 movement.

---

## System Architecture

The main MediBot architecture is:

```text
Visitor
   ↓
UX / tablet
   ↓
Communication
   ↓
Navigation
   ↓
Create3
```

Navigation also reports route results back to Communication:

```text
Navigation
   ↓
Communication
```

Communication provides visitor-task states back to UX:

```text
Communication
   ↓
UX
```

For the current two-robot prototype:

```text
Jarvis = first-floor guidance robot
Gem    = second-floor guidance robot
Coordinator Pi = central Communication/task-coordination computer
```

---

## Successful Visitor Flow

The implemented Communication flow for the current prototype is:

```text
Visitor selects DIGITAL_LIBRARY
        ↓
destination_selected
        ↓
TaskCoordinator
        ↓
Jarvis start_route → ELEVATOR_1
        ↓
Jarvis arrived_at_transfer_point
        ↓
Jarvis = handover_requested
        ↓
Gem arrived_at_receiving_point
        ↓
Gem = handover_ready
        ↓
StatusMonitor
        ↓
handover_possible
        ↓
Jarvis → prepare_handover
Gem    → prepare_receive
        ↓
UX state = handover_ready
        ↓
Visitor confirms ready
        ↓
visitor_ready
        ↓
Gem start_route → DIGITAL_LIBRARY
        ↓
Gem arrived_at_destination
        ↓
task_complete
        ↓
task_reset
        ↓
waiting_for_destination
```

---

# Main Runtime Components

## `task_coordinator.py`

Runs on the **Coordinator Pi**.

This is the main high-level visitor-task state machine.

Responsibilities include:

* receiving destination selections from UX;
* storing the final destination;
* retaining the current `user_id`;
* tracking the current task stage;
* selecting the active robot;
* publishing Jarvis and Gem route requests;
* responding to handover decisions;
* accepting the post-handover visitor-ready event;
* processing final Navigation results;
* handling route failures and aborts;
* preventing duplicate/out-of-sequence task events;
* resetting completed or stopped tasks; and
* publishing high-level UX states.

The TaskCoordinator does not perform physical navigation.

---

## `ux_api_adapter.py`

Runs on the **Coordinator Pi**.

Provides the external HTTP interface between the UX application and the ROS 2 Communication system.

Architecture:

```text
External UX
   ↓ HTTP
UX/API Adapter
   ↓
/medibot/ux_event
   ↓
TaskCoordinator
```

and:

```text
TaskCoordinator
   ↓
/medibot/ux_state
   ↓
UX/API Adapter
   ↓ HTTP
External UX
```

The adapter deliberately keeps HTTP/Flutter transport separate from task-coordination logic.

Default HTTP port:

```text
8000
```

---

## `navigation_status_adapter.py`

Runs on the **Coordinator Pi**.

Translates agreed high-level Navigation result events into Communication robot states.

Examples:

```text
Jarvis:
arrived_at_transfer_point
    ↓
state = handover_requested
handover_status = pending
```

```text
Gem:
arrived_at_receiving_point
    ↓
state = handover_ready
handover_status = ready
```

The converted statuses are published on:

```text
/medibot/robot_status
```

---

## `status_monitor.py`

Runs on the **Coordinator Pi**.

Maintains the latest Communication status for Jarvis and Gem and determines whether handover is possible.

Main input:

```text
/medibot/robot_status
```

Main output:

```text
/medibot/handover_decision
```

The successful handover condition is:

```text
Jarvis = handover_requested
Gem    = handover_ready
```

which produces:

```text
handover_possible
```

The monitor also contains stale-status protection.

---

## `handover_decision_subscriber.py`

Runs on **both Jarvis and Gem**.

Listens to:

```text
/medibot/handover_decision
```

and turns coordinator decisions into robot-specific local actions.

For:

```text
handover_possible
```

Jarvis produces:

```text
prepare_handover
```

while Gem produces:

```text
prepare_receive
```

Robot role is selected using the `robot_name` ROS parameter.

---

## `local_action_subscriber.py`

Runs on **both Jarvis and Gem**.

Listens to:

```text
/medibot/jarvis/local_action
```

or:

```text
/medibot/gem/local_action
```

depending on the configured robot.

It validates and interprets robot-specific non-navigation actions.

Current local actions are software-level behaviour-interface actions. This node does **not** directly move the Create3.

---

# Launch Files

Two ROS 2 launch files are provided.

## Coordinator

Run on the Coordinator Pi:

```bash
cd ~/medibot_ws
source install/setup.bash
ros2 launch medibot_comm coordinator.launch.py
```

This starts the Coordinator-side Communication nodes, including:

```text
task_coordinator
ux_api_adapter
navigation_status_adapter
status_monitor
```

---

## Jarvis

Run on the Jarvis Pi:

```bash
cd ~/medibot_ws
source install/setup.bash
ros2 launch medibot_comm robot_comm.launch.py robot_name:=jarvis
```

This starts:

```text
/jarvis/handover_decision_subscriber
/jarvis/local_action_subscriber
```

---

## Gem

Run on the Gem Pi:

```bash
cd ~/medibot_ws
source install/setup.bash
ros2 launch medibot_comm robot_comm.launch.py robot_name:=gem
```

This starts:

```text
/gem/handover_decision_subscriber
/gem/local_action_subscriber
```

---

# Communication ↔ Navigation Interface

## Communication → Navigation

Communication publishes high-level physical route requests.

### Jarvis

Topic:

```text
/medibot/jarvis/navigation_command
```

Example:

```json
{
  "command": "start_route",
  "destination": "ELEVATOR_1"
}
```

### Gem

Topic:

```text
/medibot/gem/navigation_command
```

Example:

```json
{
  "command": "start_route",
  "destination": "DIGITAL_LIBRARY"
}
```

Navigation is responsible for deciding **how** the requested route is physically executed.

Communication must not directly run the route runner or send Create3 movement commands.

---

## Navigation → Communication

Navigation publishes high-level route results on:

```text
/medibot/navigation_event
```

Messages use `std_msgs/msg/String` containing JSON.

### Jarvis reaches transfer point

```json
{
  "robot_name": "jarvis",
  "navigation_event": "arrived_at_transfer_point",
  "destination": "ELEVATOR_1"
}
```

### Gem reaches receiving point

```json
{
  "robot_name": "gem",
  "navigation_event": "arrived_at_receiving_point",
  "destination": "ELEVATOR_1"
}
```

### Gem reaches final destination

```json
{
  "robot_name": "gem",
  "navigation_event": "arrived_at_destination",
  "destination": "DIGITAL_LIBRARY"
}
```

### Route failure

```json
{
  "robot_name": "jarvis",
  "navigation_event": "route_failed",
  "destination": "ELEVATOR_1",
  "reason": "navigation failure reason"
}
```

### Route abort

```json
{
  "robot_name": "gem",
  "navigation_event": "route_aborted",
  "destination": "DIGITAL_LIBRARY",
  "reason": "navigation abort reason"
}
```

Communication does not automatically retry a failed or aborted route. The task enters a stopped state until it is deliberately reset or future recovery behaviour is implemented.

---

# Communication ↔ UX Interface

The intended external UX interface is HTTP through `ux_api_adapter.py`.

## Start visitor task

```text
POST /route-requests
```

Example body:

```json
{
  "destination": "DIGITAL_LIBRARY",
  "user_id": "visitor_001"
}
```

A successful request causes Communication to begin the Jarvis guidance leg.

---

## Visitor ready after handover

```text
POST /visitor-ready
```

Example:

```json
{
  "user_id": "visitor_001"
}
```

Communication validates that the system is at the correct handover stage before starting Gem's route.

---

## Reset visitor task

```text
POST /task-reset
```

This returns the Communication state to:

```text
waiting_for_destination
```

---

## Read latest UX state

```text
GET /ux-state/latest
```

Example states include:

```text
initial_guidance
handover_ready
gem_guidance_started
task_complete
route_failed
route_aborted
waiting_for_destination
```

---

## Health check

```text
GET /health
```

This can be used to confirm that the HTTP adapter is running.

---

# Main ROS 2 Topics

| Topic                                | Direction                               | Purpose                       |
| ------------------------------------ | --------------------------------------- | ----------------------------- |
| `/medibot/ux_event`                  | UX adapter → TaskCoordinator            | High-level UX events          |
| `/medibot/ux_state`                  | TaskCoordinator → UX adapter            | High-level visitor-task state |
| `/medibot/navigation_event`          | Navigation → Communication              | Navigation results            |
| `/medibot/robot_status`              | NavigationStatusAdapter → StatusMonitor | Communication robot states    |
| `/medibot/handover_decision`         | StatusMonitor → robot/task nodes        | Handover coordination result  |
| `/medibot/jarvis/navigation_command` | Communication → Navigation              | Jarvis route requests         |
| `/medibot/gem/navigation_command`    | Communication → Navigation              | Gem route requests            |
| `/medibot/jarvis/local_action`       | Communication → Jarvis                  | Jarvis non-navigation actions |
| `/medibot/gem/local_action`          | Communication → Gem                     | Gem non-navigation actions    |

---

# Important Integration Rule

Physical route requests and local handover actions are deliberately separate.

Use:

```text
navigation_command
```

for actions that require the robot to physically navigate somewhere.

Use:

```text
local_action
```

for non-navigation coordination/behaviour actions such as:

```text
prepare_handover
prepare_receive
wait_for_partner
prepare_for_handover
block_handover_stale_status
```

There should not be two different interfaces for starting the same physical route.

---

# Building the Package

From the workspace:

```bash
cd ~/medibot_ws
colcon build --symlink-install --packages-select medibot_comm
source install/setup.bash
```

---

# Runtime Distribution

The intended runtime arrangement is:

```text
Coordinator Pi
├── TaskCoordinator
├── UX/API Adapter
├── NavigationStatusAdapter
└── StatusMonitor

Jarvis Pi
├── HandoverDecisionSubscriber
└── LocalActionSubscriber

Gem Pi
├── HandoverDecisionSubscriber
└── LocalActionSubscriber
```

The Navigation component may run additional Navigation-specific processes on the robot Pis. Those processes are outside this package's responsibility.

---

# Component Responsibilities

## Communication

Communication decides:

```text
which robot should guide
where the high-level route should go
when handover is possible
when the next task stage may begin
```

## Navigation

Navigation decides:

```text
how the robot physically reaches that destination
```

Navigation therefore owns:

* route planning;
* route execution;
* odometry;
* movement distances and turns;
* obstacle handling;
* Create3 movement/control; and
* Navigation-side command bridges.

## UX

UX owns:

* kiosk/tablet presentation;
* destination-selection screens;
* Confirm/Continue interactions;
* robot screen presentation;
* visitor-facing instructions; and
* visual design.

Communication provides state and task interfaces but does not control how these are displayed.

---

# Current Integration Status

The Communication subsystem has been independently tested through the complete software-level visitor sequence using the Coordinator, Jarvis and Gem Raspberry Pis.

Verified behaviour includes:

* external HTTP destination submission;
* Jarvis route-command generation;
* Jarvis transfer-point arrival processing;
* Gem receiving-point arrival processing;
* automatic handover decision generation;
* distributed `prepare_handover` and `prepare_receive` actions;
* HTTP visitor-ready confirmation;
* Gem final-route generation;
* final-destination completion;
* route-failure handling;
* route-abort handling;
* malformed/out-of-sequence request rejection;
* duplicate-task protection;
* task reset;
* reusable second visitor sessions; and
* launch-based operation across all three Raspberry Pis.

The remaining project-level work is primarily **joint integration with the real Navigation and UX implementations and physical end-to-end testing**.

---

# Integration Notes / Known Limitations

### Navigation status source freshness

The current `NavigationStatusAdapter` republishes its latest converted Communication status periodically so that the downstream `StatusMonitor` continues receiving a fresh status.

Therefore, the StatusMonitor's freshness check currently represents freshness of the **Communication-side status stream**, rather than independently proving that the original physical Navigation source has produced a new event recently.

If stronger physical-source liveness checking is required, this should be implemented/negotiated during final Navigation integration.

### Robot local actions

`local_action_subscriber.py` currently provides the software boundary for robot-specific handover behaviour.

It deliberately does not publish movement commands.

Any physical or visual behaviour triggered by actions such as `prepare_handover` or `prepare_receive` can be connected by the appropriate Navigation/UX behaviour layer during final integration.

### IP addresses

Device IP addresses may change depending on the network/DHCP configuration and should not be treated as part of the Communication API.

ROS 2 interfaces and machine roles should be used as the stable integration contract.

---

# Final Integration Target

The final integrated MediBot system should allow the following without manually publishing ROS test messages:

```text
Visitor selects destination in UX
        ↓
Communication automatically requests Jarvis route
        ↓
Navigation physically guides Jarvis
        ↓
Navigation reports Jarvis arrival
        ↓
Communication coordinates handover
        ↓
Visitor confirms continuation
        ↓
Communication automatically requests Gem route
        ↓
Navigation physically guides Gem
        ↓
Navigation reports final arrival
        ↓
Communication marks visitor task complete
        ↓
UX presents completion
```

The Communication component has been designed so that Navigation and UX can be integrated through these defined interfaces without duplicating their internal logic.