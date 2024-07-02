# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Any, List

import aws_cdk.aws_iam as iam
import aws_cdk.aws_kms as kms
import aws_cdk.aws_s3 as s3
import aws_cdk.aws_s3_assets as s3_assets
import aws_cdk.aws_sagemaker as sagemaker
import aws_cdk.aws_servicecatalog as servicecatalog
from aws_cdk import Aws, CfnOutput, CfnParameter, CfnTag, RemovalPolicy, Tags
from constructs import Construct

from templates.xgboost_abalone.pipeline_constructs.build_pipeline_construct import (
    BuildPipelineConstruct,
)


class Product(servicecatalog.ProductStack):
    DESCRIPTION: str = "Creates a SageMaker pipeline which trains a model on Abalone dataset."
    TEMPLATE_NAME: str = "Train a model on Abalone dataset using XGBoost"

    def __init__(
        self,
        scope: Construct,
        id: str,
        build_app_asset: s3_assets.Asset,
        pre_prod_account_id: str,
        prod_account_id: str,
        vpc_id: str,
        subnet_ids: List[str],
        security_group_ids: List[str],
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, id)

        dev_account_id = Aws.ACCOUNT_ID
        pre_prod_account_id = Aws.ACCOUNT_ID if not pre_prod_account_id else pre_prod_account_id
        prod_account_id = Aws.ACCOUNT_ID if not prod_account_id else prod_account_id

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

        pre_prod_account_id = CfnParameter(
            self,
            "PreProdAccountId",
            type="String",
            description="Pre-prod AWS account id.. Required for cross-account model registry permissions.",
            default=pre_prod_account_id,
        ).value_as_string

        prod_account_id = CfnParameter(
            self,
            "ProdAccountId",
            type="String",
            description="Prod AWS account id. Required for cross-account model registry permissions.",
            default=prod_account_id,
        ).value_as_string

        Tags.of(self).add("sagemaker:project-id", sagemaker_project_id)
        Tags.of(self).add("sagemaker:project-name", sagemaker_project_name)

        # create kms key to be used by the assets bucket
        kms_key = kms.Key(
            self,
            "Artifacts Bucket KMS Key",
            description="key used for encryption of data in Amazon S3",
            enable_key_rotation=True,
            policy=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        actions=["kms:*"],
                        effect=iam.Effect.ALLOW,
                        resources=["*"],
                        principals=[iam.AccountRootPrincipal()],
                    ),
                    iam.PolicyStatement(
                        actions=[
                            "kms:Encrypt",
                            "kms:Decrypt",
                            "kms:ReEncrypt*",
                            "kms:GenerateDataKey*",
                            "kms:DescribeKey",
                        ],
                        resources=[
                            "*",
                        ],
                        principals=[
                            iam.AccountPrincipal(pre_prod_account_id),
                            iam.AccountPrincipal(prod_account_id),
                        ],
                    ),
                ]
            ),
        )

        model_bucket = s3.Bucket(
            self,
            "S3 Artifact",
            bucket_name=f"mlops-{sagemaker_project_name}-{sagemaker_project_id}-{Aws.ACCOUNT_ID}",
            encryption_key=kms_key,
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            enforce_ssl=True,  # Blocks insecure requests to the bucket
        )

        # DEV account access to objects in the bucket
        model_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AddDevPermissions",
                actions=["s3:*"],
                resources=[
                    model_bucket.arn_for_objects(key_pattern="*"),
                    model_bucket.bucket_arn,
                ],
                principals=[
                    iam.AccountRootPrincipal(),
                ],
            )
        )

        # PROD account access to objects in the bucket
        model_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AddCrossAccountPermissions",
                actions=["s3:List*", "s3:Get*", "s3:Put*"],
                resources=[
                    model_bucket.arn_for_objects(key_pattern="*"),
                    model_bucket.bucket_arn,
                ],
                principals=[
                    iam.AccountPrincipal(pre_prod_account_id),
                    iam.AccountPrincipal(prod_account_id),
                ],
            )
        )

        model_package_group_name = f"{sagemaker_project_name}-{sagemaker_project_id}"

        # cross account model registry resource policy
        model_package_group_policy = iam.PolicyDocument(
            statements=[
                iam.PolicyStatement(
                    sid="ModelPackageGroup",
                    actions=[
                        "sagemaker:DescribeModelPackageGroup",
                    ],
                    resources=[
                        (
                            f"arn:{Aws.PARTITION}:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:model-package-group/"
                            f"{model_package_group_name}"
                        )
                    ],
                    principals=[
                        iam.ArnPrincipal(f"arn:{Aws.PARTITION}:iam::{dev_account_id}:root"),
                        iam.ArnPrincipal(f"arn:{Aws.PARTITION}:iam::{pre_prod_account_id}:root"),
                        iam.ArnPrincipal(f"arn:{Aws.PARTITION}:iam::{prod_account_id}:root"),
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
                        (
                            f"arn:{Aws.PARTITION}:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:model-package/"
                            f"{model_package_group_name}/*"
                        )
                    ],
                    principals=[
                        iam.ArnPrincipal(f"arn:{Aws.PARTITION}:iam::{dev_account_id}:root"),
                        iam.ArnPrincipal(f"arn:{Aws.PARTITION}:iam::{pre_prod_account_id}:root"),
                        iam.ArnPrincipal(f"arn:{Aws.PARTITION}:iam::{prod_account_id}:root"),
                    ],
                ),
            ]
        ).to_json()

        sagemaker.CfnModelPackageGroup(
            self,
            "Model Package Group",
            model_package_group_name=model_package_group_name,
            model_package_group_description=f"Model Package Group for {sagemaker_project_name}",
            model_package_group_policy=model_package_group_policy,
            tags=[
                CfnTag(key="sagemaker:project-id", value=sagemaker_project_id),
                CfnTag(key="sagemaker:project-name", value=sagemaker_project_name),
            ],
        )

        kms_key = kms.Key(
            self,
            "Pipeline Bucket KMS Key",
            description="key used for encryption of data in Amazon S3",
            enable_key_rotation=True,
            policy=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        actions=["kms:*"],
                        effect=iam.Effect.ALLOW,
                        resources=["*"],
                        principals=[iam.AccountRootPrincipal()],
                    )
                ]
            ),
        )

        pipeline_artifact_bucket = s3.Bucket(
            self,
            "Pipeline Bucket",
            bucket_name=f"pipeline-{sagemaker_project_name}-{sagemaker_project_id}-{Aws.ACCOUNT_ID}",
            encryption_key=kms_key,
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

        BuildPipelineConstruct(
            self,
            "build",
            project_name=sagemaker_project_name,
            project_id=sagemaker_project_id,
            model_package_group_name=model_package_group_name,
            model_bucket=model_bucket,
            pipeline_artifact_bucket=pipeline_artifact_bucket,
            repo_asset=build_app_asset,
        )

        CfnOutput(
            self,
            "Model Bucket Name",
            value=model_bucket.bucket_name,
        )

        CfnOutput(
            self,
            "Model Package Group Name",
            value=model_package_group_name,
        )
