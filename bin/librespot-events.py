#!/usr/bin/env python3

import os, sys
import requests
import logging
from logging import config
from base64 import urlsafe_b64encode
import json
root_path = '/opt/lcdworks'
import socket

################# HELPER FUNCTIONS ########################
def get_token():
    creds = {}
    with open(root_path + '/conf/spotify.json', 'r') as f:
        creds = json.loads(f.read())
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
def create_connection():
    # create a socket object
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    # connect to the Unix domain socket server
    server_address = '/var/run/lcdmanager.py'

    try:
        sock.connect(server_address)
        sock.settimeout(10)
    except:
        logger.exception("Can't connect")
        sys.exit(1)

    return sock

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
logger.info("Starting up.")
player_event = os.getenv('PLAYER_EVENT')
if not player_event:
    print('Please provide an event!')
    logger.error('Please provide an event!')
    sys.exit(1)

if player_event in ['stopped', 'paused']:
    sock = create_connection()
    sock.sendall(b'["Aldemir HiFi","Stopped..."]')
    # receive data from the server
    received_data = sock.recv(1024)

    # close the socket
    sock.close()

    # process the received data
    logger.debug(received_data.decode())

elif player_event in ['playing', 'changed', 'started']:
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

    #long_string(display,artist.rstrip(),1)
    #long_string(display,spot_res['name'],2)
    data = '["%s","%s"]' % (artist.rstrip(), spot_res['name'])
    sock = create_connection()
    try:
        sock.sendall(str.encode(data))
    except:
        logger.exception()

    # receive data from the server
    received_data = sock.recv(1024)

    # close the socket
    sock.close()

    # process the received data
    logger.debug(received_data.decode())
elif player_event in ['preloading']:
    pass
else:
    logger.debug('Received unhandled event')
