import pytest
import pytest_mock
from unittest import mock
from appdaemon_testing.pytest import automation_fixture
import appdaemon.plugins.hass.hassapi as hass

import sys

sys.path.append("apps/shower_fan")

from shower_fan import ShowerFan, TimeRange

HASS_LISTEN_STATE = "listen_state"
HASS_RUN_DAILY = "run_daily"
HASS_RUN_IN = "run_in"
HASS_CANCEL_TIMER = "cancel_timer"
HASS_CALL_SERVICE = "call_service"
HASS_NOW_IS_BETWEEN = "now_is_between"

FAN = "fan.master_bathroom_fan"
REFERENCE_HUMIDITY_SENSOR = "sensor.living_room_humidity"
HUMIDITY_SENSOR = "sensor.master_bathroom_climate_humidity"
QUIET_TIME_FROM = "21:00:00"
QUIET_TIME_TO = "07:00:00"


@automation_fixture(
    ShowerFan,
    args={
        "fan_entity_id": FAN,
        "reference_humidity_sensor": REFERENCE_HUMIDITY_SENSOR,
        "humidity_sensor": HUMIDITY_SENSOR,
        "quiet_time": {"from": QUIET_TIME_FROM, "to": QUIET_TIME_TO},
    },
    initialize=False,
)
def shower_fan_app() -> ShowerFan:
    pass


def test_listens_to_state(hass_driver, shower_fan_app: ShowerFan):
    shower_fan_app.initialize()
    listen_state = hass_driver.get_mock(HASS_LISTEN_STATE)
    listen_state.assert_has_calls(
        [
            mock.call(shower_fan_app._on_humidity_state, HUMIDITY_SENSOR),
            mock.call(shower_fan_app._on_fan_state, FAN),
        ]
    )


def test_registers_start_of_quiet_time(hass_driver, shower_fan_app: ShowerFan):
    shower_fan_app.initialize()
    run_daily = hass_driver.get_mock(HASS_RUN_DAILY)
    run_daily.assert_has_calls(
        [
            mock.call(
                shower_fan_app.on_quite_time_schedule,
                QUIET_TIME_FROM,
                trigger=ShowerFan.START_QUIET_PERIOD,
            ),
        ]
    )


def test_registers_end_of_quiet_time(hass_driver, shower_fan_app: ShowerFan):
    shower_fan_app.initialize()
    run_daily = hass_driver.get_mock(HASS_RUN_DAILY)
    run_daily.assert_has_calls(
        [
            mock.call(
                shower_fan_app.on_quite_time_schedule,
                QUIET_TIME_TO,
                trigger=ShowerFan.END_QUIET_PERIOD,
            ),
        ]
    )


def test_restore_state_on_initialize(
    hass_driver, shower_fan_app: ShowerFan, mocker: pytest_mock.MockerFixture
):
    restore_state_spy = mocker.spy(shower_fan_app, "restore_state")

    shower_fan_app.initialize()

    restore_state_spy.assert_called_once()


def test_restore_state_triggers_turned_off_when_fan_is_off_and_not_quiet(
    hass_driver, shower_fan_app: ShowerFan, mocker: pytest_mock.MockerFixture
):
    with hass_driver.setup():
        hass_driver.set_state(FAN, "off")

    now_is_between_mock = mock.Mock()
    setattr(hass.Hass, "now_is_between", now_is_between_mock)
    now_is_between_mock.return_value = False

    trigger_spy = mocker.spy(shower_fan_app, "trigger")

    shower_fan_app.initialize()

    trigger_spy.assert_has_calls(
        [
            mock.call(ShowerFan.TURNED_OFF),
        ]
    )


def test_restore_state_triggers_turned_on_when_fan_is_on_and_not_quiet(
    hass_driver, shower_fan_app: ShowerFan, mocker: pytest_mock.MockerFixture
):
    with hass_driver.setup():
        hass_driver.set_state(FAN, "on")

    now_is_between_mock = mock.Mock()
    setattr(hass.Hass, "now_is_between", now_is_between_mock)
    now_is_between_mock.return_value = False

    trigger_spy = mocker.spy(shower_fan_app, "trigger")

    shower_fan_app.initialize()

    trigger_spy.assert_has_calls(
        [
            mock.call(ShowerFan.TURNED_ON),
        ]
    )


def test_restore_state_triggers_start_quiet_period_when_within_quiet_time(
    hass_driver, shower_fan_app: ShowerFan, mocker: pytest_mock.MockerFixture
):
    with hass_driver.setup():
        hass_driver.set_state(FAN, "off")

    now_is_between_mock = mock.Mock()
    setattr(hass.Hass, "now_is_between", now_is_between_mock)
    now_is_between_mock.return_value = True

    trigger_spy = mocker.spy(shower_fan_app, "trigger")

    shower_fan_app.initialize()

    trigger_spy.assert_has_calls(
        [
            mock.call(ShowerFan.START_QUIET_PERIOD),
        ]
    )


