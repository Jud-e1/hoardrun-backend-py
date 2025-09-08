#!/usr/bin/env python3
"""
Deployment readiness test script for Hoardrun Backend.
This script verifies that all necessary components are in place for deployment.
"""

import os
import sys
import subprocess
from pathlib import Path

def check_file_exists(file_path, description):
    """Check if a file exists and print status."""
    if Path(file_path).exists():
        print(f"✅ {description}: {file_path}")
        return True
    else:
        print(f"❌ {description}: {file_path} - NOT FOUND")
        return False

def check_directory_exists(dir_path, description):
    """Check if a directory exists and print status."""
    if Path(dir_path).is_dir():
        print(f"✅ {description}: {dir_path}")
        return True
    else:
        print(f"❌ {description}: {dir_path} - NOT FOUND")
        return False

def check_python_syntax(file_path):
    """Check if a Python file has valid syntax."""
    try:
        with open(file_path, 'r') as f:
            compile(f.read(), file_path, 'exec')
        print(f"✅ Python syntax valid: {file_path}")
        return True
    except SyntaxError as e:
        print(f"❌ Python syntax error in {file_path}: {e}")
        return False
    except Exception as e:
        print(f"❌ Error checking {file_path}: {e}")
        return False

def main():
    """Run deployment readiness checks."""
    print("🚀 Hoardrun Backend Deployment Readiness Check")
    print("=" * 50)
    
    all_checks_passed = True
    
    # Check essential deployment files
    print("\n📁 Deployment Configuration Files:")
    essential_files = [
        ("render.yaml", "Render deployment configuration"),
        ("Dockerfile", "Docker configuration"),
        (".dockerignore", "Docker ignore file"),
        ("DEPLOYMENT_GUIDE.md", "Deployment guide"),
    ]
    
    for file_path, description in essential_files:
        if not check_file_exists(file_path, description):
            all_checks_passed = False
    
    # Check application structure
    print("\n📂 Application Structure:")
    app_structure = [
        ("fintech_backend/", "Main application directory"),
        ("fintech_backend/app/", "App source code"),
        ("fintech_backend/app/main.py", "Application entry point"),
        ("fintech_backend/requirements.txt", "Python dependencies"),
        ("fintech_backend/.env.example", "Environment variables template"),
        ("fintech_backend/alembic/", "Database migrations"),
        ("fintech_backend/alembic.ini", "Alembic configuration"),
    ]
    
    for path, description in app_structure:
        if path.endswith('/'):
            if not check_directory_exists(path, description):
                all_checks_passed = False
        else:
            if not check_file_exists(path, description):
                all_checks_passed = False
    
    # Check Python syntax for critical files
    print("\n🐍 Python Syntax Validation:")
    python_files = [
        "fintech_backend/app/main.py",
        "fintech_backend/app/config/settings.py",
        "fintech_backend/app/database/config.py",
        "fintech_backend/alembic/env.py",
    ]
    
    for file_path in python_files:
        if Path(file_path).exists():
            if not check_python_syntax(file_path):
                all_checks_passed = False
        else:
            print(f"⚠️  Skipping syntax check for missing file: {file_path}")
    
    # Check requirements.txt content
    print("\n📦 Dependencies Check:")
    req_file = "fintech_backend/requirements.txt"
    if Path(req_file).exists():
        with open(req_file, 'r') as f:
            requirements = f.read()
            essential_deps = ['fastapi', 'uvicorn', 'sqlalchemy', 'alembic', 'psycopg2-binary']
            missing_deps = []
            
            for dep in essential_deps:
                if dep not in requirements.lower():
                    missing_deps.append(dep)
            
            if missing_deps:
                print(f"❌ Missing essential dependencies: {', '.join(missing_deps)}")
                all_checks_passed = False
            else:
                print("✅ All essential dependencies found in requirements.txt")
    
    # Check environment variables template
    print("\n🔧 Environment Configuration:")
    env_example = "fintech_backend/.env.example"
    if Path(env_example).exists():
        with open(env_example, 'r') as f:
            env_content = f.read()
            essential_vars = ['DATABASE_URL', 'SECRET_KEY', 'ENVIRONMENT']
            missing_vars = []
            
            for var in essential_vars:
                if var not in env_content:
                    missing_vars.append(var)
            
            if missing_vars:
                print(f"❌ Missing essential environment variables: {', '.join(missing_vars)}")
                all_checks_passed = False
            else:
                print("✅ All essential environment variables found in .env.example")
    
    # Final summary
    print("\n" + "=" * 50)
    if all_checks_passed:
        print("🎉 ALL CHECKS PASSED! Your application is ready for deployment.")
        print("\nNext steps:")
        print("1. Push your code to GitHub")
        print("2. Connect your repository to Render")
        print("3. Follow the DEPLOYMENT_GUIDE.md for detailed instructions")
        return 0
    else:
        print("❌ SOME CHECKS FAILED! Please fix the issues above before deploying.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
