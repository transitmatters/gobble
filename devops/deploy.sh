#!/bin/bash
set -e

export AWS_PROFILE=transitmatters
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1
export AWS_PAGER=""


STACK_NAME="gobble"

# Ensure required secrets are set
if [[ -z "$DD_API_KEY" ]]; then
    echo "Must provide DD_API_KEY in environment to deploy" 1>&2
    exit 1
fi

# Identify the version and commit of the current deploy
export GIT_SHA=`git rev-parse HEAD`
echo "Deploying version $GIT_SHA"

echo "Deploying Gobble..."
echo "View stack log here: https://$AWS_REGION.console.aws.amazon.com/cloudformation/home?region=$AWS_REGION"

aws cloudformation deploy --stack-name $STACK_NAME \
    --template-file cloudformation.json \
    --capabilities CAPABILITY_NAMED_IAM \
    --no-fail-on-empty-changeset

# Look up the physical ID of the EC2 instance currently associated with the stack
INSTANCE_PHYSICAL_ID=$(aws cloudformation list-stack-resources --stack-name $STACK_NAME --query "StackResourceSummaries[?LogicalResourceId=='GBLEInstance'].PhysicalResourceId" --output text)

# Run the playbook! :-)
export ANSIBLE_HOST_KEY_CHECKING=False # If it's a new host, ssh known_hosts not having the key fingerprint will cause an error. Silence it
ansible-galaxy collection install datadog.dd
SSH_PROXY_ARGS="-o ProxyCommand='aws ec2-instance-connect open-tunnel --instance-id $INSTANCE_PHYSICAL_ID'"
ansible-playbook -v --ssh-extra-args $SSH_PROXY_ARGS -i $INSTANCE_HOSTNAME, -u ubuntu --private-key ~/.ssh/transitmatters-gobble.pem playbook.yml
