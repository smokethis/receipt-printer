# SPI Display Setup on Pi Zero 2W (Trixie / kernel 6.x)

Getting `/dev/spidev0.0` working for the ILI9486 display on modern Pi OS requires
a custom device tree overlay. The standard `dtparam=spi=on` and `dtoverlay=spi0-1cs`
both fail silently for two reasons explained below.

## Why the standard approach doesn't work

### 1. `dtparam=spi=on` must be in `[all]`

Lines above any section header in `config.txt` are silently ignored on Trixie.
`dtparam=spi=on` must be inside the `[all]` block to take effect. Even then, see
problem 2.

### 2. `spi0-1cs` only disables CS1, never enables CS0

The `spi0-1cs.dtbo` overlay's job is to enforce "one chip select" by disabling
`spidev@1`. It never sets `spidev@0/status = "okay"`. So the base DT's
`spidev@0` stays `disabled` regardless.

### 3. `compatible = "spidev"` is rejected by kernel 6.x

Even if `spidev@0` were enabled, the base DT has `compatible = "spidev"`. Since
kernel 5.10, this string is explicitly banned from the `spidev` driver's
allowlist. The driver refuses to bind and no `/dev/spidev0.0` is created.

## Diagnostic trail

```bash
# Only spi0.1 (ads7846 touchscreen) ever appears:
ls /sys/bus/spi/devices/
# → spi0.1

# spidev@0 exists in DT but is disabled:
cat /sys/firmware/devicetree/base/soc/spi@7e204000/spidev@0/status
# → disabled

# Compatible string is the banned value:
cat /sys/firmware/devicetree/base/soc/spi@7e204000/spidev@0/compatible
# → spidev
```

## The fix: custom device tree overlay

### 1. Install the device tree compiler

```bash
sudo apt install -y device-tree-compiler
```

### 2. Create `/boot/firmware/overlays/spi0-cs0.dts`

```dts
/dts-v1/;
/plugin/;

/ {
    compatible = "brcm,bcm2835";

    fragment@0 {
        target = <&spi0>;
        __overlay__ {
            #address-cells = <1>;
            #size-cells = <0>;
            status = "okay";

            spidev@0 {
                compatible = "rohm,dh2228fv";
                reg = <0>;
                spi-max-frequency = <16000000>;
                status = "okay";
            };
        };
    };
};
```

`rohm,dh2228fv` is a real device that happens to be in the kernel's spidev
allowlist. It's used here as the conventional placeholder compatible string for
generic SPI userspace access.

### 3. Compile and install

```bash
dtc -@ -I dts -O dtb -o /tmp/spi0-cs0.dtbo /tmp/spi0-cs0.dts
sudo cp /tmp/spi0-cs0.dtbo /boot/firmware/overlays/
```

### 4. Update `config.txt`

In the `[all]` section, replace any `dtparam=spi=on` or `dtoverlay=spi0-1cs`
lines with:

```ini
[all]
enable_uart=1
dtoverlay=spi0-cs0
dtoverlay=ads7846,cs=1,penirq=17,penirq_pull=2,speed=50000,keep_vref_on=1,pmax=255,xohms=60,xmin=200,xmax=3900,ymin=200,ymax=3900
```

### 5. Autoload the spidev module

```bash
echo spidev | sudo tee -a /etc/modules
```

### 6. Reboot

After reboot, verify:

```bash
ls /dev/spidev*
# → /dev/spidev0.0
```

## What this does NOT affect

- The `ads7846` touchscreen overlay stays on SPI0 CS1 (`spi0.1`) and is
  unaffected. Touch input continues to work exactly as before.
- The `spi0-cs0` overlay only adds a child node to the SPI0 controller for CS0.
