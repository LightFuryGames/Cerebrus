# Installer Overview

This document summarizes the goals and layout of the Windows installer.

## Goals

- Provide a one-click installation experience.
- Bundle a compatible Python runtime and dependencies.
- Configure default paths for logs, cache, and reports.
- Avoid requiring administrative privileges unless necessary.
- **Studio Ready**: Support silent install flags (e.g. `/VERYSILENT`) for IT mass-deployment.

## Responsibilities

The installer should:

- Install Cerebrus binaries and scripts into a user-writable location.
- Install or bundle:
  - Python interpreter.
  - Required Python packages.
- Create shortcuts:
  - Start Menu entry.
  - Optional desktop shortcut.
- Register file associations only if explicitly requested (e.g. `.cerebrusprofile`).

Technical implementation details are in `docs/installer/WINDOWS_INSTALLER_SPEC.md`.
