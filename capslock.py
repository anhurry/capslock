#!/usr/bin/python3
from select import select

from evdev import InputDevice, ecodes, UInput, InputEvent, list_devices
from inotify_simple import INotify, flags


def send_keys(keys: list):
    for k in keys:
        _input.write(ecodes.EV_KEY, k, 1)
        _input.syn()
    for k in reversed(keys):
        _input.write(ecodes.EV_KEY, k, 0)
        _input.syn()


def send_event(event: InputEvent):
    _input.write_event(event)
    _input.syn()


def key_code_id(*key_codes):
    return '_'.join([str(k) for k in key_codes])


def in_device_list(path, devices):
    for device in devices:
        if device.path == path:
            return True
    return False


def is_keyboard_device(device):
    """Guess the device is a keyboard or not"""
    capabilities = device.capabilities(verbose=False)
    if 1 not in capabilities:
        return False
    supported_keys = capabilities[1]
    if ecodes.KEY_SPACE not in supported_keys or \
            ecodes.KEY_A not in supported_keys or \
            ecodes.KEY_Z not in supported_keys:
        # Not support common keys. Not keyboard.
        return False
    if ecodes.BTN_MOUSE in supported_keys:
        # Mouse.
        return False
    # Otherwise, its keyboard!
    return True


def add_new_device(devices, inotify):
    new_devices = []
    for event in inotify.read():
        new_device = InputDevice("/dev/input/" + event.name)
        if is_keyboard_device(new_device) and not in_device_list(new_device.path, devices):
            try:
                new_device.grab()
            except IOError:
                # Ignore errors on new devices
                print("IOError when grabbing new device: " + str(new_device.name))
                continue
            devices.append(new_device)
            new_devices.append(new_device)
    return new_devices


def print_device_list(devices):
    device_format = '{1.path:<20} {1.name:<35} {1.phys}'
    device_lines = [device_format.format(n, d) for n, d in enumerate(devices)]
    print('-' * len(max(device_lines, key=len)))
    print('{:<20} {:<35} {}'.format('Device', 'Name', 'Phys'))
    print('-' * len(max(device_lines, key=len)))
    print('\n'.join(device_lines))
    print('')


def remove_device(devices, device):
    devices.remove(device)
    try:
        device.ungrab()
    except OSError as e:
        pass


def device_filter(devices):
    keyboards = []
    for device in devices:
        if is_keyboard_device(device):
            keyboards.append(device)
    return keyboards


def active_keys_contains_capslock(active_keys):
    try:
        active_keys.index(ecodes.KEY_CAPSLOCK)
        return True
    except ValueError:
        return False


devices = [InputDevice(path) for path in list_devices()]
devices = device_filter(devices)
for dev in devices:
    dev.grab()
inotify = INotify()
inotify.add_watch('/dev/input', flags.CREATE | flags.ATTRIB)
_input = UInput()
_mapping_map = {
    key_code_id(ecodes.KEY_E, ecodes.KEY_CAPSLOCK): [ecodes.KEY_UP],
    key_code_id(ecodes.KEY_D, ecodes.KEY_CAPSLOCK): [ecodes.KEY_DOWN],
    key_code_id(ecodes.KEY_S, ecodes.KEY_CAPSLOCK): [ecodes.KEY_LEFT],
    key_code_id(ecodes.KEY_F, ecodes.KEY_CAPSLOCK): [ecodes.KEY_RIGHT],
    key_code_id(ecodes.KEY_I, ecodes.KEY_CAPSLOCK): [ecodes.KEY_LEFTSHIFT, ecodes.KEY_UP],
    key_code_id(ecodes.KEY_K, ecodes.KEY_CAPSLOCK): [ecodes.KEY_LEFTSHIFT, ecodes.KEY_DOWN],
    key_code_id(ecodes.KEY_J, ecodes.KEY_CAPSLOCK): [ecodes.KEY_LEFTSHIFT, ecodes.KEY_LEFT],
    key_code_id(ecodes.KEY_L, ecodes.KEY_CAPSLOCK): [ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHT],
    key_code_id(ecodes.KEY_P, ecodes.KEY_CAPSLOCK): [ecodes.KEY_HOME],
    key_code_id(ecodes.KEY_SEMICOLON, ecodes.KEY_CAPSLOCK): [ecodes.KEY_END],
    key_code_id(ecodes.KEY_U, ecodes.KEY_CAPSLOCK): [ecodes.KEY_LEFTSHIFT, ecodes.KEY_HOME],
    key_code_id(ecodes.KEY_O, ecodes.KEY_CAPSLOCK): [ecodes.KEY_LEFTSHIFT, ecodes.KEY_END],
    key_code_id(ecodes.KEY_ENTER, ecodes.KEY_CAPSLOCK): [ecodes.KEY_END, ecodes.KEY_ENTER],
    key_code_id(ecodes.KEY_W, ecodes.KEY_CAPSLOCK): [ecodes.KEY_BACKSPACE],
    key_code_id(ecodes.KEY_R, ecodes.KEY_CAPSLOCK): [ecodes.KEY_DELETE],
    key_code_id(ecodes.KEY_DOT, ecodes.KEY_CAPSLOCK): [ecodes.KEY_PAGEDOWN],
    key_code_id(ecodes.KEY_COMMA, ecodes.KEY_CAPSLOCK): [ecodes.KEY_PAGEUP],
    key_code_id(ecodes.KEY_H, ecodes.KEY_CAPSLOCK): [ecodes.KEY_TAB],
    key_code_id(ecodes.KEY_BACKSPACE, ecodes.KEY_CAPSLOCK): [ecodes.KEY_END, ecodes.KEY_LEFTSHIFT, ecodes.KEY_HOME,
                                                             ecodes.KEY_BACKSPACE],
}

capslock_pressed = False
try:
    while True:
        try:
            waitables = devices[:]
            waitables.append(inotify.fd)
            r, w, x = select(waitables, [], [])
            for waitable in r:
                if isinstance(waitable, InputDevice):
                    for event in waitable.read():
                        if event.type == ecodes.EV_KEY:
                            active_keys = [str(k) for k in waitable.active_keys()]
                            if event.code == ecodes.KEY_CAPSLOCK and event.value == 1:
                                capslock_pressed = True
                            if event.code == ecodes.KEY_CAPSLOCK and event.value == 2:
                                capslock_pressed = False
                            keys = _mapping_map.get('_'.join(active_keys), None)
                            if keys:
                                capslock_pressed = False
                                send_keys(keys)
                            elif active_keys_contains_capslock(active_keys):
                                capslock_pressed = False
                            elif event.code == ecodes.KEY_CAPSLOCK and event.value == 0 and capslock_pressed:
                                send_keys([ecodes.KEY_CAPSLOCK])
                            elif event.code != ecodes.KEY_CAPSLOCK:
                                send_event(event)
                        else:
                            send_event(event)
                else:
                    new_devices = add_new_device(devices, inotify)
                    if new_devices:
                        print("Okay, now enable remapping on the following new device(s):\n")
                        print_device_list(new_devices)
        except OSError:
            if isinstance(waitable, InputDevice):
                remove_device(devices, waitable)
                print("Device removed: " + str(waitable.name))
        except KeyboardInterrupt:
            print("Received an interrupt, exiting.")
            break
finally:
    for device in devices:
        try:
            device.ungrab()
        except OSError as e:
            pass
    inotify.close()
