# Flowchart Website — Project Plan

## Concept
A logic-based flowchart/task dependency tool. Users define tasks and connect them with logic gates to express conditional dependencies. Example: to complete task X, both task Y and task Z must be completed first (AND gate).

## Core Features
- Create and label task nodes
- Connect tasks with logic gates (AND, OR, etc.)
- Visual flowchart canvas — drag, drop, connect nodes
- Real-time evaluation: automatically determine which tasks are currently actionable based on gate logic
- Mark tasks as complete and watch downstream gates resolve

## Logic Gates
- **AND** — all upstream tasks must be complete before this task unlocks
- **OR** — at least one upstream task must be complete
- More gates (NOT, XOR) to be decided

## Tech Stack
- **Backend:** Python (Flask or FastAPI) — serves the app and handles logic evaluation
- **Frontend:** Plain HTML, CSS, JavaScript — no framework

## Architecture (planned)
- Frontend canvas renders the flowchart (likely using an HTML5 Canvas or SVG, or a library like jsPlumb/GoJS/D3)
- Backend exposes a REST API for saving/loading flowcharts and evaluating gate logic
- Flowchart state stored server-side (file or database TBD)

## Status
- Early planning stage
- No frontend or backend code written yet
