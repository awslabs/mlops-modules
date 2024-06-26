#!/usr/bin/env python3

import aws_cdk as cdk
import config.constants as constants
from deploy_app.pipeline_stack import PipelineStack

app = cdk.App()
PipelineStack(
    app,
    f"{constants.PROJECT_NAME}-pipeline",
    env=cdk.Environment(account=constants.DEV_ACCOUNT_ID, region=constants.DEV_REGION),
)

app.synth()