def test_restore_state_triggers_start_quiet_period_and_turned_on_when_within_quiet_time_and_fan_is_on(
    hass_driver, shower_fan_app: ShowerFan, mocker: pytest_mock.MockerFixture
):
    with hass_driver.setup():
        hass_driver.set_state(FAN, "on")

    now_is_between_mock = mock.Mock()
    setattr(hass.Hass, "now_is_between", now_is_between_mock)
    now_is_between_mock.return_value = True

    trigger_spy = mocker.spy(shower_fan_app, "trigger")

    shower_fan_app.initialize()

    trigger_spy.assert_has_calls(
        [
            mock.call(ShowerFan.START_QUIET_PERIOD),
            mock.call(ShowerFan.TURNED_ON),
        ]
    )


@pytest.mark.parametrize(
    "initial_state,input,target_state",
    [
        (ShowerFan.INIT, ShowerFan.TURNED_ON, ShowerFan.EXTRACTION),
        (ShowerFan.INIT, ShowerFan.START_QUIET_PERIOD, ShowerFan.QUIET),
        (ShowerFan.INIT, ShowerFan.TURNED_OFF, ShowerFan.OFF),
        (ShowerFan.INIT, ShowerFan.HIGH_HUMIDITY, ShowerFan.INIT),
        (ShowerFan.INIT, ShowerFan.TIMEOUT, ShowerFan.INIT),
        (ShowerFan.INIT, ShowerFan.LOW_HUMIDITY, ShowerFan.INIT),
        (ShowerFan.OFF, ShowerFan.TURNED_ON, ShowerFan.EXTRACTION),
        (ShowerFan.OFF, ShowerFan.HIGH_HUMIDITY, ShowerFan.DRYING),
        (ShowerFan.OFF, ShowerFan.START_QUIET_PERIOD, ShowerFan.QUIET),
        (ShowerFan.OFF, ShowerFan.TURNED_OFF, ShowerFan.OFF),
        (ShowerFan.OFF, ShowerFan.TIMEOUT, ShowerFan.OFF),
        (ShowerFan.OFF, ShowerFan.LOW_HUMIDITY, ShowerFan.OFF),
        (ShowerFan.OFF, ShowerFan.END_QUIET_PERIOD, ShowerFan.OFF),
        (ShowerFan.EXTRACTION, ShowerFan.TURNED_OFF, ShowerFan.OFF),
        (ShowerFan.EXTRACTION, ShowerFan.TIMEOUT, ShowerFan.OFF),
        (ShowerFan.EXTRACTION, ShowerFan.HIGH_HUMIDITY, ShowerFan.DRYING),
        (ShowerFan.EXTRACTION, ShowerFan.LOW_HUMIDITY, ShowerFan.EXTRACTION),
        (ShowerFan.EXTRACTION, ShowerFan.TURNED_ON, ShowerFan.EXTRACTION),
        (ShowerFan.EXTRACTION, ShowerFan.START_QUIET_PERIOD, ShowerFan.QUIET),
        (ShowerFan.EXTRACTION, ShowerFan.END_QUIET_PERIOD, ShowerFan.EXTRACTION),
        (ShowerFan.DRYING, ShowerFan.TURNED_OFF, ShowerFan.OFF),
        (ShowerFan.DRYING, ShowerFan.LOW_HUMIDITY, ShowerFan.OFF),
        (ShowerFan.DRYING, ShowerFan.TIMEOUT, ShowerFan.OFF),
        (ShowerFan.DRYING, ShowerFan.START_QUIET_PERIOD, ShowerFan.QUIET),
        (ShowerFan.DRYING, ShowerFan.HIGH_HUMIDITY, ShowerFan.DRYING),
        (ShowerFan.DRYING, ShowerFan.TURNED_ON, ShowerFan.DRYING),
        (ShowerFan.DRYING, ShowerFan.END_QUIET_PERIOD, ShowerFan.DRYING),
        (ShowerFan.QUIET, ShowerFan.END_QUIET_PERIOD, ShowerFan.OFF),
        (ShowerFan.QUIET, ShowerFan.TURNED_ON, ShowerFan.QUIET_EXTRACTION),
        (ShowerFan.QUIET, ShowerFan.TURNED_OFF, ShowerFan.QUIET),
        (ShowerFan.QUIET, ShowerFan.LOW_HUMIDITY, ShowerFan.QUIET),
        (ShowerFan.QUIET, ShowerFan.TIMEOUT, ShowerFan.QUIET),
        (ShowerFan.QUIET, ShowerFan.START_QUIET_PERIOD, ShowerFan.QUIET),
        (ShowerFan.QUIET, ShowerFan.HIGH_HUMIDITY, ShowerFan.QUIET),
        (ShowerFan.QUIET_EXTRACTION, ShowerFan.TURNED_OFF, ShowerFan.QUIET),
        (ShowerFan.QUIET_EXTRACTION, ShowerFan.TIMEOUT, ShowerFan.QUIET),
        (ShowerFan.QUIET_EXTRACTION, ShowerFan.END_QUIET_PERIOD, ShowerFan.OFF),
        (ShowerFan.QUIET_EXTRACTION, ShowerFan.TURNED_ON, ShowerFan.QUIET_EXTRACTION),
        (
            ShowerFan.QUIET_EXTRACTION,
            ShowerFan.LOW_HUMIDITY,
            ShowerFan.QUIET_EXTRACTION,
        ),
        (
            ShowerFan.QUIET_EXTRACTION,
            ShowerFan.START_QUIET_PERIOD,
            ShowerFan.QUIET_EXTRACTION,
        ),
        (
            ShowerFan.QUIET_EXTRACTION,
            ShowerFan.HIGH_HUMIDITY,
            ShowerFan.QUIET_EXTRACTION,
        ),
    ],
)
def test_transition(
    hass_driver, shower_fan_app: ShowerFan, input, initial_state, target_state
):
    shower_fan_app.initialize()
    shower_fan_app.current_state = initial_state

    shower_fan_app.trigger(input)

    assert shower_fan_app.current_state == target_state


