A threaded, raspberrypi based lcdmanager. Catches librespot events and displays them on a 2x16 LCD. 

Only dependencies are python-daemon, and library files from https://github.com/lyz508/python-i2c-lcd (Which requires python3-smbus2)

Place LCD.py and utils.py under lib directory. Adjust paths in lcdmanager.py

Add a config file as
    ```
       { 
          "client_id": "slkdsdlkjflsd",
          "client_secret": "dlkfjdljfldjfd"
       }
    ```

under conf directory


