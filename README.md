# Shower Fan for AppDaemon

Automates extraction fan for shower/bathrooms to reduce humidity. 

Features:

- Configurable timeout for manually switched on fan
- Automatic extraction based on hubidity
- Quite period (to avoid fan turning on automatically at night)

## Arguments



## Example

```yaml
master_bathroom_fan:
  module: shower_fan
  class: ShowerFan
  reference_humidity_sensor: sensor.living_room_humidity
  humidity_sensor: sensor.master_bathroom_climate_humidity
  humidity_relative_high: 30
  humidity_relative_low: 10
  quiet_time:
    from: "21:00:00"
    to: "07:00:00"
  fan_entity_id: fan.master_bathroom_fan
  fan_off_delay_minutes: 10
  log_level: INFO
```

## State Machine

```mermaid
stateDiagram-v2
  direction LR
  
  [*] --> INIT
  INIT --> EXTRACTION: TURNED_ON
  INIT --> OFF: TURNED_OFF
  INIT --> QUIET: START_QUIET_PERIOD
  OFF --> EXTRACTION: TURNED_ON
  OFF --> DRYING: HIGH_HUMIDITY
  OFF --> QUIET: START_QUIET_PERIOD
  EXTRACTION --> OFF: TIMEOUT
  EXTRACTION --> OFF: TURNED_OFF
  EXTRACTION --> DRYING: HIGH_HUMIDITY
  EXTRACTION --> QUIET: START_QUIET_PERIOD
  DRYING --> OFF: LOW_HUMIDITY
  DRYING --> OFF: TURNED_OFF
  DRYING --> OFF: TIMEOUT
  DRYING --> QUIET: START_QUIET_PERIOD
  QUIET --> QUIET_EXTRACTION: TURNED_ON
  QUIET --> OFF: END_QUIET_PERIOD
  QUIET_EXTRACTION --> QUIET: TIMEOUT
  QUIET_EXTRACTION --> QUIET: TURNED_OFF
  QUIET_EXTRACTION --> OFF: END_QUIET_PERIOD
```