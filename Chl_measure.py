import time
import datetime
import RPi.GPIO as gp
import Adafruit_ADS1x15
from datetime import datetime, timedelta
import busio
import board
import numpy as np
from scipy.signal import savgol_filter
import sys
import re
import requests
import os

# --- ThingSpeak Configuration ---
THINGSPEAK_API_KEY = "GHRZMABOQG7DIAWQ"
THINGSPEAK_URL = "https://api.thingspeak.com/update"

# --- File Storage Configuration ---
RESULTS_PATH = "/home/fww/results/chlorophyll/"

# --- GPIO Setup ---
pin = int(sys.argv[1])
gp.setmode(gp.BCM)
gp.setup(pin, gp.OUT)
gp.setwarnings(False)
i2c = busio.I2C(board.SCL, board.SDA)
time.sleep(0.5)
adc = Adafruit_ADS1x15.ADS1115(busnum=1)
GAIN = 2/3
conversion = 6.144 / 32768
data = []
means = []
results = []

def read():
    stop = datetime.now() + timedelta(seconds=3)
    real_time = datetime.now()
    while real_time < stop:
        v = adc.read_adc(0, gain=GAIN) * conversion
        data.append(v)
        real_time = datetime.now()

def Savgol(s):
    wl = 51 if len(s) >= 51 else len(s) // 2 * 2 + 1
    return savgol_filter(s, wl, polyorder=3)

def led_on():
    gp.output(pin, gp.HIGH)

def led_off():
    gp.output(pin, gp.LOW)

def remove_outliers(values):
    values = values.tolist()
    filtered = []
    m = np.mean(values)
    dev = np.std(values)
    
    for i in values:
        Z = (i - m) / dev if dev != 0 else 0
        Z = round(Z, 2)
        if -2.9 <= Z <= 2.9:
            filtered.append(i)
    
    return np.array(filtered) if filtered else values

def load_calibration(filename="/home/fww/calibrations/chl_calibration.txt"):
    """Load calibration parameters from file"""
    try:
        with open(filename, 'r') as f:
            content = f.read()
            
        # Extract slope, intercept, and R²
        slope_match = re.search(r'SLOPE=([-+]?[0-9]*\.?[0-9]+)', content)
        intercept_match = re.search(r'INTERCEPT=([-+]?[0-9]*\.?[0-9]+)', content)
        r2_match = re.search(r'R_SQUARED=([-+]?[0-9]*\.?[0-9]+)', content)
        
        if slope_match and intercept_match and r2_match:
            slope = float(slope_match.group(1))
            intercept = float(intercept_match.group(1))
            r_squared = float(r2_match.group(1))
            return slope, intercept, r_squared
        else:
            raise ValueError("Could not parse calibration parameters")
            
    except FileNotFoundError:
        print(f"Error: Calibration file '{filename}' not found.")
        print("Please run calibration.py first to create calibration.")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading calibration: {e}")
        sys.exit(1)

def voltage_to_concentration(voltage, slope, intercept):
    """Convert voltage to concentration using calibration curve"""
    # V = slope * C + intercept
    # Therefore: C = (V - intercept) / slope
    if slope == 0:
        print("Error: Invalid calibration (slope = 0)")
        return None
    concentration = (voltage - intercept) / slope
    return concentration

