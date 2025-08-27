"""
Copyright (C) 2019-2025 Alexandr Vasilyev, f-caro, Fern Lane and other
10moons-driver and this fork contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import click
from array import array
from typing import Any
from loguru import logger

import usb
import yaml
from evdev import AbsInfo, UInput, ecodes


def _parse_config(config_path: str) -> dict[str, Any]:
    """Parses config from YAML file"""
    with open(config_path, "r", encoding="utf-8") as file_io:
        config = yaml.load(file_io, yaml.FullLoader)
    return config


def _prepare_device(
    vendor_id: int, product_id: int, reports: list[dict[str | int, list[int]]]
) -> tuple[usb.core.Device, usb.core.Endpoint]:
    """Finds and resets USB device"""
    dev = usb.core.find(idVendor=vendor_id, idProduct=product_id)
    logger.debug(str(dev))

    if not isinstance(dev, usb.core.Device):
        raise Exception("USB device instance is not usb.core.Device type")

    dev.reset()

    logger.info("Detaching kernel driver from USB device")
    for iface_id in [0, 1, 2]:
        if dev.is_kernel_driver_active(iface_id):
            logger.debug(f"Detaching kernel driver from interface: {iface_id}")
            dev.detach_kernel_driver(iface_id)

    logger.info("Setting new configuration to USB device")
    dev.set_configuration()

    interface = 2
    logger.info(f"Claiming USB interface {interface}")
    usb.util.claim_interface(dev, interface)

    def _set_report(w_value, report_data) -> None:
        logger.debug(f"Sending SET_REPORT: {w_value}, {report_data}")
        dev.ctrl_transfer(0x21, 9, w_value, interface, report_data, timeout=250)

    logger.info("Sending reports")
    for report in reports:
        for w_value, report_data in report.items():
            if isinstance(w_value, str):
                w_value = int(w_value)
            _set_report(w_value, report_data)

    endpoint = dev.interfaces()[1].endpoints()
    logger.debug(str(endpoint))

    return dev, endpoint


def _parse_ecodes(
    actions: dict[str | int, str], ensure_int: bool = True
) -> dict[Any, list[int]]:
    ecodes_ = {}
    for key_code, action in actions.items():
        if ensure_int and isinstance(key_code, str):
            key_code = int(key_code)
        ecodes_[key_code] = [
            ecodes.ecodes[code_part] for code_part in action.split("+")
        ]
    return ecodes_


def _create_uinputs(
    xinput_name: str,
    pen_ecodes: dict[int, list[int]],
    pen_touch_ecodes: dict[str, list[int]],
    btn_ecodes: dict[int, list[int]],
    pen_config: dict[str, int | bool],
) -> tuple[UInput, UInput]:
    pen_codes = []
    for value in pen_ecodes.values():
        pen_codes.extend(value)
    for value in pen_touch_ecodes.values():
        pen_codes.extend(value)
    btn_codes = []
    for value in btn_ecodes.values():
        btn_codes.extend(value)

    abs_info_x = AbsInfo(
        0,
        pen_config.get("min_x", 0),
        pen_config.get("max_x", 4095),
        0,
        0,
        pen_config.get("resolution_x", 1),
    )
    abs_info_y = AbsInfo(
        0,
        pen_config.get("min_y", 0),
        pen_config.get("max_y", 4095),
        0,
        0,
        pen_config.get("resolution_y", 1),
    )
    pressure_info = AbsInfo(
        0,
        pen_config.get("pressure_out_min", 0),
        pen_config.get("pressure_out_max", 2047),
        0,
        0,
        pen_config.get("resolution_pressure", 1),
    )
    pen_events = {
        ecodes.EV_KEY: pen_codes,
        ecodes.EV_ABS: [
            (ecodes.ABS_X, abs_info_x),
            (ecodes.ABS_Y, abs_info_y),
            (ecodes.ABS_PRESSURE, pressure_info),
        ],
    }
    logger.debug(f"PEN events: {pen_events}")

    btn_events = {ecodes.EV_KEY: btn_codes}
    logger.debug(f"BTN events: {btn_events}")

    logger.info(f"Creating UInput {xinput_name}")
    virtual_pen = UInput(events=pen_events, name=xinput_name, version=0x3)
    logger.debug(str(virtual_pen))
    logger.debug(virtual_pen.capabilities(verbose=True).keys())
    logger.debug(virtual_pen.capabilities(verbose=True))

    logger.info(f"Creating UInput {xinput_name}_buttons")
    virtual_btn = UInput(events=btn_events, name=xinput_name + "_buttons", version=0x3)
    logger.debug(str(virtual_btn))
    logger.debug(virtual_btn.capabilities(verbose=True).keys())
    logger.debug(virtual_btn.capabilities(verbose=True))

    return virtual_pen, virtual_btn


def _write_ecode(device: UInput, ecodes_: list[int], press: bool = True) -> None:
    for ecode_ in ecodes_:
        logger.debug(f"{'Pressing' if press else 'Releasing'} ecode: {ecode_}")
        device.write(ecodes.EV_KEY, ecode_, 1 if press else 0)
    device.syn()


@click.command()
@click.option(
    "-c",
    "--config",
    "config_path",
    show_default=True,
    help="Path to config file",
)
@click.option(
    "-d",
    "--debug",
    is_flag=True,
    default=False,
    help="Enable debug logs (overrides config)",
)
def cli(config_path: str, debug: bool):
    """VINSA 1060 Plus driver"""

    config = _parse_config(config_path)

    logger.debug("DEBUG MODE ENABLED")
    logger.debug(f"Parsed config: {config}")

    actions_conf = config.get("actions", {})
    pen_ecodes = _parse_ecodes(actions_conf.get("pen_buttons", {}))
    logger.debug(f"Pen ecodes: {pen_ecodes}")
    btn_ecodes = _parse_ecodes(actions_conf.get("tablet_buttons", {}))
    logger.debug(f"Button ecodes: {btn_ecodes}")
    pen_touch_ecodes = _parse_ecodes(
        actions_conf.get("pen_touch", {}), ensure_int=False
    )
    logger.debug(f"Pen touch ecodes: {pen_touch_ecodes}")

    try:
        dev, endpoint = _prepare_device(
            config["vendor_id"], config["product_id"], config["reports"]
        )
    except Exception as e:
        logger.error("Error preparing tablet USB device", exc_info=e)
        logger.info(
            "TIP: Make sure that tablet is connected and you run this script as root"
        )
        return

    pen_config = config.get("pen", {})

    try:
        virtual_pen, virtual_btn = _create_uinputs(
            config.get("xinput_name", "10moons-pen"),
            pen_ecodes,
            pen_touch_ecodes,
            btn_ecodes,
            pen_config,
        )
    except Exception as e:
        logger.error("Error creating virtual input devices", exc_info=e)
        logger.info("TIP: Make sure to run this script as root")
        return

    swap_axes = pen_config.get("swap_axes")
    invert_x = pen_config.get("invert_x")
    invert_y = pen_config.get("invert_y")
    min_x = pen_config.get("min_x", 0)
    max_x = pen_config.get("max_x", 4095)
    min_y = pen_config.get("min_y", 0)
    max_y = pen_config.get("max_y", 4095)
    pressure_in_min = pen_config.get("pressure_in_min", 2047)
    pressure_in_max = pen_config.get("pressure_in_max", 0)
    pressure_out_min = pen_config.get("pressure_out_min", 0)
    pressure_out_max = pen_config.get("pressure_out_max", 2047)
    pressure_threshold_press = pen_config.get("pressure_threshold_press", 300)
    pressure_threshold_release = pen_config.get("pressure_threshold_release", 200)

    touch = False
    btn_pen_key_last = None
    btn_tablet_key_last = None

    logger.info("Entering main loop. Press CTRL+C to stop driver and exit")
    while True:
        try:
            data = dev.read(endpoint.bEndpointAddress, endpoint.wMaxPacketSize)  # pyright: ignore
            logger.debug(f"[RAW] USB data: {data}")

            if not isinstance(data, array):
                raise Exception("USB data type is not array.array")

            key_raw = int.from_bytes(data[11:13], byteorder="big")
            logger.debug(f"[RAW] Tablet key: {key_raw}")

            if btn_tablet_key_last is not None and key_raw != btn_tablet_key_last:
                logger.debug(f"Tablet key {btn_tablet_key_last} released")
                _write_ecode(
                    virtual_btn, btn_ecodes.get(btn_tablet_key_last, []), press=False
                )
                btn_tablet_key_last = None

            if key_raw in btn_ecodes:
                logger.debug(f"Tablet key {key_raw} pressed")
                _write_ecode(virtual_btn, btn_ecodes.get(key_raw, []))
                btn_tablet_key_last = key_raw

            pen_action = data[5]
            logger.debug(f"[RAW] pen action: {pen_action}")
            if pen_action not in [3, 4, 5, 6]:
                logger.debug("Ignoring this pen action")
                continue

            x = int.from_bytes(data[3:5] if swap_axes else data[1:3], byteorder="big")
            y = int.from_bytes(data[1:3] if swap_axes else data[3:5], byteorder="big")
            pressure_raw = int.from_bytes(data[5:7], byteorder="big")
            logger.debug(
                f"[RAW] X: {x}, Y: {y}, swapped: {'true' if swap_axes else 'false'}"
            )
            logger.debug(f"[RAW] Pressure: {pressure_raw}")

            pen_btn_raw = data
            logger.debug(f"[RAW] Pen button: {pen_btn_raw}")

            if x <= min_x or x >= max_x or y <= min_y or y >= max_y:
                logger.debug("Position is outside allowed range. Ignoring")
                continue

            if invert_x:
                x = max_x - x
            if invert_y:
                y = max_y - y

            pressure = pressure_raw - pressure_in_min
            pressure *= pressure_out_max - pressure_out_min
            pressure /= pressure_in_max - pressure_in_min
            pressure += pressure_out_min
            pressure = int(max(pressure_out_min, min(pressure, pressure_out_max)))

            if not touch and pressure > pressure_threshold_press:
                touch = True
            elif touch and pressure < pressure_threshold_release:
                touch = False

            logger.debug(f"[OUT] X: {x}, Y: {y}, pressure: {pressure}, touch: {touch}")

            for ecode_ in pen_touch_ecodes.get("down" if touch else "up", []):
                virtual_pen.write(ecodes.EV_KEY, ecode_, 1 if touch else 0)
            virtual_pen.syn()

            virtual_pen.write(ecodes.EV_ABS, ecodes.ABS_X, x)
            virtual_pen.write(ecodes.EV_ABS, ecodes.ABS_Y, y)
            virtual_pen.write(ecodes.EV_ABS, ecodes.ABS_PRESSURE, pressure)
            virtual_pen.syn()

            if btn_pen_key_last is not None and pen_btn_raw != btn_pen_key_last:
                logger.debug("Pen button released")
                _write_ecode(
                    virtual_pen, pen_ecodes.get(btn_pen_key_last, []), press=False
                )
                btn_pen_key_last = None

            if btn_pen_key_last is None and pen_btn_raw in pen_ecodes:
                logger.debug("Pen button pressed")
                _write_ecode(virtual_pen, pen_ecodes.get(pen_btn_raw, []))
                btn_pen_key_last = pen_btn_raw

        except usb.core.USBError as e:
            if e.args == 110:
                continue
            if e.args == 19:
                logger.warning("Device disconnected")
            else:
                logger.warning(f"USB error: {e}")
            break

        except (SystemExit, KeyboardInterrupt):
            logger.warning("Exiting ...")
            break

        except Exception as e:
            logger.error(f"Unknown error: {e}", exc_info=e)
            break

    try:
        if touch:
            for ecode_ in pen_touch_ecodes.get("up", []):
                virtual_pen.write(ecodes.EV_KEY, ecode_, 0)
            virtual_pen.syn()
        if btn_pen_key_last is not None:
            _write_ecode(virtual_pen, pen_ecodes.get(btn_pen_key_last, []), press=False)
        if btn_tablet_key_last is not None:
            _write_ecode(
                virtual_btn, btn_ecodes.get(btn_tablet_key_last, []), press=False
            )
    except Exception as e:
        logger.warning(f"Unable to release pen and tablet keys: {e}")

    logger.info("Closing virtual input devices")
    try:
        virtual_pen.close()
        virtual_btn.close()
    except Exception as e:
        logger.warning(f"Unable to close virtual input devices: {e}")

    logger.info("Exited!")


if __name__ == "__main__":
    cli()
