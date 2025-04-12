import serial
import time
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque
from scipy import signal
import tkinter as tk
from tkinter import ttk
import threading
from scipy.signal import find_peaks

# Serial Configuration
arduino_port = "COM3"  # Replace with your Arduino port
baud_rate = 9600
sample_rate = 8000  # Samples per second
buffer_size = sample_rate * 5  # 5 seconds of data

# Initial Filter parameters
lower_cutoff_freq = 20  # Lower cutoff frequency in Hz
upper_cutoff_freq = 350  # Upper cutoff frequency in Hz
filter_order = 2  # Filter order
filter_type = "lowpass"  # Initial filter type
filter_method = "butter"  # Initial filter method

# Connect to Arduino
try:
    ser = serial.Serial(arduino_port, baud_rate)
    time.sleep(2)  # Wait for Arduino to initialize
    print(f"Connected to Arduino on {arduino_port}")
except serial.SerialException as e:
    print(f"Error connecting to Arduino: {e}")
    exit()

# Data Buffers
analog_data = deque(maxlen=buffer_size)
filtered_data = deque(maxlen=buffer_size)
time_data = deque(maxlen=buffer_size)

# Initialize filter
nyquist_freq = 0.5 * sample_rate


def create_filter():
    # Select cutoff frequencies based on filter type
    if filter_type == "lowpass":
        normalized_cutoff = upper_cutoff_freq / nyquist_freq
    elif filter_type == "highpass":
        normalized_cutoff = lower_cutoff_freq / nyquist_freq
    else:
        normalized_cutoff = [
            lower_cutoff_freq / nyquist_freq,
            upper_cutoff_freq / nyquist_freq,
        ]

    # Create filter based on method
    if filter_method == "butter":
        return signal.butter(
            filter_order, normalized_cutoff, btype=filter_type, analog=False
        )

    elif filter_method == "cheby1":
        return signal.cheby1(
            filter_order, 0.5, normalized_cutoff, btype=filter_type, analog=False
        )

    elif filter_method == "cheby2":
        return signal.cheby2(
            filter_order, 40, normalized_cutoff, btype=filter_type, analog=False
        )

    elif filter_method == "ellip":
        return signal.ellip(
            filter_order, 0.5, 40, normalized_cutoff, btype=filter_type, analog=False
        )

    elif filter_method == "bessel":
        return signal.bessel(
            filter_order, normalized_cutoff, btype=filter_type, analog=False
        )


# Initialize filter coefficients
b, a = create_filter()

# Initialize plot
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2)
(line1,) = ax1.plot([], [])
(line2,) = ax2.plot([], [])
(line3,) = ax3.plot([], [])
(line4,) = ax4.plot([], [])

ax1.set_title("Analog Signal (Last 5 Seconds)")
ax1.set_xlabel("Time (s)")
ax1.set_ylabel("Analog Value")
ax1.set_ylim(-2.5, 2.5)

ax2.set_title("FFT of Analog Signal")
ax2.set_xlabel("Frequency (Hz)")
ax2.set_ylabel("Magnitude")
ax2.set_ylim(0, 80)

ax3.set_title("Filtered Signal (Last 5 Seconds)")
ax3.set_xlabel("Time (s)")
ax3.set_ylabel("Filtered Value")
ax3.set_ylim(-2.5, 2.5)

ax4.set_title("FFT of Filtered Signal")
ax4.set_xlabel("Frequency (Hz)")
ax4.set_ylabel("Magnitude")
ax4.set_ylim(0, 80)

fig.tight_layout()


