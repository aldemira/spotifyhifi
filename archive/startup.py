#!/usr/bin/env python3

import sys,os
sys.path.append(os.path.abspath("/opt/lcdworks/lib"))
# Get this from https://github.com/the-raspberry-pi-guy/lcd
import drivers
import argparse
import subprocess
import json

def usage():
    print("Usage:", sys.argv[0], " -s|-k")
    print("-s startup ops")
    print("-k shutdown ops")
    sys.exit(1)

def get_my_ip():
    cmd = ['/usr/sbin/ip', '-j', '-o', '-4', 'addr', 'show', 'wlan0']
    res = subprocess.run(cmd,check=True,capture_output=True)
    ip = json.loads(res.stdout.decode('utf-8'))
    #print(ip)
    return ip[0]['addr_info'][0]['local']

def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument('-s', action='store_true', help = 'startup ops',required=False)
    parser.add_argument('-k', action='store_true', help = 'shutdown ops',required=False)
    args = parser.parse_args()

    display = drivers.Lcd()
    display.lcd_backlight(0) 

    if args.s:
        display.lcd_display_string("Aldemir HiFi...",1)
        display.lcd_display_string(get_my_ip(),2)
    elif args.k:
        display.lcd_clear()
    else:
        usage()

if __name__ == '__main__':
     main()


