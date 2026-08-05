# Participant source overlay

This directory contains the participant-controlled execution overlay used for the reported L1-L5 evaluations.

- `robot_agent/`: planner, skills, environment backend, workflow, and task runner.
- `knowledge/`: fixed task and motion configuration.
- `pipeline/`: execution, scoring, realism-audit, video, and packaging tools.
- `robosuite_overrides/factory_sorting/`: two participant-controlled factory helpers for per-step attachment synchronization and continuous turning.

The organizer-provided full robosuite/MuJoCo scenes, assets, maps, and checkpoints are not duplicated here. See `TECHNICAL_REPORT.md` for architecture, versions, third-party acknowledgements, and limitations.
