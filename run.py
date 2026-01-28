"""
Quick Start Script - Installs dependencies and runs the application
"""

import subprocess
import sys
import os

def main():
    print("="*60)
    print("  FacePass - Setup")
    print("="*60)
    print()
    
    # Check Python version
    python_version = sys.version_info
    print(f"Python Version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 9):
        print("ERROR: Python 3.9+ is required!")
        return
    
    print("\n[1/3] Installing dependencies...")
    print("-"*40)
    
    try:
        # Upgrade pip first
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        
        # Install cmake (required for dlib)
        print("\nInstalling cmake...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "cmake"])
        
        # Install requirements
        print("\nInstalling requirements...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ])
        
        print("\n✓ Dependencies installed successfully!")
        
    except subprocess.CalledProcessError as e:
        print(f"\n⚠ Error installing some dependencies: {e}")
        print("\nTroubleshooting tips:")
        print("1. For dlib issues on Windows:")
        print("   - Install Visual Studio Build Tools")
        print("   - Or try: pip install dlib --pre")
        print("\n2. If face_recognition fails, try:")
        print("   pip install face_recognition --no-deps")
        print("   pip install dlib")
        print()
        return
    
    print("\n[2/3] Creating directories...")
    print("-"*40)
    
    os.makedirs("face_encodings", exist_ok=True)
    os.makedirs("registered_faces", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("static", exist_ok=True)
    
    print("✓ Directories created")
    
    print("\n[3/3] Starting application...")
    print("-"*40)
    print()
    print("Server starting at: http://localhost:8000")
    print("Press Ctrl+C to stop")
    print()
    
    try:
        subprocess.call([sys.executable, "main.py"])
    except KeyboardInterrupt:
        print("\n\n✓ Application stopped")


if __name__ == "__main__":
    main()
