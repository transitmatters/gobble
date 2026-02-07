# Deployment

Gobble runs on AWS EC2 and is deployed using CloudFormation, Ansible, and systemd.

## Infrastructure

| Component     | Details                                   |
| ------------- | ----------------------------------------- |
| Instance type | `t4g.small` (ARM/Graviton)                |
| OS            | Ubuntu (ARM64 AMI)                        |
| Storage       | 32 GB gp3 EBS volume                      |
| IAM           | S3 access to `tm-mbta-performance` bucket |
| Monitoring    | Datadog APM, logs, and profiling          |

## How to deploy

From the project root:

```bash
cd devops
bash ./deploy.sh -p -c
```

The deploy script uses Ansible to:

1. Install system dependencies (Python 3.13, uv)
2. Clone/update the repository
3. Install Python dependencies
4. Copy configuration files
5. Set up the systemd service
6. Configure the S3 upload cron job

## systemd service

Gobble runs as a systemd service that automatically restarts on failure. The service configuration is in `devops/systemd.conf`.

## S3 upload cron

A cron job runs `s3_upload.py` every 30 minutes to sync today's event data to S3:

```
*/30 * * * * cd /path/to/gobble && uv run src/s3_upload.py
```

## CloudFormation

The AWS infrastructure is defined in `devops/cloudformation.json`, which provisions:

- EC2 instance with appropriate instance profile
- IAM role with S3 write permissions
- Security group configuration
