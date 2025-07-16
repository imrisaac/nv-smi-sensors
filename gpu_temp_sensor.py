#!/usr/bin/env python3
"""
GPU Temperature Sensor Script
Makes average H100 NVL GPU temperature available to lm-sensors
Author: AI Assistant
Usage: Run as daemon or via systemd service
"""

import subprocess
import time
import argparse
import sys
import os
import signal
from pathlib import Path
import xml.etree.ElementTree as ET


class GPUTempSensor:
    def __init__(self):
        self.temp_file = Path("/tmp/gpu_h100_avg_temp")
        self.running = True
        self.target_product = "NVIDIA H100 NVL"
        
    def get_h100_nvl_avg_temp(self):
        """Get the average GPU temperature from H100 NVL cards only"""
        try:
            # Use XML output for more reliable parsing
            result = subprocess.run([
                'nvidia-smi', '-q', '-x'
            ], capture_output=True, text=True, check=True)
            
            # Parse XML output
            root = ET.fromstring(result.stdout)
            h100_temperatures = []
            
            # Find all GPU temperature readings for H100 NVL cards
            for gpu in root.findall('.//gpu'):
                # Check product name
                product_elem = gpu.find('.//product_name')
                if product_elem is not None and product_elem.text == self.target_product:
                    temp_elem = gpu.find('.//temperature/gpu_temp')
                    if temp_elem is not None:
                        temp_str = temp_elem.text.replace(' C', '')
                        try:
                            h100_temperatures.append(int(temp_str))
                        except ValueError:
                            continue
            
            if h100_temperatures:
                # Return average temperature
                return sum(h100_temperatures) / len(h100_temperatures)
            else:
                return None
                
        except subprocess.CalledProcessError:
            print("Error: nvidia-smi command failed", file=sys.stderr)
            return None
        except FileNotFoundError:
            print("Error: nvidia-smi not found", file=sys.stderr)
            return None
        except ET.ParseError:
            print("Error: Failed to parse nvidia-smi XML output", file=sys.stderr)
            return None
    
    def get_h100_nvl_avg_temp_csv(self):
        """Alternative method using CSV output (fallback) - filters by index"""
        try:
            # First get product names to identify H100 NVL cards
            result = subprocess.run([
                'nvidia-smi', 
                '--query-gpu=index,name',
                '--format=csv,noheader'
            ], capture_output=True, text=True, check=True)
            
            h100_indices = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.strip().split(', ')
                    if len(parts) >= 2 and self.target_product in parts[1]:
                        try:
                            h100_indices.append(int(parts[0]))
                        except ValueError:
                            continue
            
            if not h100_indices:
                return None
            
            # Now get temperatures for all GPUs
            result = subprocess.run([
                'nvidia-smi', 
                '--query-gpu=index,temperature.gpu',
                '--format=csv,noheader,nounits'
            ], capture_output=True, text=True, check=True)
            
            h100_temperatures = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.strip().split(', ')
                    if len(parts) >= 2:
                        try:
                            index = int(parts[0])
                            temp = int(parts[1])
                            if index in h100_indices:
                                h100_temperatures.append(temp)
                        except ValueError:
                            continue
            
            return sum(h100_temperatures) / len(h100_temperatures) if h100_temperatures else None
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
    
    def write_temp_file(self):
        """Write average H100 NVL temperature to file in lm-sensors format (millidegrees)"""
        avg_temp = self.get_h100_nvl_avg_temp()
        
        # Fallback to CSV method if XML fails
        if avg_temp is None:
            avg_temp = self.get_h100_nvl_avg_temp_csv()
        
        if avg_temp is not None:
            # Write temperature in millidegrees (lm-sensors format)
            millidegrees = int(avg_temp * 1000)
            try:
                with open(self.temp_file, 'w') as f:
                    f.write(f"{millidegrees}\n")
                
                # Make file readable by all
                os.chmod(self.temp_file, 0o644)
                print(f"H100 NVL average temperature: {avg_temp:.1f}°C written to {self.temp_file}")
                return True
            except IOError as e:
                print(f"Error writing to {self.temp_file}: {e}", file=sys.stderr)
                return False
        else:
            print("Error: Could not get H100 NVL GPU temperature (no H100 NVL cards found?)", file=sys.stderr)
            return False
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\nReceived signal {signum}, shutting down...")
        self.running = False
    
    def run_daemon(self, interval=5):
        """Run as daemon, updating temperature every interval seconds"""
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        print(f"Starting H100 NVL GPU temperature monitoring daemon (interval: {interval}s)...")
        print(f"Target product: {self.target_product}")
        print(f"Temperature file: {self.temp_file}")
        print("Press Ctrl+C to stop")
        
        while self.running:
            if not self.write_temp_file():
                print("Failed to update temperature, retrying...", file=sys.stderr)
            
            # Sleep with interruption check
            for _ in range(interval):
                if not self.running:
                    break
                time.sleep(1)
        
        print("Daemon stopped")
    
    def test_temperature(self):
        """Test temperature reading and display result"""
        print("Testing H100 NVL GPU temperature detection...")
        print(f"Target product: {self.target_product}")
        
        # Show all GPUs first
        try:
            result = subprocess.run([
                'nvidia-smi', 
                '--query-gpu=index,name,temperature.gpu',
                '--format=csv,noheader'
            ], capture_output=True, text=True, check=True)
            
            print("\nAll detected GPUs:")
            h100_count = 0
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.strip().split(', ')
                    if len(parts) >= 2:
                        is_h100 = self.target_product in parts[1]
                        marker = " ← H100 NVL" if is_h100 else ""
                        if is_h100:
                            h100_count += 1
                        print(f"  {line}{marker}")
            
            print(f"\nFound {h100_count} H100 NVL card(s)")
                        
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Could not list GPUs")
        
        # Test temperature reading
        temp = self.get_h100_nvl_avg_temp()
        if temp is None:
            temp = self.get_h100_nvl_avg_temp_csv()
        
        if temp is not None:
            print(f"Average H100 NVL temperature: {temp:.1f}°C")
        else:
            print("Error: Could not detect H100 NVL GPU temperature")
            print("Make sure you have H100 NVL cards installed and nvidia-smi is working")
            return False
        
        return True


