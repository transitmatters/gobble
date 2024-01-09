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

INSTANCE_HOSTNAME=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='InstanceHostname'].OutputValue" --output text)

# Run the playbook! :-)
export ANSIBLE_HOST_KEY_CHECKING=False # If it's a new host, ssh known_hosts not having the key fingerprint will cause an error. Silence it
ansible-galaxy collection install datadog.dd
ansible-playbook -v -i $INSTANCE_HOSTNAME, -u ubuntu --private-key ~/.ssh/transitmatters-gobble.pem playbook.yml
