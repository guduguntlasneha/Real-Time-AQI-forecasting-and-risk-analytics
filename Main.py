#!/usr/bin/env python3
"""
Air Quality Monitor - Main Control Script
Manages receiver, analytics, and monitoring in a unified interface

Usage:
    sudo python3 main.py [options]
    
Options:
    --mode [receiver|analytics|dashboard|monitor]
    --config [path to config file]
    --debug [enable debug mode]

Author: Your Name
Version: 1.0.0
"""

import sys
import argparse
import os
import time
import signal
import subprocess
from datetime import datetime

# ANSI color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

class AirQualityMonitor:
    def __init__(self, mode='receiver', debug=False):
        self.mode = mode
        self.debug = debug
        self.running = True
        self.receiver_process = None
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, sig, frame):
        """Handle Ctrl+C gracefully"""
        print(f"\n{Colors.YELLOW}Shutting down...{Colors.RESET}")
        self.running = False
        if self.receiver_process:
            self.receiver_process.terminate()
        sys.exit(0)
    
    def print_header(self):
        """Print application header"""
        print(f"\n{Colors.CYAN}{Colors.BOLD}")
        print("=" * 70)
        print("     AIR QUALITY INDEX MONITORING & RISK ANALYTICS")
        print("=" * 70)
        print(f"{Colors.RESET}")
        print(f"{Colors.GREEN}Mode: {self.mode.upper()}{Colors.RESET}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Debug: {'Enabled' if self.debug else 'Disabled'}")
        print("=" * 70 + "\n")
    
    def check_dependencies(self):
        """Check if required files and dependencies exist"""
        print(f"{Colors.BLUE}Checking dependencies...{Colors.RESET}")
        
        required_files = {
            'receiver': 'receiver/receiver_fixed.py',
            'analytics': 'analytics/aqi_forecasting.py',
            'dashboard': 'dashboard/index.html'
        }
        
        missing = []
        for name, path in required_files.items():
            if not os.path.exists(path):
                missing.append(f"{name} ({path})")
                print(f"{Colors.RED}✗ Missing: {path}{Colors.RESET}")
            else:
                print(f"{Colors.GREEN}✓ Found: {path}{Colors.RESET}")
        
        if missing:
            print(f"\n{Colors.RED}Missing required files:{Colors.RESET}")
            for item in missing:
                print(f"  - {item}")
            return False
        
        # Check Python packages
        try:
            import spidev
            import RPi.GPIO
            print(f"{Colors.GREEN}✓ Python dependencies installed{Colors.RESET}")
        except ImportError as e:
            print(f"{Colors.RED}✗ Missing Python package: {e}{Colors.RESET}")
            print(f"{Colors.YELLOW}Install with: sudo pip3 install spidev RPi.GPIO{Colors.RESET}")
            return False
        
        # Check SPI
        if not os.path.exists('/dev/spidev0.0'):
            print(f"{Colors.RED}✗ SPI not enabled{Colors.RESET}")
            print(f"{Colors.YELLOW}Enable with: sudo raspi-config → Interface Options → SPI{Colors.RESET}")
            return False
        else:
            print(f"{Colors.GREEN}✓ SPI enabled{Colors.RESET}")
        
        print(f"{Colors.GREEN}\n✓ All dependencies satisfied{Colors.RESET}\n")
        return True
    
    def run_receiver(self):
        """Run the LoRa receiver"""
        print(f"{Colors.CYAN}Starting LoRa Receiver...{Colors.RESET}\n")
        
        receiver_script = 'receiver/receiver_debug.py' if self.debug else 'receiver/receiver_fixed.py'
        
        if not os.path.exists(receiver_script):
            print(f"{Colors.RED}Error: Receiver script not found: {receiver_script}{Colors.RESET}")
            return
        
        try:
            # Run receiver script
            subprocess.run(['python3', receiver_script])
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Receiver stopped by user{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}Error running receiver: {e}{Colors.RESET}")
    
    def run_analytics(self):
        """Run data analytics and forecasting"""
        print(f"{Colors.CYAN}Running Analytics & Forecasting...{Colors.RESET}\n")
        
        analytics_script = 'analytics/aqi_forecasting.py'
        
        if not os.path.exists(analytics_script):
            print(f"{Colors.RED}Error: Analytics script not found: {analytics_script}{Colors.RESET}")
            return
        
        # Check if data file exists
        data_file = 'receiver/air_quality_data.csv'
        if not os.path.exists(data_file):
            print(f"{Colors.YELLOW}Warning: No data file found at {data_file}{Colors.RESET}")
            print(f"{Colors.YELLOW}Please run receiver first to collect data{Colors.RESET}")
            return
        
        try:
            subprocess.run(['python3', analytics_script])
        except Exception as e:
            print(f"{Colors.RED}Error running analytics: {e}{Colors.RESET}")
    
    def run_dashboard(self):
        """Start web dashboard server"""
        print(f"{Colors.CYAN}Starting Web Dashboard...{Colors.RESET}\n")
        
        dashboard_path = 'dashboard'
        
        if not os.path.exists(dashboard_path):
            print(f"{Colors.RED}Error: Dashboard directory not found: {dashboard_path}{Colors.RESET}")
            return
        
        port = 8000
        print(f"{Colors.GREEN}Dashboard server starting on port {port}{Colors.RESET}")
        print(f"{Colors.BLUE}Access at: http://localhost:{port}{Colors.RESET}")
        print(f"{Colors.BLUE}Or: http://raspberrypi.local:{port}{Colors.RESET}\n")
        print(f"{Colors.YELLOW}Press Ctrl+C to stop{Colors.RESET}\n")
        
        try:
            os.chdir(dashboard_path)
            subprocess.run(['python3', '-m', 'http.server', str(port)])
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Dashboard server stopped{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}Error starting dashboard: {e}{Colors.RESET}")
    
    def run_monitor(self):
        """Monitor system status and display live data"""
        print(f"{Colors.CYAN}System Monitor Mode{Colors.RESET}\n")
        
        data_file = 'receiver/air_quality_data.csv'
        
        print(f"{Colors.BLUE}Monitoring: {data_file}{Colors.RESET}")
        print(f"{Colors.YELLOW}Press Ctrl+C to stop{Colors.RESET}\n")
        
        try:
            # Check if file exists
            if not os.path.exists(data_file):
                print(f"{Colors.RED}No data file found. Start receiver first.{Colors.RESET}")
                return
            
            # Monitor file for changes
            last_size = 0
            while self.running:
                if os.path.exists(data_file):
                    current_size = os.path.getsize(data_file)
                    
                    if current_size != last_size:
                        # Read last line
                        with open(data_file, 'r') as f:
                            lines = f.readlines()
                            if len(lines) > 1:  # Skip header
                                last_line = lines[-1].strip()
                                parts = last_line.split(',')
                                
                                if len(parts) >= 6:
                                    timestamp = parts[0]
                                    temp = parts[2]
                                    humidity = parts[3]
                                    pm25 = parts[4]
                                    aqi = parts[5]
                                    risk = parts[6] if len(parts) > 6 else 'Unknown'
                                    
                                    # Color code based on risk
                                    if 'Good' in risk:
                                        risk_color = Colors.GREEN
                                    elif 'Moderate' in risk:
                                        risk_color = Colors.YELLOW
                                    elif 'Unhealthy' in risk:
                                        risk_color = Colors.RED
                                    else:
                                        risk_color = Colors.MAGENTA
                                    
                                    print(f"\n{Colors.CYAN}[{timestamp}]{Colors.RESET}")
                                    print(f"Temperature: {Colors.BOLD}{temp}°C{Colors.RESET}")
                                    print(f"Humidity: {Colors.BOLD}{humidity}%{Colors.RESET}")
                                    print(f"PM2.5: {Colors.BOLD}{pm25} µg/m³{Colors.RESET}")
                                    print(f"AQI: {Colors.BOLD}{aqi}{Colors.RESET}")
                                    print(f"Risk: {risk_color}{Colors.BOLD}{risk}{Colors.RESET}")
                                    print("-" * 50)
                        
                        last_size = current_size
                
                time.sleep(1)
        
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Monitor stopped{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}Error in monitor mode: {e}{Colors.RESET}")
    
    def show_menu(self):
        """Show interactive menu"""
        while self.running:
            print(f"\n{Colors.CYAN}{Colors.BOLD}=== Air Quality Monitor ==={Colors.RESET}\n")
            print(f"{Colors.GREEN}1.{Colors.RESET} Start Receiver (collect data)")
            print(f"{Colors.GREEN}2.{Colors.RESET} Run Analytics (analyze collected data)")
            print(f"{Colors.GREEN}3.{Colors.RESET} Start Dashboard (web interface)")
            print(f"{Colors.GREEN}4.{Colors.RESET} Monitor Live Data")
            print(f"{Colors.GREEN}5.{Colors.RESET} System Status")
            print(f"{Colors.GREEN}6.{Colors.RESET} View Logs")
            print(f"{Colors.RED}0.{Colors.RESET} Exit")
            
            try:
                choice = input(f"\n{Colors.YELLOW}Select option: {Colors.RESET}")
                
                if choice == '1':
                    self.run_receiver()
                elif choice == '2':
                    self.run_analytics()
                elif choice == '3':
                    self.run_dashboard()
                elif choice == '4':
                    self.run_monitor()
                elif choice == '5':
                    self.show_status()
                elif choice == '6':
                    self.view_logs()
                elif choice == '0':
                    print(f"{Colors.GREEN}Goodbye!{Colors.RESET}")
                    break
                else:
                    print(f"{Colors.RED}Invalid option{Colors.RESET}")
            
            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}Exiting...{Colors.RESET}")
                break
    
    def show_status(self):
        """Show system status"""
        print(f"\n{Colors.CYAN}=== System Status ==={Colors.RESET}\n")
        
        # Check data file
        data_file = 'receiver/air_quality_data.csv'
        if os.path.exists(data_file):
            with open(data_file, 'r') as f:
                lines = len(f.readlines()) - 1  # Exclude header
            print(f"{Colors.GREEN}✓{Colors.RESET} Data file: {lines} records")
        else:
            print(f"{Colors.RED}✗{Colors.RESET} No data file found")
        
        # Check alert log
        alert_file = 'receiver/air_quality_alerts.log'
        if os.path.exists(alert_file):
            size = os.path.getsize(alert_file)
            print(f"{Colors.GREEN}✓{Colors.RESET} Alert log: {size} bytes")
        else:
            print(f"{Colors.YELLOW}!{Colors.RESET} No alerts logged")
        
        # Check processes
        try:
            result = subprocess.run(['pgrep', '-f', 'receiver_fixed.py'], 
                                  capture_output=True, text=True)
            if result.stdout:
                print(f"{Colors.GREEN}✓{Colors.RESET} Receiver: Running (PID: {result.stdout.strip()})")
            else:
                print(f"{Colors.YELLOW}!{Colors.RESET} Receiver: Not running")
        except:
            pass
        
        print()
    
    def view_logs(self):
        """View recent log entries"""
        print(f"\n{Colors.CYAN}=== Recent Data ==={Colors.RESET}\n")
        
        data_file = 'receiver/air_quality_data.csv'
        if os.path.exists(data_file):
            try:
                subprocess.run(['tail', '-20', data_file])
            except:
                print(f"{Colors.RED}Error reading logs{Colors.RESET}")
        else:
            print(f"{Colors.RED}No data file found{Colors.RESET}")
        
        input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.RESET}")
    
    def run(self):
        """Main run method"""
        self.print_header()
        
        # Check dependencies
        if not self.check_dependencies():
            print(f"\n{Colors.RED}Cannot start: Missing dependencies{Colors.RESET}")
            return
        
        # Run based on mode
        if self.mode == 'receiver':
            self.run_receiver()
        elif self.mode == 'analytics':
            self.run_analytics()
        elif self.mode == 'dashboard':
            self.run_dashboard()
        elif self.mode == 'monitor':
            self.run_monitor()
        elif self.mode == 'menu':
            self.show_menu()
        else:
            print(f"{Colors.RED}Invalid mode: {self.mode}{Colors.RESET}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Air Quality Monitor - Control Script',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sudo python3 main.py                    # Interactive menu
  sudo python3 main.py --mode receiver    # Start receiver
  sudo python3 main.py --mode analytics   # Run analytics
  sudo python3 main.py --mode dashboard   # Start dashboard
  sudo python3 main.py --mode monitor     # Live monitoring
  sudo python3 main.py --debug            # Enable debug mode
        """
    )
    
    parser.add_argument('--mode', 
                       choices=['receiver', 'analytics', 'dashboard', 'monitor', 'menu'],
                       default='menu',
                       help='Operation mode (default: menu)')
    
    parser.add_argument('--debug',
                       action='store_true',
                       help='Enable debug mode with verbose output')
    
    parser.add_argument('--version',
                       action='version',
                       version='Air Quality Monitor v1.0.0')
    
    args = parser.parse_args()
    
    # Check if running as root
    if os.geteuid() != 0:
        print(f"{Colors.RED}Error: This script must be run as root{Colors.RESET}")
        print(f"{Colors.YELLOW}Use: sudo python3 main.py{Colors.RESET}")
        sys.exit(1)
    
    # Create and run monitor
    monitor = AirQualityMonitor(mode=args.mode, debug=args.debug)
    monitor.run()


if __name__ == '__main__':
    main()
