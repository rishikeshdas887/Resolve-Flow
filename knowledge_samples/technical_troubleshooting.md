# Technical Troubleshooting Guide (Synthetic Demo Document)

Synthetic demonstration content for ResolveFlow.

## Login problems
- Error E1001: wrong email or password. Try the "Forgot password" flow.
- Error E1002: account locked after 5 failed attempts. Wait 15 minutes or
  reset the password.
- Error E2003: session expired. Log in again; check that cookies are enabled.

## App crashes
- Ask for the app version, device/OS, and the steps that reproduce the crash.
- Clearing the app cache resolves most crashes after an update.
- Crash reports with error code E5000+ should be escalated to engineering.

## Sync issues
- Data syncs every 60 seconds while online.
- Offline changes queue locally and merge when connectivity returns.
- If sync conflicts persist, export local data before reinstalling.
