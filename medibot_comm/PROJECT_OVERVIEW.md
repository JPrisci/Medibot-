
# MediBot Communication — Project Overview

This document provides an overview of the Communication component developed for the 2026 MediBot capstone project. It summarises the completed implementation, system architecture, testing, limitations and possible future improvements.

For detailed technical information, including ROS 2 topics, message formats, HTTP interfaces and launch commands, see [README.md](README.md).

## 1. Project Background

MediBot is a multi-robot visitor guidance project that explores how social robots could support wayfinding in environments such as hospitals. The aim is to help visitors reach their destinations, including situations where they need to move between floors and transfer from one robot to another.

The 2026 prototype used two robots, Jarvis and Gem, together with tablet and robot-facing user interfaces. The project was divided into three main components:

- **Communication:** Visitor-task coordination, robot handover and communication between system components.
- **Navigation:** Physical robot movement, route execution and navigation-related behaviours.
- **UX:** Tablet and robot interfaces used to interact with visitors.

The Communication component was developed to coordinate these parts so that the robots could operate as one visitor guidance system.

## 2. Communication System Architecture

The Communication system uses a central Coordinator Raspberry Pi alongside the Raspberry Pis associated with Jarvis and Gem. The implementation uses Python, ROS 2 Jazzy and ROS 2 topics to exchange messages between components.

### Coordinator Pi

The Coordinator runs the main visitor-task management and handover logic. It also provides the interfaces used to communicate with Navigation and UX.

Four Communication nodes run on the Coordinator:

- **TaskCoordinator (`task_coordinator.py`):** Maintains the active visitor task, stores the selected destination, tracks task progress and sends high-level route requests to Navigation.
- **UX/API Adapter (`ux_api_adapter.py`):** Connects the external UX application to Communication through HTTP requests and ROS 2 messages.
- **NavigationStatusAdapter (`navigation_status_adapter.py`):** Converts Navigation handover events into robot states used by Communication.
- **StatusMonitor (`status_monitor.py`):** Maintains the latest robot states, checks received status freshness and determines whether the handover conditions are satisfied.

### Robot-Side Communication

Jarvis and Gem each run two additional Communication nodes:

- **HandoverDecisionSubscriber (`handover_decision_subscriber.py`):** Receives central handover decisions and produces robot-specific local actions.
- **LocalActionSubscriber (`local_action_subscriber.py`):** Receives, validates and interprets local actions for the configured robot.

For example, when handover becomes possible, Jarvis produces a `prepare_handover` action while Gem produces `prepare_receive`.

These robot-side actions are implemented and handled at the software level. They provide an interface that could be connected to robot-specific behaviours in future development.

The main visitor-task progression is managed by the Coordinator through its Navigation and UX interfaces.

The package includes two ROS 2 launch files:

- `coordinator.launch.py` starts the four Coordinator-side Communication nodes.
- `robot_comm.launch.py` starts the two robot-side Communication nodes, using a `robot_name` parameter to configure Jarvis or Gem.

The Navigation and UX applications are separate from these Communication launch files.

## 3. Implemented Visitor Workflow

The prototype was tested on a predefined route across Floors 1 and 2 of G Block.

During the user study, participants selected the Fashion department through the UX interface as part of a store-themed scenario. This corresponded to `DIGITAL_LIBRARY`, the destination identifier used internally by the system. Communication stores this destination and requests that Jarvis begin the first guidance stage towards `ELEVATOR_2`.

When Navigation reports that Jarvis has reached the transfer point, Communication updates Jarvis's handover state. Gem's receiving readiness is also reported through the Navigation interface.

Once Jarvis has requested handover and Gem is ready, the StatusMonitor produces a `handover_possible` decision.

The TaskCoordinator then notifies UX that the handover is ready. After the visitor confirms they are ready to continue, Communication requests that Gem navigate to the previously selected final destination.

When Navigation reports that Gem has reached `DIGITAL_LIBRARY`, the TaskCoordinator marks the visitor task as complete and publishes the completion state to UX.

The system also supports explicit task reset so that another visitor session can begin without reusing the previous task's stored handover states.

## 4. Integration and Testing Completed

