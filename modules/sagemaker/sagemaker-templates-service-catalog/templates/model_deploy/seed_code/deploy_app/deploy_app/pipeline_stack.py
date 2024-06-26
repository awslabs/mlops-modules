import json
from typing import Any

import aws_cdk as cdk
import config.constants as constants
from aws_cdk import aws_codecommit as codecommit
from aws_cdk import aws_iam as iam
from aws_cdk.pipelines import CodeBuildStep, CodePipeline, CodePipelineSource
from constructs import Construct

from .deploy_endpoint_stack import DeployEndpointStack

ENV = {
    "MODEL_PACKAGE_GROUP_NAME": constants.MODEL_PACKAGE_GROUP_NAME,
    "MODEL_BUCKET_ARN": constants.MODEL_BUCKET_ARN,
    "PROJECT_ID": constants.PROJECT_ID,
    "PROJECT_NAME": constants.PROJECT_NAME,
    "DEV_ACCOUNT_ID": constants.DEV_ACCOUNT_ID,
    "DEV_REGION": constants.DEV_REGION,
    "DEV_VPC_ID": constants.DEV_VPC_ID,
    "DEV_SUBNET_IDS": json.dumps(constants.DEV_SUBNET_IDS),
    "DEV_SECURITY_GROUP_IDS": json.dumps(constants.DEV_SECURITY_GROUP_IDS),
    "PRE_PROD_ACCOUNT_ID": constants.PRE_PROD_ACCOUNT_ID,
    "PRE_PROD_REGION": constants.PRE_PROD_REGION,
    "PRE_PROD_VPC_ID": constants.PRE_PROD_VPC_ID,
    "PRE_PROD_SUBNET_IDS": json.dumps(constants.PRE_PROD_SUBNET_IDS),
    "PRE_PROD_SECURITY_GROUP_IDS": json.dumps(constants.PRE_PROD_SECURITY_GROUP_IDS),
    "PROD_ACCOUNT_ID": constants.PROD_ACCOUNT_ID,
    "PROD_REGION": constants.PROD_REGION,
    "PROD_VPC_ID": constants.PROD_VPC_ID,
    "PROD_SUBNET_IDS": json.dumps(constants.PROD_SUBNET_IDS),
    "PROD_SECURITY_GROUP_IDS": json.dumps(constants.PROD_SECURITY_GROUP_IDS),
}


class DevStage(cdk.Stage):
    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)

        DeployEndpointStack(
            self,
            "endpoint",
            vpc_id=constants.DEV_VPC_ID,
            subnet_ids=constants.DEV_SUBNET_IDS,
            security_group_ids=constants.DEV_SECURITY_GROUP_IDS,
        )


class PreProdStage(cdk.Stage):
    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)

        DeployEndpointStack(
            self,
            "endpoint",
            vpc_id=constants.PRE_PROD_VPC_ID,
            subnet_ids=constants.PRE_PROD_SUBNET_IDS,
            security_group_ids=constants.PRE_PROD_SECURITY_GROUP_IDS,
        )


class ProdStage(cdk.Stage):
    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)

        DeployEndpointStack(
            self,
            "endpoint",
            vpc_id=constants.PROD_VPC_ID,
            subnet_ids=constants.PROD_SUBNET_IDS,
            security_group_ids=constants.PROD_SECURITY_GROUP_IDS,
        )


