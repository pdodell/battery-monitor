# Battery Monitor

Battery Monitor checks Home Assistant for battery percentage sensors and sends alerts to your existing [Dashboard Notifications integration](https://github.com/SigInTheHead/notifications-integration). Add Battery Monitor once to cover both current and future sensors.

## Install with HACS

1. In Dashboard Notifications, create or select a topic, such as **Batteries**.
2. In HACS, open the three-dot menu and select **Custom repositories**. Enter `https://github.com/pdodell/battery-monitor`, select **Integration**, and select **Add**.
3. Find **Battery Monitor** in HACS and select **Download**, then restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration**, select **Battery Monitor**, and choose your topic and threshold. The default is **20%**.
5. If your existing Dashboard Notifications card filters by topic, include the same topic on the card.

## Install manually

Copy `custom_components/battery_monitor` into your Home Assistant configuration's `custom_components` directory, restart Home Assistant, and follow the setup in steps 4 and 5 above.

## Alert behavior

- The first scan runs after startup or setup. Subsequent scans run every minute.
- Each enabled `sensor` with the `battery` device class and `%` as its unit is discovered automatically. In **Developer tools → States**, check those attributes if you expect a sensor to appear. Devices that expose only battery voltage or a binary low-battery flag need a percentage sensor to be included.
- A valid reading at or below the threshold creates one persistent warning for that sensor. Changes to the displayed reading update the same warning. A reading above the threshold clears it.
- An unknown or unavailable reading leaves any existing warning in place until the sensor reports a valid reading again. Removing or disabling a sensor clears its warning once Home Assistant removes the state.
- Use **Configure** on the Battery Monitor integration to change the topic or threshold or view the discovered batteries and their current readings. Check a battery to exclude it and clear its warning. Uncheck it to resume monitoring. Previously excluded sensors remain in the list even if they are unavailable.

To check the setup, temporarily set the threshold to the current percentage of a battery sensor. Its warning should appear on the selected card within a minute. Lower the threshold below that sensor's reading and confirm that the warning clears.
