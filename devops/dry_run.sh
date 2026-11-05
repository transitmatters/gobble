#!/bin/bash
# Test-provision a throwaway instance with the AMI in cloudformation.json and this branch's playbook, before
# rebuilding production on a new image. The test instance:
#   - has no IAM instance profile, so it can't read or write the S3 bucket
#   - skips the S3 upload cron and reports to Datadog as env:dryrun
#   - is tagged service:gobble-dryrun, outside the gobble stack
# It still runs the Datadog Agent with the gobble.service check, so expect the "Gobble service has restarted"
# monitor to fire for its host unless you mute that host in Datadog first.
# Terminate it when you're done; the command is printed at the start and the end.
#
# usage: cd devops && DD_API_KEY=... bash dry_run.sh <branch to deploy>
# Needs devops/local.json (the same config deploy.sh's playbook copies to the box) and ~/.ssh/transitmatters-gobble.pem
set -e

export AWS_PROFILE=transitmatters
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1
export AWS_PAGER=""

BRANCH="$1"
if [[ -z "$BRANCH" ]]; then
    echo "usage: bash dry_run.sh <branch to deploy>" 1>&2
    exit 1
fi
if [[ -z "$DD_API_KEY" ]]; then
    echo "Must provide DD_API_KEY in environment" 1>&2
    exit 1
fi
if [[ ! -f local.json ]]; then
    echo "Must have devops/local.json" 1>&2
    exit 1
fi

export GIT_SHA=$(git rev-parse "origin/$BRANCH")
AMI_ID=$(grep -o '"ImageId": "ami-[0-9a-f]*"' cloudformation.json | grep -o 'ami-[0-9a-f]*')
SG_ID=$(aws ec2 describe-security-groups --group-names GBLE-securitygroup --query "SecurityGroups[0].GroupId" --output text)
echo "Launching a dry-run instance from $AMI_ID to deploy $BRANCH ($GIT_SHA)"

INSTANCE_ID=$(aws ec2 run-instances \
    --image-id "$AMI_ID" \
    --instance-type t4g.small \
    --key-name transitmatters-gobble \
    --security-group-ids "$SG_ID" \
    --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=32,VolumeType=gp3}" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=gobble-dryrun},{Key=service,Value=gobble-dryrun}]" \
    --query "Instances[0].InstanceId" --output text)
TERMINATE="aws ec2 terminate-instances --profile $AWS_PROFILE --region $AWS_REGION --instance-ids $INSTANCE_ID"
echo "Launched $INSTANCE_ID. When you're done, terminate it with:"
echo "  $TERMINATE"

aws ec2 wait instance-status-ok --instance-ids "$INSTANCE_ID"
INSTANCE_HOSTNAME=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --query "Reservations[*].Instances[*].PublicDnsName" --output text)

export ANSIBLE_HOST_KEY_CHECKING=False
ansible-galaxy collection install datadog.dd
time ansible-playbook -v -i "$INSTANCE_HOSTNAME", -u ubuntu --private-key ~/.ssh/transitmatters-gobble.pem \
    -e dd_env=dryrun -e gobble_branch="$BRANCH" playbook.yml

echo
echo "Provisioned. Check it with:"
echo "  ssh -i ~/.ssh/transitmatters-gobble.pem ubuntu@$INSTANCE_HOSTNAME 'systemctl status gobble --no-pager; crontab -l; ls gobble/data'"
echo "Then terminate it:"
echo "  $TERMINATE"
