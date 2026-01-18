#!/usr/bin/env python
"""
Simple script to check the latest OTP code from the file.
Run this script: python check_otp.py
"""
import os
from pathlib import Path

# Get the backend directory
backend_dir = Path(__file__).parent
otp_file = backend_dir / 'otp_code.txt'

if otp_file.exists():
    print("\n" + "="*80)
    print("OTP CODE FILE FOUND!")
    print("="*80)
    with open(otp_file, 'r') as f:
        content = f.read()
        print(content)
    print("="*80 + "\n")
else:
    print("\n" + "="*80)
    print("OTP file not found yet.")
    print("Please log in or resend OTP, then run this script again.")
    print(f"Expected file location: {otp_file}")
    print("="*80 + "\n")

