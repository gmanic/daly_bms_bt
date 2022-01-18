Starting with dreadnought's py-module for the Daly BMS, I found some more snippets on commands and return codes. (thanks to the brave man at https://diysolarforum.com/threads/decoding-the-daly-smartbms-protocol.21898/)
I am far from having all of them implemented, and I likely will not implement all of them.
As my plan is to use the BT capabilities on my BMS (4S-120A), I'll focus on certain functions.

MQTT is implemented (also gracefully taken from dreadnought) grafana/prometheus functionality might be implemented (grabbing more pieces from around the internet). Because I intend to use it as monitoring-only, and to keep security footprint low, I will not implement setting parameters of the BMS. Use the usual ways to modify (app etc.).

Configuration is via commandline hardcoded so far (especially the BT mac-address of the BMS).

**daly_bms_bt.py** is the file to run, it'll show some help when called without the required BT mac_address to connect to. The MQTT arguments are also provided on the cmd-line, you can define a loop-wait in seconds, but be aware, that the Daly BT module goes to sleep if not used and neither load/charge are present after approx 1h of inactivity.

Running daly_bms_bt.py will loop endlessly (until a fatal error or CTRL-C [always trying to cleanly shut down BT connection]). Results are currently printed (json) on STDOUT unless you configure MQTT. While this BT connection is active, you cannot connect to the BMS with any other app/PC on BT. I have not tried to connect via CAN/UART-485 at the same time.

Requirements are especially bleak for BT connectivity, paho for MQTT (and some more usually installed modules).

Structure is that daly_bms.py is implementing data functionallity, daly_bms_bluetooth.py is the connection layer to the BMS via bleak (via asyncio, hence this additional layer (extended to dreadnought's initial implementation).

Data model is a little different to accomodate a clear (IMHO) MQTT structure, especially considering using more than one Daly SMART BMS.

I have no prior experience with python, nor asyncio programming, so bear with me. :)

Feel free to re-use (according to MIT licence, as original dreadnought's repo).

Thanks a lot, dreadnought and that writer on diysolarforum.com.

I cannot confirm, as of now, but keep the following in mind:
- It seems like the Bluetooth BMS Module goes to sleep after 1 hour of inactivity (no load or charging), while the serial connection responds all the time. Sending a command via the serial interface wakes up the Bluetooth module.

Keep in mind: no guarantees, use at your own risk & your mileage might vary.