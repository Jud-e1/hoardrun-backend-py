#!/usr/bin/env python3
"""
Install dependencies for the HoardRun backend.
"""

import subprocess
import sys
import os

def run_command(command, description):
    """Run a command and print the result."""
    print(f"\n🔧 {description}")
    print("-" * 50)
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=os.path.dirname(__file__)
        )
        
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
            
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
        else:
            print(f"❌ {description} failed with return code {result.returncode}")
            
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Error running {description}: {e}")
        return False

def main():
    """Install all dependencies."""
    print("🚀 Installing HoardRun Backend Dependencies")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not os.path.exists("fintech_backend/requirements.txt"):
        print("❌ Error: requirements.txt not found. Make sure you're in the hoardrun-backend-py directory.")
        return 1
    
    # Try different Python/pip combinations
    python_commands = [
        "myenv/bin/python -m pip",
        "myenv\\Scripts\\python -m pip",
        "python -m pip",
        "python3 -m pip",
        "pip",
        "pip3"
    ]
    
    requirements_file = "fintech_backend/requirements.txt"
    
    for python_cmd in python_commands:
        print(f"\n🔍 Trying: {python_cmd}")
        
        # First check if the command works
        if run_command(f"{python_cmd} --version", f"Testing {python_cmd}"):
            # Try to install requirements
            if run_command(f"{python_cmd} install -r {requirements_file}", f"Installing requirements with {python_cmd}"):
                print(f"\n✅ Successfully installed dependencies using {python_cmd}")
                
                # Test if pydantic is now available
                test_cmd = python_cmd.replace(" -m pip", "")
                if run_command(f'{test_cmd} -c "import pydantic; print(f\'Pydantic {pydantic.VERSION} installed successfully\')"', "Testing pydantic import"):
                    print("\n🎉 All dependencies installed successfully!")
                    return 0
                    
        print(f"❌ {python_cmd} didn't work, trying next option...")
    
    print("\n❌ Could not install dependencies with any Python/pip combination.")
    print("\n💡 Manual installation options:")
    print("1. Try activating the virtual environment manually:")
    print("   - Windows: myenv\\Scripts\\activate")
    print("   - Linux/Mac: source myenv/bin/activate")
    print("2. Then run: pip install -r fintech_backend/requirements.txt")
    print("3. Or create a new virtual environment:")
    print("   - python -m venv new_env")
    print("   - Activate it and install requirements")
    
    return 1

if __name__ == "__main__":
    sys.exit(main())
