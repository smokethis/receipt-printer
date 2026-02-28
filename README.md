# Hardware Notes

## Waveshare 4" LCD (ILI9486) on Raspberry Pi Zero 2 W / Trixie

Waveshare's LCD-show installer script is broken on Trixie - 
writes to /boot/config.txt instead of /boot/firmware/config.txt 
and installs wrong overlay. Use manual fbtft config instead.

Add to /boot/firmware/config.txt:
- Comment out dtoverlay=vc4-kms-v3d and display_auto_detect=1
- Add dtoverlay=fbtft,ili9486,bgr=1,speed=16000000,rotate=90,dc_pin=24,reset_pin=25,led_pin=18
- Add dtoverlay=ads7846,cs=1,penirq=17,penirq_pull=2,speed=50000,keep_vref_on=1,swapxy=1,pmax=255,xohms=60,xmin=200,xmax=3900,ymin=200,ymax=3900

Pin mapping (physical -> GPIO):
- Pin 18 (LCD_RS/DC) -> GPIO24
- Pin 22 (RST) -> GPIO25  
- Pin 11 (TP_IRQ) -> GPIO17