The Communication component was developed and evaluated through several stages of testing.

These included:

- ROS 2 communication testing across the three Raspberry Pis.
- Coordinator status monitoring and handover-decision testing.
- Integration with Navigation event and command interfaces.
- Integration with the external UX through HTTP.
- Complete software-level visitor-task testing.
- Invalid-input, duplicate-event and task-reset testing.
- Navigation failure and abort handling.
- Testing with the integrated physical MediBot prototype.

The final integrated prototype was also used in the project's user study with 15 participants.

Fourteen participants completed the full route, and fourteen were recorded as fully understanding the handover and identifying the correct robot to follow. One participant's route was not completed because Gem did not move after the handover. The exact underlying cause was not confirmed.

These results support the Communication approach used for the two-robot guidance and handover scenario. However, the system remains a research prototype and would require further development and testing before real hospital deployment.

## 5. Current Limitations and Future Development

The completed system provides a working foundation for future development. However, several limitations should be considered before extending it.

### Navigation Status Freshness

The NavigationStatusAdapter stores and periodically republishes the latest converted Navigation-derived robot states.

Although the StatusMonitor checks whether Communication status messages are still being received, this does not independently confirm whether the original Navigation process is still running.

Future development could introduce a Navigation heartbeat, source timestamp or another direct liveness check to improve the reliability of the handover information.

### Central Coordinator Dependency

The current system uses one Coordinator Pi to maintain visitor-task state and make coordination decisions.

This simplifies coordination for the two-robot prototype, but it also creates a single point of failure. There is currently no backup Coordinator or automatic recovery mechanism.

Future development could investigate Coordinator recovery, backup coordination or other fault-tolerance mechanisms.

### Robot and Route Scalability

The current Communication implementation is designed around two robots with fixed roles:

- Jarvis handles the first guidance stage.
- Gem handles the second guidance stage.

The prototype also supports one predefined destination and one active visitor task at a time.

Future development could extend the system to support additional robots, multiple destinations, different transfer points and multiple simultaneous visitor sessions.

### Robot-Side Behaviours

The robot-side Communication nodes currently process and log local handover actions.

These actions could be extended through the relevant Navigation or UX components to trigger additional physical or visitor-facing behaviours where required.

### Physical Robot Operation

During the final prototype testing, Jarvis and Gem needed to be manually returned to their starting positions between runs.

Future development could include automatic return-to-start behaviour, charging management and improved recovery from robot or network failures.

Additional testing would also be useful to improve reliability during longer periods of operation.

### Wider System Evaluation

The final user study used one predefined route with 15 participants in a university setting.

Before deployment in a real hospital, the system would require further testing with more routes, destinations, users and environmental conditions.

The user study also identified opportunities to improve aspects of the guidance experience, including robot pacing, turn clarity and some interface controls.

## 6. Development and Integration Notes

The existing [README.md](README.md) provides the detailed technical reference for the Communication component. It documents the ROS 2 interfaces, message formats, HTTP endpoints, launch commands and responsibilities of the individual Communication nodes.

The main architectural separation is between Communication, Navigation and UX:

- Communication manages visitor-task coordination and high-level route requests.
- Navigation handles physical robot movement and reports route events.
- UX handles visitor-facing interaction and displays.

The `medibot_comm` folder in the shared MediBot repository contains the Communication component rather than the complete MediBot system.

The provided launch files support the Coordinator-side and robot-side Communication nodes. The corresponding Navigation and UX components operate through the defined interfaces.

Changes affecting Navigation commands, Navigation events or HTTP endpoints need to remain consistent across the integrated components.

The existing implementation provides a foundation for additional robot behaviours, more flexible task coordination and future reliability improvements.

## 7. Summary

The 2026 MediBot Communication component provides a centralised coordination system for the current two-robot visitor guidance prototype.

It supports visitor-task management, high-level Navigation requests, handover readiness evaluation, integration with UX, failure handling and reusable task sessions.

The completed system was tested independently and as part of the integrated physical MediBot prototype.

The existing implementation and interfaces provide a foundation for extending the project towards more flexible, scalable and reliable multi-robot visitor guidance.