# Function to animate the plot
def animate(i):
    # Read data from serial port. Read Arduino code for more details
    data_buffer = ""
    while ser.in_waiting > 0:
        try:
            char = ser.read().decode("utf-8")
            data_buffer += char

            if "E" in data_buffer and "S" in data_buffer:
                try:
                    start_index = data_buffer.index("S")
                    end_index = data_buffer.index("E")
                    value_str = data_buffer[start_index + 1 : end_index]
                    if value_str.isdigit():
                        analog_value = int(value_str)
                        normalized = (
                            (analog_value / 1024.0) * 5.0
                        ) - 2.5  # Normalize and zero center because most of the dsp functions require zero centered data

                        analog_data.append(normalized)
                        time_data.append(time.time())

                        while time_data and (time_data[-1] - time_data[0] > 5):
                            time_data.popleft()
                            analog_data.popleft()
                except ValueError:
                    pass
                data_buffer = ""

        except UnicodeDecodeError:
            data_buffer = ""
        except Exception:
            data_buffer = ""

    if len(analog_data) > 1:
        relative_times = np.array(list(time_data)) - time_data[0]

        # Apply filter
        filtered = signal.lfilter(b, a, list(analog_data))
        filtered_data.extend(filtered)
        while len(filtered_data) > len(analog_data):
            filtered_data.popleft()

        line1.set_data(relative_times, list(analog_data))
        ax1.relim()
        ax1.autoscale_view()

        # FFT of analog signal
        yf = np.fft.fft(list(analog_data))
        T = 1.0 / sample_rate
        xf = np.fft.fftfreq(len(analog_data), T)[: len(analog_data) // 2]
        line2.set_data(xf, np.abs(yf[0 : len(analog_data) // 2]))
        ax2.relim()
        ax2.autoscale_view()

        line3.set_data(relative_times, list(filtered_data))
        ax3.relim()
        ax3.autoscale_view()

        # FFT of filtered signal
        yff = np.fft.fft(list(filtered_data))
        xff = np.fft.fftfreq(len(filtered_data), T)[: len(filtered_data) // 2]
        line4.set_data(xff, np.abs(yff[0 : len(filtered_data) // 2]))
        ax4.relim()
        ax4.autoscale_view()

    return (line1, line2, line3, line4)


# Function to calculate BPM, not working properly :D
def calculate_bpm():
    if len(filtered_data) > 1:
        # Detect peaks in the filtered signal (which corresponds to heartbeats)
        peaks, _ = find_peaks(
            list(filtered_data), height=0.5, distance=10  # sample_rate // 2
        )  # Adjust height and distance if needed

        if len(peaks) > 1:  # Ensure there are at least two peaks
            # Calculate the time intervals between successive peaks
            peak_times = np.array([time_data[i] for i in peaks])
            peak_intervals = np.diff(
                peak_times
            )  # Time intervals between successive peaks

            avg_interval = np.mean(peak_intervals)  # Average interval in seconds
            bpm = 60 / avg_interval  # BPM calculation (beats per minute)

            bpm_label.config(text=f"BPM: {bpm:.2f}")  # Display BPM in the GUI
        else:
            bpm_label.config(text="BPM: Not enough data")  # Not enough peaks detected
    else:
        bpm_label.config(text="BPM: Not enough data")  # Not enough filter


# Function to update filter parameters
def update_filter_params():
    global b, a, lower_cutoff_freq, upper_cutoff_freq, filter_order, filter_type, filter_method

    try:
        new_lower_cutoff = float(lower_cutoff_entry.get())
        new_upper_cutoff = float(upper_cutoff_entry.get())
        new_order = int(order_entry.get())
        new_filter_type = filter_type_var.get()
        new_filter_method = filter_method_var.get()

        # Validate filter parameters according to Nyquist sapmling theorem
        if new_lower_cutoff <= 0 or new_order <= 0:
            raise ValueError("Cutoff frequencies and order must be positive.")
        if new_lower_cutoff >= nyquist_freq or (
            new_filter_type in ["bandpass", "bandstop"]
            and new_upper_cutoff >= nyquist_freq
        ):
            raise ValueError("Cutoff frequencies must be less than Nyquist frequency.")
        if (
            new_filter_type in ["bandpass", "bandstop"]
            and new_lower_cutoff >= new_upper_cutoff
        ):
            raise ValueError(
                "For bandpass/bandstop, lower cutoff must be less than upper cutoff."
            )

        lower_cutoff_freq = new_lower_cutoff
        upper_cutoff_freq = new_upper_cutoff
        filter_order = new_order
        filter_type = new_filter_type
        filter_method = new_filter_method

        # Update filter coefficients
        b, a = create_filter()

        status_label.config(
            text=f"Filter updated: Method={filter_method}, Type={filter_type}, Cutoff={lower_cutoff_freq}-{upper_cutoff_freq}Hz, Order={filter_order}",
            foreground="green",
        )
    except ValueError as ve:
        status_label.config(text=f"Error: {ve}", foreground="red")


# Tkinter GUI setup
def create_gui():
    global lower_cutoff_entry, upper_cutoff_entry, order_entry, status_label, filter_type_var, filter_method_var, bpm_label

    root = tk.Tk()
    root.title("Filter Parameter Settings")

    # Lower Cutoff Frequency
    ttk.Label(root, text="Lower Cutoff Frequency (Hz):").grid(
        row=0, column=0, padx=10, pady=5
    )
    lower_cutoff_entry = ttk.Entry(root)
    lower_cutoff_entry.grid(row=0, column=1, padx=10, pady=5)
    lower_cutoff_entry.insert(0, str(lower_cutoff_freq))

    # Upper Cutoff Frequency
    ttk.Label(root, text="Upper Cutoff Frequency (Hz):").grid(
        row=1, column=0, padx=10, pady=5
    )
    upper_cutoff_entry = ttk.Entry(root)
    upper_cutoff_entry.grid(row=1, column=1, padx=10, pady=5)
    upper_cutoff_entry.insert(0, str(upper_cutoff_freq))

    # Filter Order
    ttk.Label(root, text="Filter Order:").grid(row=2, column=0, padx=10, pady=5)
    order_entry = ttk.Entry(root)
    order_entry.grid(row=2, column=1, padx=10, pady=5)
    order_entry.insert(0, str(filter_order))

    # Filter Type
    ttk.Label(root, text="Filter Type:").grid(row=3, column=0, padx=10, pady=5)
    filter_type_var = tk.StringVar(value=filter_type)
    filter_type_menu = ttk.OptionMenu(
        root,
        filter_type_var,
        filter_type,
        "lowpass",
        "highpass",
        "bandpass",
        "bandstop",
    )
    filter_type_menu.grid(row=3, column=1, padx=10, pady=5)

    # Filter Method
    ttk.Label(root, text="Filter Method:").grid(row=4, column=0, padx=10, pady=5)
    filter_method_var = tk.StringVar(value=filter_method)
    filter_method_menu = ttk.OptionMenu(
        root,
        filter_method_var,
        filter_method,
        "butter",
        "cheby1",
        "cheby2",
        "ellip",
        "bessel",
    )
    filter_method_menu.grid(row=4, column=1, padx=10, pady=5)

    # BPM Label
    bpm_label = ttk.Label(
        root, text="BPM: N/A", foreground="blue"
    )  # Define bpm_label here
    bpm_label.grid(row=7, column=0, columnspan=2, pady=10)

    # Update Button
    update_button = ttk.Button(root, text="Update Filter", command=update_filter_params)
    update_button.grid(row=5, column=0, columnspan=2, pady=10)

    # Calculate BPM Button
    calculate_bpm_button = ttk.Button(root, text="Calculate BPM", command=calculate_bpm)
    calculate_bpm_button.grid(row=8, column=0, columnspan=2, pady=10)

    # Status Label
    status_label = ttk.Label(
        root, text="Filter parameters are set.", foreground="green"
    )
    status_label.grid(row=6, column=0, columnspan=2, pady=5)

    root.mainloop()


# Start Tkinter GUI in a separate thread
threading.Thread(target=create_gui, daemon=True).start()

# Start the animation
ani = animation.FuncAnimation(
    fig,
    animate,
    interval=1 / 144,  # 144 Hz refresh rate, adjust as needed
    blit=True,
    cache_frame_data=False,
)
plt.show()
