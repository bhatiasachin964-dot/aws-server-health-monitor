#!/usr/bin/env python3
"""Create an SNS topic, an email subscription and CloudWatch alarms for one EC2 instance.

Alarms created (names are prefixed with the instance ID):
  - cpu-high      AWS/EC2  CPUUtilization       (no agent needed)
  - mem-high      CWAgent  mem_used_percent     (needs the CloudWatch agent)
  - disk-high     CWAgent  disk_used_percent    (needs the CloudWatch agent)
  - status-check  AWS/EC2  StatusCheckFailed    (instance or system check failed)

After running, confirm the subscription email that AWS sends, otherwise no alerts arrive.
"""
import argparse

import boto3


def build_alarms(args):
    # (suffix, namespace, metric, statistic, threshold, period, eval periods, description)
    return [
        ("cpu-high", "AWS/EC2", "CPUUtilization", "Average", args.cpu_threshold, 300, 3,
         f"CPU above {args.cpu_threshold}% for 15 minutes"),
        ("mem-high", "CWAgent", "mem_used_percent", "Average", args.mem_threshold, 300, 3,
         f"Memory above {args.mem_threshold}% for 15 minutes"),
        ("disk-high", "CWAgent", "disk_used_percent", "Average", args.disk_threshold, 300, 2,
         f"Root disk above {args.disk_threshold}% for 10 minutes"),
        ("status-check", "AWS/EC2", "StatusCheckFailed", "Maximum", 0, 60, 2,
         "EC2 instance or system status check failing"),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--instance-id", required=True, help="EC2 instance ID, e.g. i-0abc123")
    parser.add_argument("--email", required=True, help="Email address for alert notifications")
    parser.add_argument("--region", default=None, help="AWS region (default: from your AWS config)")
    parser.add_argument("--topic-name", default="ec2-health-alerts")
    parser.add_argument("--cpu-threshold", type=float, default=80)
    parser.add_argument("--mem-threshold", type=float, default=80)
    parser.add_argument("--disk-threshold", type=float, default=85)
    args = parser.parse_args()

    session = boto3.Session(region_name=args.region)
    sns = session.client("sns")
    cloudwatch = session.client("cloudwatch")

    topic_arn = sns.create_topic(Name=args.topic_name)["TopicArn"]
    sns.subscribe(TopicArn=topic_arn, Protocol="email", Endpoint=args.email)
    print(f"SNS topic ready: {topic_arn}")
    print(f"Confirmation email sent to {args.email} - click the link in it.")

    dimensions = [{"Name": "InstanceId", "Value": args.instance_id}]
    for suffix, namespace, metric, stat, threshold, period, periods, desc in build_alarms(args):
        name = f"{args.instance_id}-{suffix}"
        cloudwatch.put_metric_alarm(
            AlarmName=name,
            AlarmDescription=desc,
            Namespace=namespace,
            MetricName=metric,
            Dimensions=dimensions,
            Statistic=stat,
            Period=period,
            EvaluationPeriods=periods,
            DatapointsToAlarm=periods,
            Threshold=threshold,
            ComparisonOperator="GreaterThanThreshold",
            TreatMissingData="missing",
            AlarmActions=[topic_arn],
            OKActions=[topic_arn],
        )
        print(f"Alarm created: {name}  ({desc})")


if __name__ == "__main__":
    main()
