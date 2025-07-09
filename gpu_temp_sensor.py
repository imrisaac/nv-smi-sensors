#!/usr/bin/env python3
"""
GPU Temperature Sensor Script
Makes highest GPU temperature available to lm-sensors
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
        self.temp_file = Path("/tmp/gpu_max_temp")
        self.running = True
        
    def get_max_gpu_temp(self):
        """Get the highest GPU temperature from nvidia-smi"""
        try:
            # Use XML output for more reliable parsing
            result = subprocess.run([
                'nvidia-smi', '-q', '-x'
            ], capture_output=True, text=True, check=True)
            
            # Parse XML output
            root = ET.fromstring(result.stdout)
            temperatures = []
            
            # Find all GPU temperature readings
            for gpu in root.findall('.//gpu'):
                temp_elem = gpu.find('.//temperature/gpu_temp')
                if temp_elem is not None:
                    temp_str = temp_elem.text.replace(' C', '')
                    try:
                        temperatures.append(int(temp_str))
                    except ValueError:
                        continue
            
            if temperatures:
                return max(temperatures)
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
    
    def get_max_gpu_temp_csv(self):
        """Alternative method using CSV output (fallback)"""
        try:
            result = subprocess.run([
                'nvidia-smi', 
                '--query-gpu=temperature.gpu',
                '--format=csv,noheader,nounits'
            ], capture_output=True, text=True, check=True)
            
            temperatures = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    try:
                        temp = int(line.strip())
                        temperatures.append(temp)
                    except ValueError:
                        continue
            
            return max(temperatures) if temperatures else None
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
    
    def write_temp_file(self):
        """Write temperature to file in lm-sensors format (millidegrees)"""
        max_temp = self.get_max_gpu_temp()
        
        # Fallback to CSV method if XML fails
        if max_temp is None:
            max_temp = self.get_max_gpu_temp_csv()
        
        if max_temp is not None:
            # Write temperature in millidegrees (lm-sensors format)
            millidegrees = max_temp * 1000
            try:
                with open(self.temp_file, 'w') as f:
                    f.write(f"{millidegrees}\n")
                
                # Make file readable by all
                os.chmod(self.temp_file, 0o644)
                print(f"GPU max temperature: {max_temp}°C written to {self.temp_file}")
                return True
            except IOError as e:
                print(f"Error writing to {self.temp_file}: {e}", file=sys.stderr)
                return False
        else:
            print("Error: Could not get GPU temperature", file=sys.stderr)
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
        
        print(f"Starting GPU temperature monitoring daemon (interval: {interval}s)...")
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
        print("Testing GPU temperature detection...")
        
        temp = self.get_max_gpu_temp()
        if temp is None:
            temp = self.get_max_gpu_temp_csv()
        
        if temp is not None:
            print(f"Highest GPU temperature: {temp}°C")
            
            # Also show individual GPU temps for debugging
            try:
                result = subprocess.run([
                    'nvidia-smi', 
                    '--query-gpu=index,name,temperature.gpu',
                    '--format=csv,noheader'
                ], capture_output=True, text=True, check=True)
                
                print("\nIndividual GPU temperatures:")
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        print(f"  {line}")
                        
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        else:
            print("Error: Could not detect GPU temperature")
            return False
        
        return True


def create_systemd_service(script_path, interval=5):
    """Create systemd service file"""
    service_content = f"""[Unit]
Description=GPU Temperature Sensor
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
    
    service_file = Path("/etc/systemd/system/gpu-temp-sensor.service")
    
    try:
        with open(service_file, 'w') as f:
            f.write(service_content)
        
        print(f"Systemd service created at {service_file}")
        print("Enable with: systemctl enable gpu-temp-sensor.service")
        print("Start with: systemctl start gpu-temp-sensor.service")
        print("Check status: systemctl status gpu-temp-sensor.service")
        return True
        
    except IOError as e:
        print(f"Error creating systemd service: {e}", file=sys.stderr)
        return False


def create_sensors_config():
    """Create lm-sensors configuration"""
    config_content = """# GPU Temperature Sensor Configuration
# Custom GPU temperature monitoring

chip "gpu_max_temp-*"
    label temp1 "GPU Max Temp"
    set temp1_max 90
    set temp1_crit 95

# Alternative: Monitor via file-based sensor
# You can also monitor /tmp/gpu_max_temp directly
"""
    
    config_dir = Path("/etc/sensors.d")
    config_file = config_dir / "gpu-temp.conf"
    
    try:
        config_dir.mkdir(exist_ok=True)
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        print(f"Sensors config created at {config_file}")
        print("Note: File-based monitoring is simpler than hwmon integration")
        print("You can monitor the temperature file directly:")
        print("  watch -n 1 'echo \"GPU Temp: $(($(cat /tmp/gpu_max_temp) / 1000))°C\"'")
        return True
        
    except IOError as e:
        print(f"Error creating sensors config: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="GPU Temperature Sensor for lm-sensors integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --test                    # Test temperature reading
  %(prog)s --temp-file              # Write temp to file once  
  %(prog)s --daemon                 # Run as daemon
  %(prog)s --daemon --interval 10   # Run daemon with 10s interval
  sudo %(prog)s --install-service   # Install as system service

Temperature file location: /tmp/gpu_max_temp
File format: temperature in millidegrees (multiply by 1000)
        """
    )
    
    parser.add_argument('--test', action='store_true',
                       help='Test GPU temperature detection')
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
            print("2. systemctl enable gpu-temp-sensor.service")
            print("3. systemctl start gpu-temp-sensor.service")
        sys.exit(0 if (service_ok and config_ok) else 1)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()