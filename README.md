# AWS Server Health Monitoring & Alerting

Monitor an EC2 instance with CloudWatch, get **email alerts through SNS** when CPU, memory, disk or status checks go wrong, and generate a **daily health report** with Python (boto3).

> **Status:** work in progress. The scripts are written, and I am still testing them against a live AWS account. Screenshots and real output will be added after that.

<!-- TODO: add a screenshot of your CloudWatch dashboard / alarm list here -->
<!-- TODO: add a screenshot of a real alert email here -->

## What it does

| Piece | Purpose |
|---|---|
| CloudWatch agent | Collects memory and disk usage, which EC2 does **not** report by default |
| `setup_alarms.py` | Creates an SNS topic, an email subscription and four alarms |
| `health_report.py` | Pulls the last 24 h of metrics and writes a markdown report |
| `docs/runbook.md` | First-response steps for each alarm |

## Architecture

```
EC2 instance
  |-- CloudWatch agent (memory, disk) --+
  |-- built-in EC2 metrics (CPU, status)-+--> CloudWatch metrics
                                                  |
                                          CloudWatch alarms (threshold + duration)
                                                  |
                                              SNS topic --> email
                                                  
health_report.py --> reads metrics + alarm states --> reports/*.md
```

## Alarms

| Alarm | Metric | Default trigger |
|---|---|---|
| cpu-high | `AWS/EC2` CPUUtilization | average above 80% for 15 min |
| mem-high | `CWAgent` mem_used_percent | average above 80% for 15 min |
| disk-high | `CWAgent` disk_used_percent | average above 85% for 10 min |
| status-check | `AWS/EC2` StatusCheckFailed | failing for 2 consecutive minutes |

Alarms need several consecutive bad data points before they fire, so a short spike does not page anyone. Thresholds are configurable with flags.

## Prerequisites

- An AWS account and an EC2 instance (Amazon Linux or Ubuntu)
- An IAM role attached to the instance with the AWS-managed policy **CloudWatchAgentServerPolicy**
- AWS credentials on your own machine for the scripts (`aws configure`) with permission to use CloudWatch and SNS
- Python 3.8+

## Setup

### 1. Install and start the CloudWatch agent on the instance

Amazon Linux 2023:
```bash
sudo dnf install -y amazon-cloudwatch-agent
```
Ubuntu: download the `.deb` package for your architecture from the AWS documentation ("Installing the CloudWatch agent"), then `sudo dpkg -i` it.

Copy `config/cloudwatch-agent-config.json` to the instance, then:
```bash
sudo cp cloudwatch-agent-config.json /opt/aws/amazon-cloudwatch-agent/etc/config.json
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config -m ec2 -c file:/opt/aws/amazon-cloudwatch-agent/etc/config.json -s
```
After a few minutes, `CWAgent` metrics appear in the CloudWatch console. The config also publishes the metrics with only the `InstanceId` dimension (`aggregation_dimensions`), which keeps the alarm definitions simple.

### 2. Create the alarms and email alerts

```bash
git clone https://github.com/bhatiasachin964-dot/aws-server-health-monitor.git
cd aws-server-health-monitor
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

python scripts/setup_alarms.py --instance-id i-0123456789abcdef0 --email you@example.com --region ap-south-1
```
**Confirm the subscription email from AWS**, otherwise no alerts are delivered.

### 3. Test that alerts work

Fast check, without stressing the server:
```bash
aws cloudwatch set-alarm-state --alarm-name i-0123456789abcdef0-cpu-high \
  --state-value ALARM --state-reason "testing notifications"
```
Real check: generate load on the instance (for example with `stress-ng --cpu 2 --timeout 1200`, installing it first) and wait for the alarm to fire.

### 4. Generate a health report

```bash
python scripts/health_report.py --instance-id i-0123456789abcdef0 --region ap-south-1
```
Example output format (illustrative values, not a real run):

```
| Metric   | Average | Peak  | Status           |
|----------|---------|-------|------------------|
| CPU      | 6.2%    | 41.0% | OK (warn at 80%) |
| Memory   | 38.5%   | 52.1% | OK (warn at 80%) |
| Disk (/) | 24.0%   | 24.0% | OK (warn at 85%) |
```

To run it daily, add a cron entry on a machine with AWS credentials:
```
0 8 * * * cd /path/to/aws-server-health-monitor && ./venv/bin/python scripts/health_report.py --instance-id i-0123456789abcdef0
```

## Clean up (avoid charges)

```bash
aws cloudwatch delete-alarms --alarm-names \
  i-0123456789abcdef0-cpu-high i-0123456789abcdef0-mem-high \
  i-0123456789abcdef0-disk-high i-0123456789abcdef0-status-check
aws sns delete-topic --topic-arn <your-topic-arn>
```
Stop the CloudWatch agent and stop or terminate the instance when you are done. Custom metrics and alarms can cost money beyond the free tier, so check current AWS pricing.

## Security notes

- The instance role uses the AWS-managed `CloudWatchAgentServerPolicy` only.
- No credentials are stored in this repo. The scripts use your normal AWS credential chain.
- Reports are git-ignored because they contain your instance IDs.

## Ideas for next steps

- [ ] Deploy the setup with Terraform (see my IaC project)
- [ ] Send alerts to Slack through AWS Chatbot or a Lambda function
- [ ] Add a CloudWatch dashboard definition
- [ ] Run the report on a schedule with Lambda and EventBridge

## Author

**Sachin Bhatia** · [LinkedIn](https://linkedin.com/in/sachin-bhatia-725a7a1a0) · [GitHub](https://github.com/bhatiasachin964-dot)
