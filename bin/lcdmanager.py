#!/usr/bin/env python3

import sys,os
sys.path.append(os.path.abspath("/opt/lcdworks/lib"))
# Get this from https://github.com/the-raspberry-pi-guy/lcd
import drivers
import argparse
import subprocess
import json
import signal
import logging
from logging import config
import lockfile
import socket
from queue import Queue
#from threading import Thread
from _thread import *
import daemon, daemon.pidfile

socket_path = "/var/run"

LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'verbose': {
            'format': '%(module)s: %(levelname)s %(message)s'
            },
        },
    'handlers': {
        #'stdout': {
        #    'class': 'logging.StreamHandler',
        #    'stream': sys.stdout,
        #    'formatter': 'verbose',
        #    },
        'daemon': {
            'class': 'logging.handlers.SysLogHandler',
            'address': '/dev/log',
            'facility': "daemon",
            'formatter': 'verbose',
            },
        },
    'loggers': {
        'aldemir-hifi': {
            'handlers': ['daemon',],
            'level': logging.INFO,
            'propagate': True,
            },
        }
    }

config.dictConfig(LOGGING)
logger = logging.getLogger("aldemir-hifi")

def shutdown(signal, frame):
    logger.debug('Shutting down!')
    display = drivers.Lcd()
    display.lcd_backlight(0)
    display.lcd_clear()
    os.unlink(socket_path + '/' + os.path.basename(sys.argv[0]))
    sys.exit(0)

def get_my_ip():
    cmd = ['/usr/sbin/ip', '-j', '-o', '-4', 'addr', 'show', 'wlan0']
    res = subprocess.run(cmd,check=True,capture_output=True)
    ip = json.loads(res.stdout.decode('utf-8'))
    #print(ip)
    return ip[0]['addr_info'][0]['local']

def lcd_manager_writer(queue, display):
    mydict = {}
    try:
        mydict = json.loads(queue.get(block=False))
    except:
        logger.error("Malformed data")
        return
    display.lcd_clear()
    display.lcd_backlight(1)
    display.lcd_display_string(mydict[0], 1)
    display.lcd_display_string(mydict[1], 2)

def main():
    logger.info('Starting up...')

    display = drivers.Lcd()
    display.lcd_backlight(0)

    display.lcd_display_string("Aldemir HiFi...",1)
    display.lcd_display_string(get_my_ip(),2)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    # TODO change this os.path.basename thingy
    mysocket = socket_path + '/' + os.path.basename(sys.argv[0])
    server.bind(mysocket)
    server.listen(1)

    logger.info('Server is listening for incoming connections...')
    while True:
        connection, client_address = server.accept()

        myq = Queue()

        logger.info('Connection from %s' % str(connection).split(", ")[0][-4:])

        # receive data from the client
        while True:
            if not myq.empty():
                try:
                    start_new_thread(lcd_manager_writer, (myq,display,))
                except Exception as ex:
                    logging.exception("aaa")
            data = connection.recv(1024)
            if not data:
                break
            logger.debug('Received data: %s' % data.decode('utf-8'))
            myq.put(data)

            # Send a response back to the client
            response = 'ack!'
            connection.sendall(response.encode())
        connection.close()
        # remove the socket file
    os.unlink(mysocket)

if __name__ == '__main__':
    myname = os.path.basename(sys.argv[0])
    try:
        # Delete the leftover socket (if it exists)
        os.unlink('/var/run/%s' % myname)
        logger.info("Deleting /var/run/%s" % myname)
    except:
        pass
    with daemon.DaemonContext(
            pidfile=daemon.pidfile.TimeoutPIDLockFile('/var/run/%s.pid' % myname),
            signal_map={
                signal.SIGTERM: shutdown,
                signal.SIGTSTP: shutdown
                }
            ):
        main()