def test_fan_turning_on_when_extraction(hass_driver, shower_fan_app: ShowerFan):
    with hass_driver.setup():
        hass_driver.set_state(FAN, "off")

    shower_fan_app.initialize()

    shower_fan_app.set_extraction()

    call_service = hass_driver.get_mock(HASS_CALL_SERVICE)
    call_service.assert_has_calls(
        [
            mock.call("homeassistant/turn_on", entity_id=FAN),
        ]
    )


def test_fan_turning_off_when_off(hass_driver, shower_fan_app: ShowerFan):
    with hass_driver.setup():
        hass_driver.set_state(FAN, "on")

    shower_fan_app.initialize()

    shower_fan_app.set_off()

    call_service = hass_driver.get_mock(HASS_CALL_SERVICE)
    call_service.assert_has_calls(
        [
            mock.call("homeassistant/turn_off", entity_id=FAN),
        ]
    )


def test_fan_turning_on_when_drying(hass_driver, shower_fan_app: ShowerFan):
    with hass_driver.setup():
        hass_driver.set_state(FAN, "off")

    shower_fan_app.initialize()

    shower_fan_app.set_drying()

    call_service = hass_driver.get_mock(HASS_CALL_SERVICE)
    call_service.assert_has_calls(
        [
            mock.call("homeassistant/turn_on", entity_id=FAN),
        ]
    )


def test_fan_turning_off_when_quiet(hass_driver, shower_fan_app: ShowerFan):
    with hass_driver.setup():
        hass_driver.set_state(FAN, "on")

    shower_fan_app.initialize()
    shower_fan_app.current_state = ShowerFan.DRYING

    shower_fan_app.set_quiet()

    call_service = hass_driver.get_mock(HASS_CALL_SERVICE)
    call_service.assert_has_calls(
        [
            mock.call("homeassistant/turn_off", entity_id=FAN),
        ]
    )


def test_fan_turning_on_when_quiet_extraction(hass_driver, shower_fan_app: ShowerFan):
    with hass_driver.setup():
        hass_driver.set_state(FAN, "off")

    shower_fan_app.initialize()
    shower_fan_app.current_state = ShowerFan.QUIET

    shower_fan_app.set_quiet_extraction()

    call_service = hass_driver.get_mock(HASS_CALL_SERVICE)
    call_service.assert_has_calls(
        [
            mock.call("homeassistant/turn_on", entity_id=FAN),
        ]
    )


def test_fan_on_triggers_turned_on(
    hass_driver, shower_fan_app: ShowerFan, mocker: pytest_mock.MockerFixture
):
    with hass_driver.setup():
        hass_driver.set_state(FAN, "off")

    shower_fan_app.initialize()

    trigger_spy = mocker.spy(shower_fan_app, "trigger")
    hass_driver.set_state(FAN, "on")

    trigger_spy.assert_has_calls(
        [
            mock.call(ShowerFan.TURNED_ON),
        ]
    )


def test_fan_off_triggers_turned_off(
    hass_driver, shower_fan_app: ShowerFan, mocker: pytest_mock.MockerFixture
):
    with hass_driver.setup():
        hass_driver.set_state(FAN, "on")

    shower_fan_app.initialize()

    trigger_spy = mocker.spy(shower_fan_app, "trigger")
    hass_driver.set_state(FAN, "off")

    trigger_spy.assert_has_calls(
        [
            mock.call(ShowerFan.TURNED_OFF),
        ]
    )


