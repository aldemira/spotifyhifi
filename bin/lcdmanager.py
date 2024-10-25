#!/usr/bin/env python3

import sys,os
sys.path.append(os.path.abspath("/opt/lcdworks/lib"))
# Get this from https://github.com/lyz508/python-i2c-lcd
from LCD import LCD
import subprocess
import json
import signal
import logging
from logging import config
import socket
from queue import Queue
import threading
from threading import Thread
import daemon, daemon.pidfile
from time import perf_counter as pc, sleep
import configparser
import argparse

socket_path = "/var/run"
thread_local = threading.local()
display_lock = threading.Lock()

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
        thread_local.display = LCD()
    return thread_local.display

def shutdown(signal, frame):
    logger.info('Shutting down!')
    for thread in threading.enumerate():
        thread.kill()
    display = get_display()
    display.no_backlight()
    display.clear()
    os.unlink(socket_path + '/' + os.path.basename(sys.argv[0]))
    sys.exit(0)

def get_my_ip():
    cmd = ['/usr/sbin/ip', '-j', '-o', '-4', 'addr', 'show', 'wlan0']
    res = subprocess.run(cmd,check=True,capture_output=True)
    ip = json.loads(res.stdout.decode('utf-8'))
    #print(ip)
    return ip[0]['addr_info'][0]['local']

def lcd_manager_writer(data, logger, action=None):
    display_lock.acquire(timeout=30)
    display = get_display()

    if action == 'screen_reset':
        logger.info("Resetting screen")
        display.no_backlight()
        display.write_lcd(0, 0, "Aldemir HiFi...")
        display.write_lcd(0, 1, get_my_ip())
        return
    elif action == 'write_msg':
        thread_local.screen_light = True
        # Scrolling takes time, and librespot might send the same
        # song details again.
        mydict = {}
        # TODO use ['spotify'] or some other dict for recived msgs
        try:
            mydict = json.loads(data)
        except:
            logger.info("Malformed data %s" % data)
            display_lock.release()
            return
        display.home()
        display.clear()
        display.backlight()
        long_string(display,mydict['hifi']['artist'], 0)
        long_string(display,mydict['hifi']['track'], 1)
    elif action == 'screen_dim':
        logger.info("Dimming screen")
        thread_local.screen_light = False
        #display.no_backlight()
        # TODO this just clears everything
        pass
    display_lock.release()


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
def long_string(display, text='', num_line=0, num_cols=16):
    if len(text) > num_cols:
        display.write_lcd(0, num_line, text[:num_cols])
        sleep(1)
        for i in range(len(text) - num_cols + 1):
            text_to_print = text[i:i+num_cols]
            display.write_lcd(0, num_line, text_to_print)
            sleep(0.2)
        sleep(0.5)
        for i in reversed(range(len(text) - num_cols + 1)):
            text_to_print = text[i:i+num_cols]
            display.write_lcd(0, num_line, text_to_print)
            sleep(0.2)
    else:
        display.write_lcd(0, num_line, text)

def main():
    config.dictConfig(LOGGING)
    logger = logging.getLogger("aldemir-hifi")
    timeout = int(thread_local.screen_off) * 60
    logger.info('Starting lcdmanager')
    logger.info('Will clear the screen after %s minutes' % thread_local.screen_off)

    writerThread = Thread(target=lcd_manager_writer, args=(None,logger,'screen_reset'))
    writerThread.start()

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    # TODO change this os.path.basename thingy
    mysocket = socket_path + '/' + os.path.basename(sys.argv[0])
    server.bind(mysocket)
    server.listen(1)

    last_screen_message = pc()
    screen_on_time = pc()

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
        if int(pc() - last_screen_message) >= int(timeout):
            logger.info("Timeout clearing screen...")
            writerThread = Thread(target=lcd_manager_writer, args=(None,logger,'screen_reset'))
            writerThread.start()
            last_screen_message = pc()

        if not myq.empty():
            try:
                logger.info("Starting display thread")
                writerThread = Thread(target=lcd_manager_writer, args=(myq.get(),logger,'write_msg'))
                writerThread.start()
                last_screen_message = pc()
                screen_on_time = pc()
            except Exception as ex:
                logging.exception("aaa")

        if int(pc() - screen_on_time) >= int(thread_local.screen_dim):
            if thread_local.screen_light:
                pass
                #writerThread = Thread(target=lcd_manager_writer, args=(None,logger,'screen_dim'))
                #writerThread.start()
            screen_on_time = pc()
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

    parser = argparse.ArgumentParser(description='Display current song&artist from spotify on a 2x16 LCD',add_help=True)
    parser.add_argument('-f',nargs=1,help='Path to the config file',required=False,metavar='/etc/lcdworks.conf')
    args = parser.parse_args()

    if os.path.isfile(args.f[0]):
        CONFIG_FILE = args.f[0]

        lcdworks_config = configparser.ConfigParser()
        with open(CONFIG_FILE, 'r') as f:
            config_string = '[lcd]\n' + f.read()

        lcdworks_config.read_string(config_string)
        config_val = lcdworks_config['lcd']

        thread_local.screen_dim = config_val.get('screen_dim',30)
        thread_local.screen_off = config_val.get('screen_off',10)
        thread_local.screen_msg = config_val.get('screen_msg','')
    else:
        print('Config file is not accessible!')
        print('Using default values')

        thread_local.screen_dim = 30
        thread_local.screen_off = 10
        thread_local.screen_msg = ''


    thread_local.screen_light = False

    # Setup audio output as in 
    # https://learn.adafruit.com/adding-basic-audio-ouput-to-raspberry-pi-zero?view=all
    cmd = ['/usr/bin/gpio', '-g', 'mode', '12', 'alt0']
    res = subprocess.run(cmd,check=True)
    cmd = ['/usr/bin/gpio', '-g', 'mode', '13', 'alt0']
    res = subprocess.run(cmd,check=True)

    with daemon.DaemonContext(
            pidfile=daemon.pidfile.TimeoutPIDLockFile('/var/run/%s.pid' % myname),
            signal_map={
                signal.SIGTERM: shutdown,
                signal.SIGTSTP: shutdown
                }):
        main()
