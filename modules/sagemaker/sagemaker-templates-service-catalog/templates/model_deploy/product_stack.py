# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import json
from typing import Any, List

import aws_cdk.aws_s3_assets as s3_assets
import aws_cdk.aws_servicecatalog as servicecatalog
from aws_cdk import Aws, CfnParameter, Tags
from aws_cdk import aws_codebuild as codebuild
from aws_cdk import aws_codecommit as codecommit
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from constructs import Construct


class Product(servicecatalog.ProductStack):
    DESCRIPTION: str = (
        "Creates a self-mutating CodePipeline that deploys a model endpoint to dev, pre-prod, and prod environments."
    )
    TEMPLATE_NAME: str = "Deployment pipeline that deploys model endpoints to dev, pre-prod, and prod"

    def __init__(
        self,
        scope: Construct,
        id: str,
        deploy_app_asset: s3_assets.Asset,
        dev_vpc_id: str,
        dev_subnet_ids: List[str],
        dev_security_group_ids: List[str],
        pre_prod_account_id: str,
        pre_prod_region: str,
        pre_prod_vpc_id: str,
        pre_prod_subnet_ids: List[str],
        pre_prod_security_group_ids: List[str],
        prod_account_id: str,
        prod_region: str,
        prod_vpc_id: str,
        prod_subnet_ids: List[str],
        prod_security_group_ids: List[str],
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, id)

        sagemaker_project_name = CfnParameter(
            self,
            "SageMakerProjectName",
            type="String",
            description="Name of the project.",
        ).value_as_string

        sagemaker_project_id = CfnParameter(
            self,
            "SageMakerProjectId",
            type="String",
            description="Service generated Id of the project.",
        ).value_as_string

        model_package_group_name = CfnParameter(
            self,
            "ModelPackageGroupName",
            type="String",
            description="Name of the model package group.",
        ).value_as_string

        model_bucket_name = CfnParameter(
            self,
            "ModelBucketName",
            type="String",
            description="Name of the bucket that stores model artifacts.",
        ).value_as_string

        pre_prod_account_id = CfnParameter(
            self,
            "PreProdAccountId",
            type="String",
            description="Pre-prod AWS account id.",
            default=pre_prod_account_id,
        ).value_as_string

        pre_prod_region = CfnParameter(
            self,
            "PreProdRegion",
            type="String",
            description="Pre-prod region name.",
            default=pre_prod_region,
        ).value_as_string

        prod_account_id = CfnParameter(
            self,
            "ProdAccountId",
            type="String",
            description="Prod AWS account id.",
            default=prod_account_id,
        ).value_as_string

        prod_region = CfnParameter(
            self,
            "ProdRegion",
            type="String",
            description="Prod region name.",
            default=prod_region,
        ).value_as_string

        Tags.of(self).add("sagemaker:project-id", sagemaker_project_id)
        Tags.of(self).add("sagemaker:project-name", sagemaker_project_name)

        dev_account_id: str = Aws.ACCOUNT_ID
        dev_region: str = Aws.REGION

        model_package_arn = (
            f"arn:{Aws.PARTITION}:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:model-package/"
            f"{model_package_group_name}/*"
        )
        model_package_group_arn = (
            f"arn:{Aws.PARTITION}:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:model-package-group/"
            f"{model_package_group_name}"
        )

        # Create source repo from seed bucket/key
        repository = codecommit.Repository(
            self,
            "Deploy App Code Repo",
            repository_name=f"{sagemaker_project_name}-deploy",
            code=codecommit.Code.from_asset(
                asset=deploy_app_asset,
                branch="main",
            ),
        )

        # Import model bucket
        model_bucket = s3.Bucket.from_bucket_name(self, "ModelBucket", bucket_name=model_bucket_name)

        code_pipeline_deploy_project_name = "CodePipelineDeployProject"

        project = codebuild.Project(
            self,
            code_pipeline_deploy_project_name,
            build_spec=codebuild.BuildSpec.from_object(
                {
                    "version": "0.2",
                    "phases": {
                        "build": {
                            "commands": [
                                "npm install -g aws-cdk",
                                "python -m pip install -r requirements.txt",
                                'cdk deploy --require-approval never --app "python app.py" ',
                            ]
                        }
                    },
                }
            ),
            source=codebuild.Source.code_commit(repository=repository),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_5_0,
                environment_variables={
                    "MODEL_PACKAGE_GROUP_NAME": codebuild.BuildEnvironmentVariable(value=model_package_group_name),
                    "MODEL_BUCKET_ARN": codebuild.BuildEnvironmentVariable(value=model_bucket.bucket_arn),
                    "PROJECT_ID": codebuild.BuildEnvironmentVariable(value=sagemaker_project_id),
                    "PROJECT_NAME": codebuild.BuildEnvironmentVariable(value=sagemaker_project_name),
                    "DEV_VPC_ID": codebuild.BuildEnvironmentVariable(value=dev_vpc_id),
                    "DEV_ACCOUNT_ID": codebuild.BuildEnvironmentVariable(value=dev_account_id),
                    "DEV_REGION": codebuild.BuildEnvironmentVariable(value=dev_region),
                    "DEV_SUBNET_IDS": codebuild.BuildEnvironmentVariable(value=json.dumps(dev_subnet_ids)),
                    "DEV_SECURITY_GROUP_IDS": codebuild.BuildEnvironmentVariable(
                        value=json.dumps(dev_security_group_ids)
                    ),
                    "PRE_PROD_VPC_ID": codebuild.BuildEnvironmentVariable(value=pre_prod_vpc_id),
                    "PRE_PROD_ACCOUNT_ID": codebuild.BuildEnvironmentVariable(value=pre_prod_account_id),
                    "PRE_PROD_REGION": codebuild.BuildEnvironmentVariable(value=pre_prod_region),
                    "PRE_PROD_SUBNET_IDS": codebuild.BuildEnvironmentVariable(value=json.dumps(pre_prod_subnet_ids)),
                    "PRE_PROD_SECURITY_GROUP_IDS": codebuild.BuildEnvironmentVariable(
                        value=json.dumps(pre_prod_security_group_ids)
                    ),
                    "PROD_VPC_ID": codebuild.BuildEnvironmentVariable(value=prod_vpc_id),
                    "PROD_ACCOUNT_ID": codebuild.BuildEnvironmentVariable(value=prod_account_id),
                    "PROD_REGION": codebuild.BuildEnvironmentVariable(value=prod_region),
                    "PROD_SUBNET_IDS": codebuild.BuildEnvironmentVariable(value=json.dumps(prod_subnet_ids)),
                    "PROD_SECURITY_GROUP_IDS": codebuild.BuildEnvironmentVariable(
                        value=json.dumps(prod_security_group_ids)
                    ),
                },
            ),
        )
        # Verify that the project.role is not None
        if project.role is None:
            raise ValueError("project.role is None, unable to attach inline policy")
        else:
            project.role.attach_inline_policy(
                iam.Policy(
                    self,
                    "Policy",
                    statements=[
                        iam.PolicyStatement(
                            sid="ModelPackageGroup",
                            actions=[
                                "sagemaker:DescribeModelPackageGroup",
                            ],
                            resources=[model_package_group_arn],
                        ),
                        iam.PolicyStatement(
                            sid="ModelPackage",
                            actions=[
                                "sagemaker:DescribeModelPackage",
                                "sagemaker:ListModelPackages",
                                "sagemaker:UpdateModelPackage",
                                "sagemaker:CreateModel",
                            ],
                            resources=[model_package_arn],
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "sts:AssumeRole",
                            ],
                            effect=iam.Effect.ALLOW,
                            resources=[
                                f"arn:{Aws.PARTITION}:iam::{dev_account_id}:role/cdk*",
                                f"arn:{Aws.PARTITION}:iam::{pre_prod_account_id}:role/cdk*",
                                f"arn:{Aws.PARTITION}:iam::{prod_account_id}:role/cdk*",
                            ],
                        ),
                        iam.PolicyStatement(
                            actions=["ssm:GetParameter"],
                            resources=[
                                f"arn:{Aws.PARTITION}:ssm:{dev_region}:{dev_account_id}:parameter/*",
                                f"arn:{Aws.PARTITION}:ssm:{pre_prod_region}:{pre_prod_account_id}:parameter/*",
                                f"arn:{Aws.PARTITION}:ssm:{prod_region}:{prod_account_id}:parameter/*",
                            ],
                        ),
                    ],
                )
            )
