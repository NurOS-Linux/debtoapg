#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2025 AnmiTaliDev (taliildar)
# Created: 2025-01-06 15:56:29 UTC
# This program is licensed under the GNU GPL v3.
# See LICENSE file for details.

import os
import sys
import json
import shutil
import tarfile
import hashlib
import tempfile
import argparse
import subprocess
from datetime import datetime
from termcolor import colored

class DebToApgConverter:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.temp_dir = None
        self.version = "1.0.0"
        self.total_steps = 4
        self.current_step = 0

    def print_version(self):
        version_info = f"""
{colored('AnmiTali/NurOS debtoapg v' + self.version, 'green')}
{colored('License:', 'blue')} GNU GPLv3
{colored('Contributors:', 'blue')} AnmiTaliDev (taliildar)
{colored('URL:', 'blue')} https://github.com/NurOS-Linux/debtoapg
{colored('Site:', 'blue')} nuros.anmitali.kz
"""
        print(version_info)

    def print_banner(self):
        banner = f"""
{colored('╔══════════════════════════════════════════════════╗', 'blue')}
{colored('║', 'blue')}           {colored('DebToApg Package Converter', 'green')}          {colored('║', 'blue')}
{colored('║', 'blue')}                Version {self.version}                   {colored('║', 'blue')}
{colored('║', 'blue')}          {colored('© AnmiTali/NurOS Linux', 'cyan')}             {colored('║', 'blue')}
{colored('╚══════════════════════════════════════════════════╝', 'blue')}
"""
        print(banner)

    def update_progress(self, message):
        self.current_step += 1
        percentage = (self.current_step / self.total_steps) * 100
        progress_bar = ('=' * int(percentage/2)).ljust(50, ' ')
        print(colored(f"\r[{progress_bar}] {percentage:.1f}% - {message}", 'cyan'), end='')
        if percentage == 100:
            print()

    def log(self, message, level="info"):
        colors = {
            "info": "blue",
            "success": "green",
            "warning": "yellow",
            "error": "red",
            "process": "cyan"
        }
        prefix = {
            "info": "ℹ",
            "success": "✔",
            "warning": "⚠",
            "error": "✖",
            "process": "⚙"
        }
        if self.verbose or level in ["error", "success", "warning"]:
            print(colored(f"{prefix[level]} {message}", colors[level]))

    def validate_deb(self, input_file):
        if not os.path.exists(input_file):
            raise ValueError("Input file does not exist")
        if not input_file.endswith('.deb'):
            raise ValueError("Input file must be a .deb package")
        try:
            subprocess.run(['dpkg-deb', '--info', input_file], capture_output=True, check=True)
            subprocess.run(['dpkg-deb', '--contents', input_file], capture_output=True, check=True)
            self.log("Package validation successful", "success")
            return True
        except subprocess.CalledProcessError as e:
            raise ValueError(f"Invalid or corrupted .deb package: {e.stderr.decode()}")

    def extract_deb(self, input_file):
        self.log(f"Extracting {input_file}...", "process")
        self.update_progress("Extracting DEB package")
        self.temp_dir = tempfile.mkdtemp()
        try:
            subprocess.run(['dpkg-deb', '-R', input_file, self.temp_dir], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            self.cleanup()
            raise RuntimeError(f"Failed to extract .deb: {e.stderr.decode()}")

    def generate_metadata(self):
        self.update_progress("Generating metadata")
        debian_dir = os.path.join(self.temp_dir, 'DEBIAN')
        metadata = {
            "created": datetime.utcnow().isoformat(),
            "converter_version": self.version,
            "converter": "debtoapg",
            "author": "AnmiTaliDev"
        }
        control_files = ['control', 'preinst', 'postinst', 'prerm', 'postrm', 'triggers', 'conffiles']
        for file in control_files:
            file_path = os.path.join(debian_dir, file)
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    metadata[file] = f.read()
        return metadata

    def calculate_checksums(self, directory):
        self.update_progress("Calculating checksums")
        checksums = {}
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, directory)
                with open(file_path, 'rb') as f:
                    checksums[rel_path] = hashlib.sha256(f.read()).hexdigest()
        return checksums

    def create_apg(self, output_file):
        self.log("Creating APG structure...", "process")
        apg_root = os.path.join(self.temp_dir, 'apg')
        os.makedirs(apg_root)
        os.makedirs(os.path.join(apg_root, 'data'))
        
        data_source = os.path.join(self.temp_dir)
        data_dest = os.path.join(apg_root, 'data')
        for item in os.listdir(data_source):
            if item != 'DEBIAN' and item != 'apg':
                src = os.path.join(data_source, item)
                dst = os.path.join(data_dest, item)
                shutil.move(src, dst)

        with open(os.path.join(apg_root, 'metadata.json'), 'w') as f:
            json.dump(self.generate_metadata(), f, indent=2)

        with open(os.path.join(apg_root, 'checksums.json'), 'w') as f:
            json.dump(self.calculate_checksums(data_dest), f, indent=2)

        self.update_progress("Creating APG archive")
        with tarfile.open(output_file, 'w:xz') as tar:
            tar.add(apg_root, arcname='')

    def cleanup(self):
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def convert(self, input_file, output_file):
        self.print_banner()
        try:
            print("\nStarting conversion process:")
            self.validate_deb(input_file)
            self.extract_deb(input_file)
            self.create_apg(output_file)
            size_mb = os.path.getsize(output_file) / (1024 * 1024)
            self.log(f"\nSuccessfully created {output_file} ({size_mb:.1f} MB)", "success")
        except Exception as e:
            self.log(f"Conversion failed: {str(e)}", "error")
            raise
        finally:
            self.cleanup()

def main():
    parser = argparse.ArgumentParser(
        description='Convert Debian (.deb) packages to AnmiTali Package Format (.apg)',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('input', nargs='?', help='Input .deb file')
    parser.add_argument('-o', '--output', help='Output .apg file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--version', action='store_true', help='Show version information')
    
    args = parser.parse_args()
    converter = DebToApgConverter(verbose=args.verbose)

    if args.version:
        converter.print_version()
        return 0

    if not args.input or not args.output:
        parser.print_help()
        return 1

    try:
        converter.convert(args.input, args.output)
        return 0
    except KeyboardInterrupt:
        print("\n")
        print(colored("✖ Operation cancelled by user", "yellow"))
        return 130
    except Exception as e:
        print(colored(f"✖ Error: {str(e)}", "red"))
        return 1

if __name__ == "__main__":
    sys.exit(main())