# Alert runbook

First steps for each alarm. SSH in, and note the time the alert fired.

## cpu-high
```bash
top -o %CPU            # or: ps aux --sort=-%cpu | head
uptime                 # load average vs number of cores (nproc)
```
Identify the process. If it is a runaway job, check its logs before restarting it, then record the cause.

## mem-high
```bash
free -h
ps aux --sort=-%mem | head
dmesg | grep -i "out of memory"    # OOM killer events
```
Steadily climbing memory with no drop suggests a leak. Capture evidence before restarting the service.

## disk-high
```bash
df -h
sudo du -xh / --max-depth=2 2>/dev/null | sort -h | tail -20
sudo journalctl --disk-usage
```
Common causes: logs that are not rotated, old deployments, container images. Also check `df -i` for inode exhaustion.

## status-check
Instance or system status check failed. Look at the EC2 console, then try a reboot. If it is a system check failure, stop and start the instance, which moves it to new hardware. Check the system log from the console.

## After any alert
Write a short RCA: what fired, the root cause, the fix, and how to stop it recurring.
