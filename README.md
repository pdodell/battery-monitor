# Battery Monitor

Battery Monitor checks Home Assistant for battery percentage sensors and sends alerts to your existing [Dashboard Notifications integration](https://github.com/SigInTheHead/notifications-integration). Add Battery Monitor once to cover both current and future sensors.

## Install with HACS

1. In Dashboard Notifications, create or select a topic, such as **Batteries**.
2. In HACS, open the three-dot menu and select **Custom repositories**. Enter `https://github.com/pdodell/battery-monitor`, select **Integration**, and select **Add**.
3. Find **Battery Monitor** in HACS and select **Download**, then restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration**, select **Battery Monitor**, and choose your topic and thresholds. The defaults are **20%** for warnings and **10%** for critical alerts.
5. If your existing Dashboard Notifications card filters by topic, include the same topic on the card.

## Install manually

Copy `custom_components/battery_monitor` into your Home Assistant configuration's `custom_components` directory, restart Home Assistant, and follow the setup in steps 4 and 5 above.

## Alert behavior

- The first scan runs after startup or setup. Subsequent scans run every minute.
- Each enabled `sensor` with the `battery` device class and `%` as its unit is discovered automatically. In **Developer tools → States**, check those attributes if you expect a sensor to appear. Devices that expose only battery voltage or a binary low-battery flag need a percentage sensor to be included.
- A reading at or below the warning threshold creates a persistent **Warning**. A reading at or below the critical threshold takes priority and uses **Error** severity. Alerts hide their timestamps.
- Each scan updates the same alert if the battery reading or severity has changed. This includes drops within the same severity and increases that remain in the alert range. A reading above both thresholds clears the alert.
- An unknown or unavailable reading leaves any existing warning in place until the sensor reports a valid reading again. Removing or disabling a sensor clears its warning once Home Assistant removes the state.
- Use **Configure** on the Battery Monitor integration to change the topic or thresholds or view the discovered batteries and their current readings. Check a battery to exclude it and clear its alert. Uncheck it to resume monitoring. Previously excluded sensors remain in the list even if they are unavailable.

To check the setup, temporarily set the warning threshold to the current percentage of a battery sensor. Its alert should appear on the selected card within a minute. Lower both thresholds below that sensor's reading and confirm that the alert clears.
