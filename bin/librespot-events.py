#!/usr/bin/env python3

import os, sys
import requests
import logging
from logging import config
from base64 import urlsafe_b64encode
from time import sleep
import json
root_path = '/opt/lcdworks'
sys.path.append(os.path.abspath(root_path + '/lib'))
# Get this from https://github.com/the-raspberry-pi-guy/lcd
import drivers

################# HELPER FUNCTIONS ########################
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
        display.lcd_display_string(text[:num_cols], num_line)
        sleep(1)
    else:
        display.lcd_display_string(text, num_line)


def get_token():
    creds = []
    with open(root_path + '/conf/spotify.json', 'r') as f:
        creds = json.loads(f.read())[0]
    client_id = creds['client_id']
    client_secret = creds['client_secret']

    url= 'https://accounts.spotify.com/api/token'
    b = urlsafe_b64encode(bytes(client_id + ':'+ client_secret, 'utf-8')).decode()
    headers= {
        'Authorization': 'Basic ' + str(b),
        'Content-Type': 'application/x-www-form-urlencoded'
        }


    data = { 
        'grant_type': 'client_credentials' 
        }
    response = requests.post(url=url, 
                         data=data,
                         headers=headers)
    if response.status_code == 200:
        auth_res = response.json()
        return auth_res['access_token']
    else:
        return None

def get_track(track_id, access_token):
    url = "https://api.spotify.com/v1/tracks"
    headers = {
        'Authorization': 'Bearer ' + access_token,
    }

    response = requests.get(
        url = url + "/" + track_id,
        headers=headers
    )

    spot_res = response.json()

    if response.status_code == 200:
        return spot_res
    else:
        return None

######################## END HELPER FUNCTIONS ##########################

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
        'librespot-events': {
            'handlers': ['daemon',],
            'level': logging.INFO,
            'propagate': True,
            },
        }
    }

config.dictConfig(LOGGING)
logger = logging.getLogger("librespot-events")

player_event = os.getenv('PLAYER_EVENT')
if not player_event:
    print('Please provide an event!')
    logger.error('Please provide an event!')
    sys.exit(1)


if player_event in ['stopped', 'paused']:
    display = drivers.Lcd()
    display.lcd_backlight(0) 
    display.lcd_clear()
    display.lcd_display_string('Aldemir HiFi!',1)
    display.lcd_display_string('Stopped...',2)
elif player_event in ['playing', 'changed', 'started']:
    display = drivers.Lcd()
    cur_track = os.environ['TRACK_ID']
    logger.info('New track: ' + cur_track)

    #cur_track = '1n7em6Nj2p0SS4S5QMY4Qr'
    spot_res = ''
    with open('spotify_access_token.txt', 'w+') as f:
        access_token = f.read()
        spot_res = get_track(cur_track,access_token)
        if not spot_res:
            access_token = get_token()
        spot_res = get_track(cur_track,access_token)
        f.write(access_token)

    artist = ''
    for i in spot_res['album']['artists']:
        artist = artist + i['name'] + ' '

    display.lcd_backlight(1) 
    long_string(display,artist.rstrip(),1)
    #long_string(display,spot_res['album']['name'],2)
    long_string(display,spot_res['name'],2)

elif player_event in ['preloading']:
    pass
else:
    logger.debug('Received unhandled event')