def create_systemd_service(script_path, interval=5):
    """Create systemd service file"""
    service_content = f"""[Unit]
Description=H100 NVL GPU Temperature Sensor
After=multi-user.target
Wants=multi-user.target

[Service]
Type=simple
ExecStart={script_path} --daemon --interval {interval}
Restart=always
RestartSec=10
User=root
KillSignal=SIGTERM
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
"""
    
    service_file = Path("/etc/systemd/system/gpu-h100-temp-sensor.service")
    
    try:
        with open(service_file, 'w') as f:
            f.write(service_content)
        
        print(f"Systemd service created at {service_file}")
        print("Enable with: systemctl enable gpu-h100-temp-sensor.service")
        print("Start with: systemctl start gpu-h100-temp-sensor.service")
        print("Check status: systemctl status gpu-h100-temp-sensor.service")
        return True
        
    except IOError as e:
        print(f"Error creating systemd service: {e}", file=sys.stderr)
        return False


def create_sensors_config():
    """Create lm-sensors configuration"""
    config_content = """# H100 NVL GPU Temperature Sensor Configuration
# Custom H100 NVL GPU temperature monitoring

chip "gpu_h100_avg_temp-*"
    label temp1 "H100 NVL Avg Temp"
    set temp1_max 90
    set temp1_crit 95

# Alternative: Monitor via file-based sensor
# You can also monitor /tmp/gpu_h100_avg_temp directly
"""
    
    config_dir = Path("/etc/sensors.d")
    config_file = config_dir / "gpu-h100-temp.conf"
    
    try:
        config_dir.mkdir(exist_ok=True)
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        print(f"Sensors config created at {config_file}")
        print("Note: File-based monitoring is simpler than hwmon integration")
        print("You can monitor the temperature file directly:")
        print("  watch -n 1 'echo \"H100 NVL Avg Temp: $(($(cat /tmp/gpu_h100_avg_temp) / 1000))°C\"'")
        return True
        
    except IOError as e:
        print(f"Error creating sensors config: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="H100 NVL GPU Temperature Sensor for lm-sensors integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --test                    # Test temperature reading
  %(prog)s --temp-file              # Write temp to file once  
  %(prog)s --daemon                 # Run as daemon
  %(prog)s --daemon --interval 10   # Run daemon with 10s interval
  sudo %(prog)s --install-service   # Install as system service

Temperature file location: /tmp/gpu_h100_avg_temp
File format: temperature in millidegrees (multiply by 1000)
Filters: Only monitors NVIDIA H100 NVL cards
        """
    )
    
    parser.add_argument('--test', action='store_true',
                       help='Test H100 NVL GPU temperature detection')
    parser.add_argument('--temp-file', action='store_true',
                       help='Write temperature to file (one-time)')
    parser.add_argument('--daemon', action='store_true',
                       help='Run as daemon (continuous monitoring)')
    parser.add_argument('--interval', type=int, default=5,
                       help='Update interval in seconds for daemon mode (default: 5)')
    parser.add_argument('--install-service', action='store_true',
                       help='Install systemd service (requires root)')
    
    args = parser.parse_args()
    
    # Check if running as root for service installation
    if args.install_service and os.geteuid() != 0:
        print("Error: Must run as root to install systemd service", file=sys.stderr)
        sys.exit(1)
    
    sensor = GPUTempSensor()
    
    if args.test:
        success = sensor.test_temperature()
        sys.exit(0 if success else 1)
    
    elif args.temp_file:
        success = sensor.write_temp_file()
        sys.exit(0 if success else 1)
    
    elif args.daemon:
        try:
            sensor.run_daemon(args.interval)
        except KeyboardInterrupt:
            print("\nDaemon stopped by user")
    
    elif args.install_service:
        script_path = Path(__file__).resolve()
        service_ok = create_systemd_service(script_path, args.interval)
        config_ok = create_sensors_config()
        
        if service_ok and config_ok:
            print("\nInstallation complete!")
            print("Next steps:")
            print("1. systemctl daemon-reload")
            print("2. systemctl enable gpu-h100-temp-sensor.service")
            print("3. systemctl start gpu-h100-temp-sensor.service")
        sys.exit(0 if (service_ok and config_ok) else 1)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()