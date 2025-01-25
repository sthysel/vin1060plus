# 10moons-driver-vin1060plus

> Forked from [f-caro](https://github.com/f-caro/10moons-driver-vin1060plus) which itself is forked from [Alex-S-V](https://github.com/alex-s-v/10moons-driver)

![Aliexpress Graphics Tablet VINSA 1060plus](http://eng.10moons.com/upload/2018/06/11/201806112311552.jpg)

[10moons Graphics Tablet product homepage](http://eng.10moons.com/info5494.html)

[Aliexpress equivalent sold under VINSA brand. --- Download User Manual](http://blog.ping-it.cn/h/8/sms.pdf)

This is a Simple driver with pyUSB code modified to handle the interaction events of the VINSA 1060Plus graphics tablet, that includes a passive two button pen.

Linux detects it as a T501 GoTOP tablet, hence pyUSB library is able to interface with the tablet device.

## About

Driver which provides basic functionality for VINSA 1060plus T501 tablet:

* 12 buttons on the tablet itself
* Correct X and Y positioning (two active area modes present:  Android Active Area & Full Tablet Active Area)
* Pressure sensitivity ( able to read the values, but unable to pass it onto Graphics Software )

Tablet has 4096 levels in both axes and 2047 levels of pressure ( Product description says 8092, but actual output readings are 2047 max).

## The progress so far

With linux Kernel 5+,  the graphics tablet should be detected but pen movement is restricted to Android Active Area (the small area on the tablet).  That driver was added to the kernel but interacts with the T503 chipset.
Thanks to [Digimend - https://github.com/DIGImend](https://github.com/DIGImend) for providing valuable functionality not just to 10moons Tablets, but to a variety of other popular Tablets.

Unfortuantely, Mr Digimend has chosen not to further develop the driver applicable to VINSA 1060plus, due to the inaccurate information transmitted between the T501 chipset and the USB driver --> [Live recording of Mr DIGIMEND working on 10moons tablet debug and analysis.  Awesome to see the master at work :)](https://www.youtube.com/watch?v=WmnSwjlpRBE).

So an alternative workaround was needed.  In steps Alex-S-V with his pyUSB implementation of the T503 driver --- together with the [Digimend 10moons-Probe tool](https://github.com/DIGImend/10moons-tools),  it has the particular effect of switching the Graphics Tablet out of AndroidActiveArea Mode and into FullTabletArea mode.  I will need to ask the original author (Mr.Digimend) how he identified the hex string to transmit to the tablet [ (probe.c src: line#165 ---> SET_REPORT(0x0308, 0x08, 0x04, 0x1d, 0x01, 0xff, 0xff, 0x06, 0x2e); ) ] (<https://github.com/DIGImend/10moons-tools/blob/6cc7c40c50cb58fefe4e732f6a94fac75c9e4859/10moons-probe.c#L165>)

The person to discover this "hack" was Mr.Digimend himself and thanks to the [Youtube video that he uploaded time-stamp @1:40.11](https://youtu.be/WmnSwjlpRBE?t=6011) he shows that usbhid-dump  output when in Android-Active-Area Mode (8 byte TX)  vs  the required  Full-Tablet-Active-Area mode ( 64 byte TX).

## How to install

> ⚠️ **You need to connect your tablet and run the driver prior to launching a drawing software otherwise the device will not be recognized by it**

1. Clone this repo recursively

  ```shell
  git clone --recursive https://github.com/F33RNI/10moons-driver-vin1060plus.git
  cd https://github.com/F33RNI/10moons-driver-vin1060plus
  ```

2. Build 10moons-tools

  ```shell
  cd 10moons-tools
  autoreconf -i -f
  ./configure
  make
  cd ..
  ```

3. Create python's virtual environment and install requirements

  > NOTE: Tested on Python 3.12.7

  ```shell
  python -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```

4. Connect tablet and wait a bit

5. Find bus and device IDs

  ```shell
  lsusb | grep "08f2:6811"
  ```

6. Run 10moons-probe

  ```shell
  sudo 10moons-tools/10moons-probe <Bus ID> <Device ID>
  ```

  Or you can inline with `lsusb` like so

  ```shell
  sudo 10moons-tools/10moons-probe `lsusb | grep "08f2:6811" | awk '{print $2}' | sed 's/^0*//'` `lsusb | grep "08f2:6811" | awk '{print $4}' | tr -d ':' | sed 's/^0*//'`
  ```

7. Start driver in debug mode

  ```shell
  sudo venv/bin/python driver-vin1060plus.py -d
  ```

  > NOTE: You can provide path to config file with `-c [CONFIG]` argument. Also you can enable debug mode in config file

8. Calibrate pressure

* Hover pen over tablet without touching it and write down `[RAW] Pressure: <-` value
* Now, touch tablet as hard as you can and write down `[RAW] Pressure:` value again
* Stop driver by pressing `CTRL` + `C`
* Put these values into `pressure_in_min` and `pressure_in_max` inside config file
* Start driver again in debug mode
* Determine pressure at which you want touch / release to be registered using value from `[OUT] X: ..., Y: ..., pressure: <-`
* Stop driver by pressing `CTRL` + `C`
* Edit `pressure_threshold_press` and `pressure_threshold_release` in config file if needed

9. Start driver in normal mode

  ```shell
  sudo venv/bin/python driver-vin1060plus.py
  ```

  > NOTE: You can provide path to config file with `-c [CONFIG]` argument
  
### In case of multiple monitors connected

> Not tested
  
1. run `xrandr` to identify the name of the Display that you want to limit your tablet x & y coords.

```
e.g.  DisplayPort-1
```

2. run `xinput` to list all virtual devices,  identify the virtual core pointer associated with tablet pen

```
e.g.   ↳ 10moons-pen Pen (0)                      id=17 [slave  pointer  (2)]
```

3. configure xinput to restrict x&y coords to relevant monitor

```
e.g.  xinput map-to-output 17 DisplayPort-1
```

## Configuring tablet

Configuration of the driver placed in `config-vin1060plus.yml` file

You can provide path to it using `-c` argument

> Pls read config file with it's comments for more info

## Changing Button/Key shortcuts

`config-vin1060plus.yml` contains a Key code list ( variable `tablet_buttons` ) that allows the user to edit the 12 buttons found on the left-side of the graphics tablet.

To list all the possible Key codes you may run:

```shell
python -c "from evdev import ecodes; print([x for x in dir(ecodes) if 'KEY' in x])"
```

`config-vin1060plus.yml` also contains a BTN code list ( variable `pen_buttons` ) that allows the user to edit the 2 buttons found on passive stylus pen.

To list all the possible Mouse/Stylus BTN codes you may run:

```shell
python -c "from evdev import ecodes; print([x for x in dir(ecodes) if 'BTN' in x])"
```

> Useful Doc explaining how the Kernel categorises and uses those ecodes :
  <https://www.kernel.org/doc/Documentation/input/event-codes.txt>
>
> Input-Event-codes Src from Github :
  <https://github.com/torvalds/linux/blob/master/include/uapi/linux/input-event-codes.h>

You can also use multiple keys at the same time separated with `+`

For example, to bind `CTRL` + `Z` on `CTRL` button (bottom left):

```yaml
actions:
    ...
    tablet_buttons:
        ...
        # Labelled as 'CTRL'
        63283: KEY_LEFTCTRL+KEY_Z
```

## Credits

> From f-caro's repo:
>
> Some parts of code are taken from:
  <https://github.com/Mantaseus/Huion_Kamvas_Linux>
>
> Other parts taken from:  
  <https://github.com/alex-s-v/10moons-driver>
>
> All inspiration tricks and tactics taken from :
  <https://github.com/DIGImend/10moons-tools>
>
> Together with howto videos from DigiMend :  
  <https://www.youtube.com/watch?v=WmnSwjlpRBE>
>
> DigiMend conference talk on interfacing grahics tablets in Linux:  
  <https://www.youtube.com/watch?v=Qi73_QFSlpo>
>
> The forum that got me started with finding a simple solution to my cheap graphics tablet purchase:  
>
> "Please Add support for 10moons 10*6 inch Graphics Tablet #182"
  <https://github.com/DIGImend/digimend-kernel-drivers/issues/182>

## TODOS

* Map the 10 "virtual buttons" found on the top-side of the graphics tablet active area.  `( mute, vol_dwn, vol_up, music_player, play_pause, prev_song, next_song, home_btn, calc_btn, desktop_view )`

* Allow the Graphics App (e.g. Gimp, Scribus, Pix, Inkscape etc. ) to make use of the "pressure sensitivity" measurement

* Use its linear Z-axis "pressure sensitivity" measurements and map it to a non-linear function (maybe bezzier-curve) that simulates more natural pen strokes

* Is there a way with [pyUSB transfer bytecode]() to the VINSA1060plus T501 microcontroller that can enable one to skip the `./10moons-probe` code execution ?!?!

# Useful references

* Docs to Python source code of UInput class :  <https://python-evdev.readthedocs.io/en/latest/_modules/evdev/uinput.html>

* pyUSB tutorial howto : <https://github.com/pyusb/pyusb/blob/master/docs/tutorial.rst>

* wireshark tips on howto filter USB traffic ( [better to use the video from Digimend](https://www.youtube.com/watch?v=WmnSwjlpRBE) ) : <https://osqa-ask.wireshark.org/questions/53919/how-can-i-precisely-specify-a-usb-device-to-capture-with-tshark/>  :::   howto configure in Linux : <https://wiki.wireshark.org/CaptureSetup/USB>  :::  tutorial with step-by-step screenshots : <https://github.com/liquidctl/liquidctl/blob/main/docs/developer/capturing-usb-traffic.md>

* PDF USB.org  Device Class Definition for Human Interface Devices Firmware Specification : <https://www.usb.org/sites/default/files/documents/hid1_11.pdf>

* Digimend howto do diagnostics when trying out new tablets in Linux : <http://digimend.github.io/support/howto/trbl/diagnostics/>

* 10moons 10x6 tablet homepage : <http://eng.10moons.com/info5494.html>  :::  picture revealing possible circuit schematic ??  <http://eng.10moons.com/info5494.html>

* libUSB C library initialization/deinitialization : <https://libusb.sourceforge.io/api-1.0/group__libusb__lib.html#details>

* USB in a Nutshell - tutorial/howtos/references : <https://www.beyondlogic.org/usbnutshell/usb1.shtml>