def test_humidity_sensor_going_above_higher_threshold_triggers_high_humidity(
    hass_driver, shower_fan_app: ShowerFan, mocker: pytest_mock.MockerFixture
):
    with hass_driver.setup():
        hass_driver.set_state(FAN, "off")
        hass_driver.set_state(REFERENCE_HUMIDITY_SENSOR, "50")

    shower_fan_app.initialize()

    trigger_spy = mocker.spy(shower_fan_app, "trigger")
    hass_driver.set_state(HUMIDITY_SENSOR, "71")

    trigger_spy.assert_has_calls(
        [
            mock.call(ShowerFan.HIGH_HUMIDITY),
        ]
    )


def test_humidity_sensor_going_below_lower_threshold_triggers_low_humidity(
    hass_driver, shower_fan_app: ShowerFan, mocker: pytest_mock.MockerFixture
):
    with hass_driver.setup():
        hass_driver.set_state(FAN, "on")
        hass_driver.set_state(REFERENCE_HUMIDITY_SENSOR, "50")

    shower_fan_app.initialize()

    trigger_spy = mocker.spy(shower_fan_app, "trigger")
    hass_driver.set_state(HUMIDITY_SENSOR, "59")

    trigger_spy.assert_has_calls(
        [
            mock.call(ShowerFan.LOW_HUMIDITY),
        ]
    )


def test_humidity_sensor_within_threshold_does_not_trigger(
    hass_driver, shower_fan_app: ShowerFan, mocker: pytest_mock.MockerFixture
):
    with hass_driver.setup():
        hass_driver.set_state(FAN, "off")
        hass_driver.set_state(REFERENCE_HUMIDITY_SENSOR, "50")

    shower_fan_app.initialize()

    trigger_spy = mocker.spy(shower_fan_app, "trigger")
    hass_driver.set_state(HUMIDITY_SENSOR, "70")

    trigger_spy.assert_not_called()

def test_quite_period_schedule_initialised(hass_driver, shower_fan_app: ShowerFan):
    with hass_driver.setup():
        hass_driver.set_state(FAN, "off")

    shower_fan_app.initialize()

    run_daily_mock = hass_driver.get_mock(HASS_RUN_DAILY)
    run_daily_mock.assert_has_calls(
        [
            mock.call(
                shower_fan_app.on_quite_time_schedule,
                QUIET_TIME_FROM,
                trigger=ShowerFan.START_QUIET_PERIOD,
            ),
            mock.call(
                shower_fan_app.on_quite_time_schedule,
                QUIET_TIME_TO,
                trigger=ShowerFan.END_QUIET_PERIOD,
            ),
        ]
    )


def test_quite_period_schedule_triggers_transition(
    hass_driver, shower_fan_app: ShowerFan, mocker: pytest_mock.MockerFixture
):
    with hass_driver.setup():
        hass_driver.set_state(FAN, "off")

    shower_fan_app.initialize()

    trigger_spy = mocker.spy(shower_fan_app, "trigger")

    shower_fan_app.on_quite_time_schedule({"trigger": ShowerFan.START_QUIET_PERIOD})

    trigger_spy.assert_has_calls(
        [
            mock.call(ShowerFan.START_QUIET_PERIOD),
        ]
    )

def test_extraction_starts_timeout(
    hass_driver, shower_fan_app: ShowerFan
):
    with hass_driver.setup():
        hass_driver.set_state(FAN, "off")

    shower_fan_app.initialize()
    shower_fan_app.set_extraction()

    run_in_mock = hass_driver.get_mock(HASS_RUN_IN)
    run_in_mock.assert_called_once_with(shower_fan_app.on_timeout, 300)

def test_quiet_extraction_starts_timeout(
    hass_driver, shower_fan_app: ShowerFan, mocker: pytest_mock.MockerFixture
):
    with hass_driver.setup():
        hass_driver.set_state(FAN, "off")

    shower_fan_app.initialize()
    shower_fan_app.set_quiet_extraction()

    run_in_mock = hass_driver.get_mock(HASS_RUN_IN)
    run_in_mock.assert_called_once_with(shower_fan_app.on_timeout, 300)


def test_dryig_starts_long_timeout(
    hass_driver, shower_fan_app: ShowerFan, mocker: pytest_mock.MockerFixture
):
    with hass_driver.setup():
        hass_driver.set_state(FAN, "off")

    shower_fan_app.initialize()
    shower_fan_app.set_drying()

    run_in_mock = hass_driver.get_mock(HASS_RUN_IN)
    run_in_mock.assert_called_once_with(shower_fan_app.on_timeout, 3600)