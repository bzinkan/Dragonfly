"""Dragonfly CDK app entry.

Run with:
    cdk bootstrap               # once per account/region
    cdk deploy --all            # deploys all stacks for the current env
    cdk diff                    # preview changes

Environment selection comes from DRAGONFLY_ENV (default: dev).
"""

from __future__ import annotations

import os

import aws_cdk as cdk

from stacks.api_stack import ApiStack
from stacks.auth_stack import AuthStack
from stacks.data_stack import DataStack

# Environment name drives resource naming — so dev/staging/prod can coexist
# in one AWS account during early development.
env_name = os.environ.get("DRAGONFLY_ENV", "dev")
aws_account = os.environ.get("CDK_DEFAULT_ACCOUNT")
aws_region = os.environ.get("CDK_DEFAULT_REGION", "us-east-1")

env = cdk.Environment(account=aws_account, region=aws_region)

app = cdk.App()

data_stack = DataStack(
    app,
    f"Dragonfly-Data-{env_name}",
    env_name=env_name,
    env=env,
    description="DynamoDB table and S3 photo bucket for Dragonfly",
)

auth_stack = AuthStack(
    app,
    f"Dragonfly-Auth-{env_name}",
    env_name=env_name,
    env=env,
    description="Cognito user pool and app client for Dragonfly",
)

api_stack = ApiStack(
    app,
    f"Dragonfly-Api-{env_name}",
    env_name=env_name,
    env=env,
    description="HTTP API Gateway and FastAPI Lambda for Dragonfly",
    table=data_stack.table,
    photo_bucket=data_stack.photo_bucket,
    user_pool=auth_stack.user_pool,
    app_client=auth_stack.app_client,
)

# Phase 1 Weeks 5–7 adds:
# WorkersStack — moderation, inat_submit, rarity_refresh Lambdas

cdk.Tags.of(app).add("Project", "Dragonfly")
cdk.Tags.of(app).add("Environment", env_name)
cdk.Tags.of(app).add("ManagedBy", "CDK")

app.synth()