def send_to_thingspeak(concentration, timestamp):
    """Send concentration and timestamp to ThingSpeak"""
    try:
        payload = {
            'api_key': THINGSPEAK_API_KEY,
            'field1': concentration,
            'field2': timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        response = requests.get(THINGSPEAK_URL, params=payload, timeout=10)
        
        if response.status_code == 200:
            entry_id = response.text
            if entry_id != '0':
                print(f"✓ Data sent to ThingSpeak successfully (Entry ID: {entry_id})")
                return True
            else:
                print("✗ ThingSpeak returned 0 (possible rate limit or error)")
                return False
        else:
            print(f"✗ Failed to send data to ThingSpeak (Status: {response.status_code})")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Network error sending to ThingSpeak: {e}")
        return False
    except Exception as e:
        print(f"✗ Error sending to ThingSpeak: {e}")
        return False

def save_offline(concentration, voltage, timestamp, slope, intercept, r_squared):
    """Save measurement data to local file"""
    try:
        # Create directory if it doesn't exist
        os.makedirs(RESULTS_PATH, exist_ok=True)
        
        # Generate filename with timestamp
        filename = timestamp.strftime('%Y%m%d_%H%M%S') + "_chlorophyll.txt"
        filepath = os.path.join(RESULTS_PATH, filename)
        
        # Write data to file
        with open(filepath, 'w') as f:
            f.write("CHLOROPHYLL MEASUREMENT RESULTS\n")
            f.write("=" * 60 + "\n")
            f.write(f"Timestamp: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Date: {timestamp.strftime('%Y-%m-%d')}\n")
            f.write(f"Time: {timestamp.strftime('%H:%M:%S')}\n")
            f.write("\n")
            f.write("MEASUREMENT DATA\n")
            f.write("-" * 60 + "\n")
            f.write(f"Concentration: {concentration:.4f}\n")
            f.write(f"Voltage: {voltage:.4f} V\n")
            f.write("\n")
            f.write("CALIBRATION PARAMETERS USED\n")
            f.write("-" * 60 + "\n")
            f.write(f"Equation: V = {slope:.6f} * C + {intercept:.6f}\n")
            f.write(f"R^2 = {r_squared:.6f}\n")
            f.write("\n")
        
        print(f" Data saved to: {filepath}")
        return True
        
    except Exception as e:
        print(f"✗ Error saving data offline: {e}")
        return False

# --- MAIN ---
print("=" * 60)
print("CHLOROPHYLL MEASUREMENT")
print("=" * 60)
print()

# Get current timestamp
measurement_time = datetime.now()

# Load calibration
print("Loading calibration...")
slope, intercept, r_squared = load_calibration()
print(f"Calibration loaded: V = {slope:.6f} * C + {intercept:.6f}")
print(f"R² = {r_squared:.6f}")
print()

# Take measurement
print("Taking measurement...")
for i in range(1, 4):
    led_on()
    read()
    led_off()
    sdev = np.std(data)
    mean = np.mean(data)
    # --- Smoothing ---
    f = Savgol(data)
    f = remove_outliers(f)
    sdev_f = np.std(f)
    mean_f = np.mean(f)
    means.append(mean_f)
    data.clear()
    time.sleep(0.5)

# Calculate final voltage
mean_voltage = round(np.mean(means), 4)

print()
print("-" * 60)
print("RESULTS")
print("-" * 60)
print(f"Timestamp: {measurement_time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Mean Voltage: {mean_voltage} V")

# Convert to concentration
concentration = voltage_to_concentration(mean_voltage, slope, intercept)

if concentration is not None:
    print(f"Concentration: {concentration:.4f}")
    print()
    
    # Quality indicator
    if r_squared >= 0.95:
        print(" Measurement based on reliable calibration")
    else:
        print(" Warning: Calibration quality is poor (R² < 0.95)")
        print("  Consider recalibrating for better accuracy")
    
    print()
    print("-" * 60)
    print("DATA TRANSMISSION & STORAGE")
    print("-" * 60)
    
    # Send to ThingSpeak
    print("Sending to ThingSpeak...")
    thingspeak_success = send_to_thingspeak(concentration, measurement_time)
    
    # Save offline
    print("Saving data offline...")
    offline_success = save_offline(concentration, mean_voltage, measurement_time, 
                                   slope, intercept, r_squared)
    
    print()
    print("=" * 60)
    
    # Summary
    if thingspeak_success and offline_success:
        print(" Measurement completed successfully")
    elif thingspeak_success or offline_success:
        print(" Measurement completed with partial success")
    else:
        print(" Measurement completed but data storage failed")
    
    print("=" * 60)

else:
    print(" Error: Could not calculate concentration")

gp.cleanup()