def create_inline_policy(scope: Construct, identifier: str) -> iam.Policy:
    return iam.Policy(
        scope,
        identifier,
        statements=[
            iam.PolicyStatement(
                sid="ModelPackageGroup",
                actions=[
                    "sagemaker:DescribeModelPackageGroup",
                ],
                resources=[
                    f"arn:{cdk.Aws.PARTITION}:sagemaker:{constants.DEV_REGION}:{constants.DEV_ACCOUNT_ID}:model-package-group/{constants.MODEL_PACKAGE_GROUP_NAME}",
                    f"arn:{cdk.Aws.PARTITION}:sagemaker:{constants.PRE_PROD_REGION}:{constants.PRE_PROD_ACCOUNT_ID}:model-package-group/{constants.MODEL_PACKAGE_GROUP_NAME}",
                    f"arn:{cdk.Aws.PARTITION}:sagemaker:{constants.PROD_REGION}:{constants.PROD_ACCOUNT_ID}:model-package-group/{constants.MODEL_PACKAGE_GROUP_NAME}",
                ],
            ),
            iam.PolicyStatement(
                sid="ModelPackage",
                actions=[
                    "sagemaker:DescribeModelPackage",
                    "sagemaker:ListModelPackages",
                    "sagemaker:UpdateModelPackage",
                    "sagemaker:CreateModel",
                ],
                resources=[
                    f"arn:{cdk.Aws.PARTITION}:sagemaker:{constants.DEV_REGION}:{constants.DEV_ACCOUNT_ID}:model-package-group/{constants.MODEL_PACKAGE_GROUP_NAME}",
                    f"arn:{cdk.Aws.PARTITION}:sagemaker:{constants.PRE_PROD_REGION}:{constants.PRE_PROD_ACCOUNT_ID}:model-package-group/{constants.MODEL_PACKAGE_GROUP_NAME}",
                    f"arn:{cdk.Aws.PARTITION}:sagemaker:{constants.PROD_REGION}:{constants.PROD_ACCOUNT_ID}:model-package-group/{constants.MODEL_PACKAGE_GROUP_NAME}",
                ],
            ),
            iam.PolicyStatement(
                actions=[
                    "sts:AssumeRole",
                ],
                effect=iam.Effect.ALLOW,
                resources=[
                    # TODO: this is clearly over-permissive
                    f"arn:{cdk.Aws.PARTITION}:iam::{constants.DEV_ACCOUNT_ID}:role/*",
                    f"arn:{cdk.Aws.PARTITION}:iam::{constants.PRE_PROD_ACCOUNT_ID}:role/cdk*",
                    f"arn:{cdk.Aws.PARTITION}:iam::{constants.PROD_ACCOUNT_ID}:role/cdk*",
                ],
            ),
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[
                    f"arn:{cdk.Aws.PARTITION}:ssm:{constants.DEV_REGION}:{constants.DEV_ACCOUNT_ID}:parameter/*",
                    f"arn:{cdk.Aws.PARTITION}:ssm:{constants.PRE_PROD_REGION}:{constants.PRE_PROD_ACCOUNT_ID}:parameter/*",
                    f"arn:{cdk.Aws.PARTITION}:ssm:{constants.PROD_REGION}:{constants.PROD_ACCOUNT_ID}:parameter/*",
                ],
            ),
        ],
    )


class PipelineStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)

        repository = codecommit.Repository.from_repository_name(
            self, "Repository", repository_name=f"{constants.PROJECT_NAME}-deploy"
        )

        codepipeline_role = iam.Role(
            self,
            "CodePipelineRole",
            assumed_by=iam.ServicePrincipal("codepipeline.amazonaws.com"),
            path="/service-role/",
        )

        codepipeline_role.attach_inline_policy(create_inline_policy(self, "DeployPipelinePolicy"))

        synth_codebuild_role = iam.Role(
            self,
            "SynthStageRole",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
            path="/service-role/",
        )
        synth_codebuild_role.attach_inline_policy(create_inline_policy(self, "SynthStagePolicy"))

        pipeline = CodePipeline(
            self,
            "Pipeline",
            pipeline_name=f"{constants.PROJECT_NAME}-pipeline",
            synth=CodeBuildStep(
                "Synth",
                input=CodePipelineSource.code_commit(repository=repository, branch="main"),
                install_commands=[
                    "npm install -g aws-cdk",
                ],
                commands=["python -m pip install -r requirements.txt", 'cdk synth --app "python app.py" '],
                role=synth_codebuild_role,
                env=ENV,
            ),
            cross_account_keys=True,
            self_mutation=True,
            role=codepipeline_role,
        )

        pipeline.add_stage(
            DevStage(
                self,
                "dev",
                env=cdk.Environment(account=constants.DEV_ACCOUNT_ID, region=constants.DEV_REGION),
            )
        )

        pipeline.add_stage(
            PreProdStage(
                self,
                "preprod",
                env=cdk.Environment(account=constants.PRE_PROD_ACCOUNT_ID, region=constants.PRE_PROD_REGION),
            )
        )

        pipeline.add_stage(
            ProdStage(
                self,
                "prod",
                env=cdk.Environment(account=constants.PROD_ACCOUNT_ID, region=constants.PROD_REGION),
            )
        )
