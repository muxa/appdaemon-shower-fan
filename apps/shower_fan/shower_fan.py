import appdaemon.plugins.hass.hassapi as hass

DEBUG = "DEBUG"
DEFAULT_FAN_DELAYED_OFF_MINUTES = 5
DEFAULT_HUMIDITY_RELATIVE_HIGH = 20
DEFAULT_HUMIDITY_RELATIVE_LOW = 10

CONFIG_REFERENCE_HUMIDITY_SENSOR = "reference_humidity_sensor"
CONFIG_HUMIDITY_SENSOR = "humidity_sensor"
CONFIG_HUMIDITY_RELATIVE_HIGH = "humidity_relative_high"
CONFIG_HUMIDITY_RELATIVE_LOW = "humidity_relative_low"
CONFIG_QUIET_SWITCH = "quiet_switch"
CONFIG_FAN = "fan"
CONFIG_FAN_OFF_DELAY_MINUTES = "fan_off_delay_minutes"


class ShowerFan(hass.Hass):
    # states
    INIT = "init"
    OFF = "off"
    EXTRACTION = "extraction"
    DRYING = "drying"
    QUIET = "quiet"
    QUIET_EXTRACTION = "quiet extraction"

    # triggers
    TURNED_ON = "turned on"
    TURNED_OFF = "turned off"
    HIGH_HUMIDITY = "high humidity"
    LOW_HUMIDITY = "low humidity"
    TIMEOUT = "timeout"
    BEGIN_QUIET = "begin quiet"
    END_QUIET = "end quiet"

    def initialize(self):
        self.reference_humidity_sensor = self.args.get(CONFIG_REFERENCE_HUMIDITY_SENSOR)
        self.humidity_sensor = self.args.get(CONFIG_HUMIDITY_SENSOR)
        self.humidity_relative_high = float(
            self.args.get(CONFIG_HUMIDITY_RELATIVE_HIGH, DEFAULT_HUMIDITY_RELATIVE_HIGH)
        )
        self.humidity_relative_low = float(
            self.args.get(CONFIG_HUMIDITY_RELATIVE_LOW, DEFAULT_HUMIDITY_RELATIVE_LOW)
        )

        self.quiet_switch = self.args.get(CONFIG_QUIET_SWITCH)
        self.log(f"Quiet switch: {self.quiet_switch}", level=DEBUG)
        self.listen_state(self._on_quiet_switch_state, self.quiet_switch)

        if self.reference_humidity_sensor:
            self.log(
                f"Reference humidity sensor: {self.reference_humidity_sensor}",
                level=DEBUG,
            )

        if self.humidity_sensor:
            self.log(f"Humidity sensor: {self.humidity_sensor}", level=DEBUG)
            self.listen_state(self._log_entity_state, self.humidity_sensor)
            self.listen_state(self._on_humidity_state, self.humidity_sensor)

        self.fan = self.args.get(CONFIG_FAN)
        self.log(f"Extraction fan: {self.fan}", level=DEBUG)
        self.fan_off_delay_seconds = (
            float(
                self.args.get(
                    CONFIG_FAN_OFF_DELAY_MINUTES, DEFAULT_FAN_DELAYED_OFF_MINUTES
                )
            )
            * 60
        )
        self.fan_timeout_handle = None
        self.current_state = ShowerFan.INIT

        self.listen_state(self._on_fan_state, self.fan)

        self.log(
            f"{self.fan} configured with {self.fan_off_delay_seconds} off delay",
            level=DEBUG,
        )

        self.restore_state()

    # commands -----------------

    def restore_state(self):
        is_quiet_period = self.get_state(self.quiet_switch) == "on"

        if is_quiet_period:
            self.trigger(ShowerFan.BEGIN_QUIET)
            if self.is_on():
                self.trigger(ShowerFan.TURNED_ON)
        elif self.is_on():
            self.trigger(ShowerFan.TURNED_ON)
        else:
            self.trigger(ShowerFan.TURNED_OFF)

    def turn_on(self):
        if not self.is_on():
            self.call_service("homeassistant/turn_on", entity_id=self.fan)

    def turn_off(self):
        if self.is_on():
            self.call_service("homeassistant/turn_off", entity_id=self.fan)

    def is_on(self):
        return self.get_state(self.fan) == "on"

    def begin_timeout(self, duration):
        self.end_timeout()
        self.fan_timeout_handle = self.run_in(self.on_timeout, duration)

    def end_timeout(self):
        if self.fan_timeout_handle is not None:
            # already on with delay
            self.cancel_timer(self.fan_timeout_handle)

        self.fan_timeout_handle = None

    # state machine -------------------

    def trigger(self, input):
        previous_state = self.current_state
        if self.current_state == ShowerFan.INIT:
            if input == ShowerFan.TURNED_ON:
                self.set_extraction()
            elif input == ShowerFan.TURNED_OFF:
                self.set_off()
            elif input == ShowerFan.BEGIN_QUIET:
                self.set_quiet()
            else:
                self.log_invalid_transition(input)
                return
        elif self.current_state == ShowerFan.OFF:
            if input == ShowerFan.TURNED_ON:
                self.set_extraction()
            elif input == ShowerFan.HIGH_HUMIDITY:
                self.set_drying()
            elif input == ShowerFan.BEGIN_QUIET:
                self.set_quiet()
            else:
                self.log_invalid_transition(input)
                return
        elif self.current_state == ShowerFan.EXTRACTION:
            if input == ShowerFan.TIMEOUT:
                self.set_off()
            elif input == ShowerFan.TURNED_OFF:
                self.set_off()
            elif input == ShowerFan.HIGH_HUMIDITY:
                self.set_drying()
            elif input == ShowerFan.BEGIN_QUIET:
                self.set_quiet()
            else:
                self.log_invalid_transition(input)
                return
        elif self.current_state == ShowerFan.DRYING:
            if input == ShowerFan.LOW_HUMIDITY:
                self.set_off()
            elif input == ShowerFan.TURNED_OFF:
                self.set_off()
            elif input == ShowerFan.TIMEOUT:
                self.set_off()
            elif input == ShowerFan.BEGIN_QUIET:
                self.set_quiet()
            else:
                self.log_invalid_transition(input)
                return
        elif self.current_state == ShowerFan.QUIET:
            if input == ShowerFan.TURNED_ON:
                self.set_quiet_extraction()
            elif input == ShowerFan.END_QUIET:
                self.set_off()
            else:
                self.log_invalid_transition(input)
                return
        elif self.current_state == ShowerFan.QUIET_EXTRACTION:
            if input == ShowerFan.TIMEOUT:
                self.set_quiet()
            elif input == ShowerFan.TURNED_OFF:
                self.set_quiet()
            elif input == ShowerFan.END_QUIET:
                self.set_off()
            else:
                self.log_invalid_transition(input)
                return
        else:
            self.log_invalid_transition(input)
            return
        self.log(
            f"Transitioned from '{previous_state}' to '{self.current_state}' on '{input}'",
            level=DEBUG,
        )
        self.set_state(
            f"sensor.{self.name}_fan_state_machine",
            state=self.current_state,
            attributes={"input": input, "previous_state": previous_state},
        )

    def log_invalid_transition(self, input):
        self.log(
            f"Transition from '{self.current_state}' on '{input}' is not allowed",
            level="WARNING",
        )

    def set_off(self):
        self.current_state = ShowerFan.OFF
        self.turn_off()

    def set_quiet_extraction(self):
        self.current_state = ShowerFan.QUIET_EXTRACTION
        self.begin_timeout(self.fan_off_delay_seconds)
        self.turn_on()

    def set_extraction(self):
        self.current_state = ShowerFan.EXTRACTION
        self.begin_timeout(self.fan_off_delay_seconds)
        self.turn_on()

    def set_drying(self):
        self.current_state = ShowerFan.DRYING
        self.begin_timeout(3600)  # large timeout
        self.turn_on()

    def set_quiet(self):
        self.current_state = ShowerFan.QUIET
        self.end_timeout()
        self.turn_off()

    # state listeners -----------------

    def _log_entity_state(self, entity, attribute, old, new, kwargs):
        self.log(
            f"{entity} {attribute} changed from {old} to {new}. {kwargs}", level=DEBUG
        )

    def _on_humidity_state(self, entity, attribute, old, new, kwargs):
        if self.reference_humidity_sensor:
            reference_humidity = float(self.get_state(self.reference_humidity_sensor))
            humidity = float(new)
            self.log(
                f"humidity: {humidity}, reference_humidity: {reference_humidity}",
                level=DEBUG,
            )

            if humidity > (reference_humidity + self.humidity_relative_high):
                self.trigger(ShowerFan.HIGH_HUMIDITY)
            elif humidity < (reference_humidity + self.humidity_relative_low):
                self.trigger(ShowerFan.LOW_HUMIDITY)

    def _on_quiet_switch_state(self, entity, attribute, old, new, kwargs):
        self.log(
            f"{self.name} {attribute} changed from {old} to {new}. {kwargs}",
            level=DEBUG,
        )

        if old == "unavailable" or new == "unavailable":
            return

        if new == "on":
            self.trigger(ShowerFan.BEGIN_QUIET)
        elif new == "off":
            self.trigger(ShowerFan.END_QUIET)

    def _on_fan_state(self, entity, attribute, old, new, kwargs):
        self.log(
            f"{self.name} {attribute} changed from {old} to {new}. {kwargs}",
            level=DEBUG,
        )

        if old == "unavailable" or new == "unavailable":
            return

        if new == "on":
            self.trigger(ShowerFan.TURNED_ON)
        elif new == "off":
            self.trigger(ShowerFan.TURNED_OFF)

    # timers callbacks ----------------

    def on_timeout(self, kwargs):
        self.fan_timeout_handle = None
        self.trigger(ShowerFan.TIMEOUT)
