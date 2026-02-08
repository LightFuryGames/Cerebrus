
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

try:
    from cerebrus.tools.adb import AdbClient
    from cerebrus.core.devices import collect_device_info

    print("--- Testing AdbClient.list_devices ---")
    client = AdbClient()
    try:
        serials = client.list_devices()
        print(f"Serials found: {serials}")
    except Exception as e:
        print(f"list_devices failed: {e}")

    print("\n--- Testing collect_device_info ---")
    try:
        # Pass a dummy package name
        devices = collect_device_info("com.example.app")
        print(f"Devices found: {len(devices)}")
        for d in devices:
            print(f"Device: {d}")
    except Exception as e:
        print(f"collect_device_info failed: {e}")

except ImportError as e:
    print(f"Import failed: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
