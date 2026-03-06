import time
import datetime
import RPi.GPIO as gp
import Adafruit_ADS1x15
from datetime import datetime, timedelta
import busio
import board
import numpy as np
from scipy.signal import savgol_filter
from scipy import stats
import sys

# --- GPIO Setup ---
pin = int(sys.argv[1])
gp.setmode(gp.BCM)
gp.setup(pin, gp.OUT)
gp.setwarnings(False)

# --- I2C and ADC Setup ---
i2c = busio.I2C(board.SCL, board.SDA)
time.sleep(0.5)
adc = Adafruit_ADS1x15.ADS1115(busnum=1)
GAIN = 2/3
conversion = 6.144 / 32768

# --- Global variables ---
data = []
means = []
results = []
path = "/home/fww/calibrations/"

def read():
    """Read ADC data for 3 seconds"""
    stop = datetime.now() + timedelta(seconds=3)
    real_time = datetime.now()
    while real_time < stop:
        v = adc.read_adc(0, gain=GAIN) * conversion #Use ADS1115 channel 0
        data.append(v)
        real_time = datetime.now()

def Savgol(s):
    """Apply Savitzky-Golay filter for smoothing"""
    wl = 51 if len(s) >= 51 else len(s) // 2 * 2 + 1
    return savgol_filter(s, wl, polyorder=3)

def led_on():
    """Turn LED on"""
    gp.output(pin, gp.HIGH)

def led_off():
    """Turn LED off"""
    gp.output(pin, gp.LOW)

def remove_outliers(values):
    """Remove outliers using Z-score method"""
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

def take_measurement():
    """Take a single measurement (3 readings averaged)"""
    means.clear()
    
    for i in range(1, 4):
        led_on()
        read()
        led_off()
        
        # Smoothing and filtering
        f = Savgol(data)
        f = remove_outliers(f)
        mean_f = np.mean(f)
        means.append(mean_f)
        data.clear()
        time.sleep(0.5)
    
    # Return average of 3 measurements
    return round(np.mean(means), 4)

def main():
    print("=" * 60)
    print("CALIBRATION PROCEDURE FOR CHLOROPHYLL MEASUREMENT")
    print("=" * 60)
    print()
    
    # Get number of standards from user
    while True:
        try:
            num_standards = int(input("Enter number of standard solutions (minimum 3): "))
            if num_standards >= 3:
                break
            else:
                print("Please enter at least 3 standards for reliable calibration.")
        except ValueError:
            print("Please enter a valid integer.")
    
    print()
    print("You will measure:")
    print("  1. One blank (0 concentration)")
    print(f"  2. {num_standards} standard solutions")
    print()
    
    concentrations = []
    voltages = []
    
    # Measure blank
    print("-" * 60)
    input("Prepare BLANK solution (0 concentration). Press Enter when ready...")
    print("Measuring blank...")
    blank_voltage = take_measurement()
    print(f"Blank voltage: {blank_voltage} V")
    print()
    
    concentrations.append(0.0)
    voltages.append(blank_voltage)
    
    # Measure standards
    for i in range(1, num_standards + 1):
        print("-" * 60)
        while True:
            try:
                conc = float(input(f"Enter concentration of standard #{i} (e.g., mg/L or µg/L): "))
                if conc > 0:
                    break
                else:
                    print("Concentration must be positive.")
            except ValueError:
                print("Please enter a valid number.")
        
        input(f"Prepare standard #{i} ({conc} concentration). Press Enter when ready...")
        print(f"Measuring standard #{i}...")
        voltage = take_measurement()
        print(f"Standard #{i} voltage: {voltage} V")
        print()
        
        concentrations.append(conc)
        voltages.append(voltage)
    
    # Perform linear regression
    print("=" * 60)
    print("CALIBRATION RESULTS")
    print("=" * 60)
    print()
    
    concentrations = np.array(concentrations)
    voltages = np.array(voltages)
    
    # Linear fit: voltage = slope * concentration + intercept
    slope, intercept, r_value, p_value, std_err = stats.linregress(concentrations, voltages)
    r_squared = r_value ** 2
    
    print(f"Linear regression: V = {slope:.6f} * C + {intercept:.6f}")
    print(f"R² = {r_squared:.6f}")
    print(f"Correlation coefficient (R) = {r_value:.6f}")
    print()
    
    # Display calibration data
    print("Calibration data:")
    print(f"{'Concentration':<20} {'Voltage (V)':<15}")
    print("-" * 35)
    for c, v in zip(concentrations, voltages):
        print(f"{c:<20.4f} {v:<15.4f}")
    print()
    
    # Save calibration to file
    filename = path+"chl_calibration.txt"
    with open(filename, 'w') as f:
        f.write("CHLOROPHYLL CALIBRATION DATA\n")
        f.write("=" * 60 + "\n")
        f.write(f"Calibration date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Number of standards: {num_standards + 1} (including blank)\n")
        f.write("\n")
        f.write("LINEAR REGRESSION RESULTS\n")
        f.write("-" * 60 + "\n")
        f.write(f"Equation: V = {slope:.6f} * C + {intercept:.6f}\n")
        f.write(f"Where V = voltage (V), C = concentration\n")
        f.write(f"R² = {r_squared:.6f}\n")
        f.write(f"Correlation coefficient (R) = {r_value:.6f}\n")
        f.write(f"Standard error: {std_err:.6f}\n")
        f.write(f"P-value: {p_value:.6e}\n")
        f.write("\n")
        f.write("CALIBRATION DATA POINTS\n")
        f.write("-" * 60 + "\n")
        f.write(f"{'Concentration':<20} {'Voltage (V)':<15}\n")
        f.write("-" * 35 + "\n")
        for c, v in zip(concentrations, voltages):
            f.write(f"{c:<20.4f} {v:<15.4f}\n")
        f.write("\n")
        f.write("CALIBRATION PARAMETERS (for use in measurement code)\n")
        f.write("-" * 60 + "\n")
        f.write(f"SLOPE={slope:.6f}\n")
        f.write(f"INTERCEPT={intercept:.6f}\n")
        f.write(f"R_SQUARED={r_squared:.6f}\n")
    
    print(f"Calibration saved to '{filename}'")
    print()
    
    # Quality check
    if r_squared >= 0.99:
        print(" Excellent calibration (R^2 ≥ 0.99)")
    elif r_squared >= 0.97:
        print(" Good calibration (R^2 ≥ 0.95)")
    elif r_squared >= 0.95:
        print(" Acceptable calibration (R^2 ≥ 0.90)")
    else:
        print("WARNING: Poor calibration (R^2 < 0.90)")
        print("  Consider repeating calibration with fresh standards.")
    
    print()
    print("=" * 60)
    
    # Cleanup
    gp.cleanup()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCalibration interrupted by user.")
        gp.cleanup()
        sys.exit(0)
    except Exception as e:
        print(f"\n\nError during calibration: {e}")
        gp.cleanup()
        sys.exit(1)
