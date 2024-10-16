#!/usr/bin/env python3

import sys,os
sys.path.append(os.path.abspath("/opt/lcdworks/lib"))
# Get this from https://github.com/the-raspberry-pi-guy/lcd
import drivers
import subprocess
import json
import signal
import logging
from logging import config
import lockfile
import socket
from queue import Queue
import threading
from threading import Thread
import daemon, daemon.pidfile
from time import perf_counter as pc, sleep

socket_path = "/var/run"
thread_local = threading.local()

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


def get_display():
    if not hasattr(thread_local, "display"):
        thread_local.display = drivers.Lcd()
    return thread_local.display

def shutdown(signal, frame):
    logger.info('Shutting down!')
    for thread in threading.enumerate():
        thread.kill()
    display = get_display()
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

def lcd_manager_writer(data, display, logger):
    mydict = {}
    try:
        mydict = json.loads(data)
    except:
        logger.info("Malformed data %s" % mydict)
        return
    display.lcd_clear()
    display.lcd_backlight(1)
    long_string(display,mydict[0], 1)
    long_string(display,mydict[1], 2)

def init_screen(display):
    display.lcd_backlight(0)

    display.lcd_display_string("Aldemir HiFi...",1)
    display.lcd_display_string(get_my_ip(),2)


def handle_conn(logger,server,myQueue):
    try:
        connection, client_address = server.accept()
        logger.info('Connection from %s' % str(connection).split(", ")[0][-4:])
        while True:
            data = connection.recv(1024)
            if not data:
                break
            logger.info('Received data: %s' % data.decode('utf-8'))
            myQueue.put(data)
            # Send a response back to the client
            response = 'ack!'
            connection.sendall(response.encode())
        connection.close()
    except:
        logger.exception()
        connection.close()



# Also pulled from https://github.com/the-raspberry-pi-guy/lcd
def long_string(display, text='', num_line=1, num_cols=16):
    """
    Parameters: (driver, string to print, number of line to print, number of columns of your display)
    Return: This function send to display your scrolling string.
    """
    if len(text) > num_cols:
        display.lcd_display_string(text[:num_cols], num_line)
        sleep(1)
        for i in range(len(text) - num_cols + 1):
            text_to_print = text[i:i+num_cols]
            display.lcd_display_string(text_to_print, num_line)
            sleep(0.2)
        sleep(1)
    else:
        display.lcd_display_string(text, num_line)

def main():
    config.dictConfig(LOGGING)
    logger = logging.getLogger("aldemir-hifi")
    timeout = 1800
    logger.info('Starting up...')

    display = get_display()
    init_screen(display)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    # TODO change this os.path.basename thingy
    mysocket = socket_path + '/' + os.path.basename(sys.argv[0])
    server.bind(mysocket)
    server.listen(1)

    last_screen_message = pc()

    myq = Queue()
    logger.info('Server is listening for incoming connections...')

    connThread = Thread(target=handle_conn,args=(logger,server,myq,))
    connThread.start()
    # Main server loop
    while True:
        # Connection handling
        if not connThread.is_alive():
            logger.info("Starting connection thread")
            connThread = Thread(target=handle_conn,args=(logger,server,myq,))
            connThread.start()

        #logger.debug("Timeout: %d" % int(pc() - last_screen_message))
        if int(pc() - last_screen_message) >= timeout:
            logger.info("Timeout clearing screen...")
            init_screen(display)
            last_screen_message = pc()

        if not myq.empty():
            try:
                writerThread = Thread(target=lcd_manager_writer, args=(myq.get(),display,logger))
                writerThread.start()
                last_screen_message = pc()
            except Exception as ex:
                logging.exception("aaa")

        sleep(1)

if __name__ == '__main__':
    myname = os.path.basename(sys.argv[0])
    try:
        # Delete the leftover socket (if it exists)
        os.unlink('/var/run/%s' % myname)
        print("Deleting /var/run/%s" % myname)
        os.unlink('/var/run/%s.pid' % myname)
    except:
        pass

    with daemon.DaemonContext(
            pidfile=daemon.pidfile.TimeoutPIDLockFile('/var/run/%s.pid' % myname),
            signal_map={
                signal.SIGTERM: shutdown,
                signal.SIGTSTP: shutdown
                }):
        main()
