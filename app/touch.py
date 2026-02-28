import select

try:
    import evdev
    from evdev import InputDevice, ecodes
    _EVDEV_AVAILABLE = True
except ImportError:
    _EVDEV_AVAILABLE = False

from app.display import DISPLAY_WIDTH, DISPLAY_HEIGHT

_RAW_MIN = 200
_RAW_MAX = 3900

_device = None
_cur_x = 0
_cur_y = 0


def _get_device():
    global _device
    if _device is not None:
        return _device
    for path in evdev.list_devices():
        dev = InputDevice(path)
        if 'ADS7846' in dev.name:
            _device = dev
            return _device
    return None


def _map(raw, display_max):
    raw = max(_RAW_MIN, min(_RAW_MAX, raw))
    return int((raw - _RAW_MIN) / (_RAW_MAX - _RAW_MIN) * display_max)


def poll():
    """Return (x, y) display coordinates on tap, or None if no tap."""
    if not _EVDEV_AVAILABLE:
        return None

    global _cur_x, _cur_y

    device = _get_device()
    if device is None:
        return None

    r, _, _ = select.select([device.fd], [], [], 0)
    if not r:
        return None

    tap = None
    for event in device.read():
        if event.type == ecodes.EV_ABS:
            if event.code == ecodes.ABS_X:
                _cur_x = event.value
            elif event.code == ecodes.ABS_Y:
                _cur_y = event.value
        elif event.type == ecodes.EV_KEY:
            if event.code == ecodes.BTN_TOUCH and event.value == 0:
                # swapxy=1: device ABS_X → display Y, device ABS_Y → display X
                disp_x = _map(_cur_y, DISPLAY_WIDTH - 1)
                disp_y = _map(_cur_x, DISPLAY_HEIGHT - 1)
                tap = (disp_x, disp_y)
    return tap
