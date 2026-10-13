#!/usr/bin/env python3
"""Generate a markdown health report for an EC2 instance from CloudWatch metrics.

Pulls average and peak CPU, memory and disk usage for the last N hours and lists
the current state of the instance's alarms. Output goes to the terminal and to
reports/health-<instance>-<date>.md
"""
import argparse
import datetime as dt
import os

import boto3

METRICS = [
    # label, namespace, metric name, warning threshold (%)
    ("CPU", "AWS/EC2", "CPUUtilization", 80),
    ("Memory", "CWAgent", "mem_used_percent", 80),
    ("Disk (/)", "CWAgent", "disk_used_percent", 85),
]


def metric_summary(cloudwatch, namespace, metric, instance_id, hours):
    end = dt.datetime.now(dt.timezone.utc)
    start = end - dt.timedelta(hours=hours)
    response = cloudwatch.get_metric_statistics(
        Namespace=namespace,
        MetricName=metric,
        Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
        StartTime=start,
        EndTime=end,
        Period=300,
        Statistics=["Average", "Maximum"],
    )
    points = response["Datapoints"]
    if not points:
        return None
    average = sum(p["Average"] for p in points) / len(points)
    peak = max(p["Maximum"] for p in points)
    return average, peak


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--region", default=None)
    parser.add_argument("--hours", type=int, default=24, help="Look-back window (default 24)")
    parser.add_argument("--output-dir", default="reports")
    args = parser.parse_args()

    session = boto3.Session(region_name=args.region)
    cloudwatch = session.client("cloudwatch")
    now = dt.datetime.now(dt.timezone.utc)

    lines = [
        f"# Health report: {args.instance_id}",
        f"Generated {now:%Y-%m-%d %H:%M} UTC, covering the last {args.hours} hours.",
        "",
        "| Metric | Average | Peak | Status |",
        "|---|---|---|---|",
    ]
    for label, namespace, metric, warn in METRICS:
        summary = metric_summary(cloudwatch, namespace, metric, args.instance_id, args.hours)
        if summary is None:
            lines.append(f"| {label} | n/a | n/a | NO DATA (is the agent running?) |")
            continue
        average, peak = summary
        status = "WARN" if peak >= warn else "OK"
        lines.append(f"| {label} | {average:.1f}% | {peak:.1f}% | {status} (warn at {warn}%) |")

    alarms = cloudwatch.describe_alarms(AlarmNamePrefix=args.instance_id)["MetricAlarms"]
    lines += ["", "## Alarm states", "", "| Alarm | State |", "|---|---|"]
    if alarms:
        for alarm in sorted(alarms, key=lambda a: a["AlarmName"]):
            lines.append(f"| {alarm['AlarmName']} | {alarm['StateValue']} |")
    else:
        lines.append("| (none found) | - |")

    report = "\n".join(lines) + "\n"
    print(report)

    os.makedirs(args.output_dir, exist_ok=True)
    path = os.path.join(args.output_dir, f"health-{args.instance_id}-{now:%Y%m%d}.md")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(report)
    print(f"Saved to {path}")


if __name__ == "__main__":
    main()
