# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import aws_cdk.aws_iam as iam
import aws_cdk.aws_kms as kms
import aws_cdk.aws_s3 as s3
import aws_cdk.aws_s3_assets as s3_assets
import aws_cdk.aws_sagemaker as sagemaker
import aws_cdk.aws_servicecatalog as servicecatalog
from aws_cdk import Aws, CfnParameter, CfnTag, RemovalPolicy, Tags
from typing import List
from constructs import Construct

from templates.multi_account_basic.pipeline_constructs.build_pipeline_construct import BuildPipelineConstruct
from templates.multi_account_basic.pipeline_constructs.deploy_pipeline_construct import DeployPipelineConstruct


class Product(servicecatalog.ProductStack):
    DESCRIPTION: str = "Creates a SageMaker pipeline which trains a model on Abalone data."
    TEMPLATE_NAME: str = "Train Model on Abalone Data"

    def __init__(
        self,
        scope: Construct,
        id: str,
        build_app_asset: s3_assets.Asset,
        deploy_app_asset: s3_assets.Asset,
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

        preprod_account_id = CfnParameter(
            self,
            "PreprodAccountId",
            type="String",
            description="Pre-prod account id.",
        ).value_as_string

        preprod_region = CfnParameter(
            self,
            "PreprodRegion",
            type="String",
            description="Pre-prod region.",
        ).value_as_string

        prod_account_id = CfnParameter(
            self,
            "ProdAccountId",
            type="String",
            description="Prod account id.",
        ).value_as_string

        prod_region = CfnParameter(
            self,
            "ProdRegion",
            type="String",
            description="Prod region.",
        ).value_as_string

        pre_prod_vpc_id = CfnParameter(
            self,
            "PreprodVpcId",
            type="AWS::EC2::VPC::Id",
            description="The ID of the VPC to be used.",
            default="",
        )
        if pre_prod_vpc_id:
            preprod_vpc_id = pre_prod_vpc_id.value_as_string
        else:
            preprod_vpc_id = ""

        pre_prod_private_subnet_ids = CfnParameter(
            self,
            "PreprodPrivateSubnetIds",
            type="List<AWS::EC2::Subnet::Id>",
            description="A list of private subnet IDs within the VPC.",
            default=None,
        )

        if pre_prod_private_subnet_ids.value_as_list:
            preprod_private_subnet_ids = [
                Fn.select(i, pre_prod_private_subnet_ids.value_as_list)
                for i in range(len(pre_prod_private_subnet_ids.value_as_list))
            ]
        else:
            preprod_private_subnet_ids = []

        pre_prod_public_subnet_ids = CfnParameter(
            self,
            "PreprodPublicSubnetIds",
            type="List<AWS::EC2::Subnet::Id>",
            description="A list of public subnet IDs within the VPC.",
            default=None,
        )
        if pre_prod_public_subnet_ids.value_as_list:
            preprod_public_subnet_ids = [
                Fn.select(i, pre_prod_public_subnet_ids.value_as_list)
                for i in range(len(pre_prod_public_subnet_ids.value_as_list))
            ]
        else:
            preprod_public_subnet_ids = []

        prod_vpc_id = CfnParameter(
            self,
            "ProdVpcId",
            type="AWS::EC2::VPC::Id",
            description="The ID of the VPC to be used.",
            default="",
        )
        if prod_vpc_id:
            prodvpc_id = prod_vpc_id.value_as_string
        else:
            prodvpc_id = ""

        prod_private_subnet_ids = CfnParameter(
            self,
            "ProdPrivateSubnetIds",
            type="List<AWS::EC2::Subnet::Id>",
            description="A list of private subnet IDs within the VPC.",
            default=None,
        )
        if prod_private_subnet_ids.value_as_list:
            prodprivate_subnet_ids = [
                Fn.select(i, prod_private_subnet_ids.value_as_list)
                for i in range(len(prod_private_subnet_ids.value_as_list))
            ]
        else:
            prodprivate_subnet_ids = []

        prod_public_subnet_ids = CfnParameter(
            self,
            "ProdPublicSubnetIds",
            type="List<AWS::EC2::Subnet::Id>",
            description="A list of public subnet IDs within the VPC.",
            default=None,
        )

        if prod_public_subnet_ids.value_as_list:
            prodpublic_subnet_ids = [
                Fn.select(i, prod_public_subnet_ids.value_as_list)
                for i in range(len(prod_public_subnet_ids.value_as_list))
            ]
        else:
            prodpublic_subnet_ids = []

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
                    )
                ]
            ),
        )

        # allow cross account access to the kms key
        kms_key.add_to_resource_policy(
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
                    iam.AccountPrincipal(preprod_account_id),
                    iam.AccountPrincipal(prod_account_id),
                ],
            )
        )

        s3_artifact = s3.Bucket(
            self,
            "S3 Artifact",
            bucket_name=f"mlops-{sagemaker_project_name}-{sagemaker_project_id}-{Aws.ACCOUNT_ID}",
            encryption_key=kms_key,
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            enforce_ssl=True,  # Blocks insecure requests to the bucket
        )

        # DEV account access to objects in the bucket
        s3_artifact.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AddDevPermissions",
                actions=["s3:*"],
                resources=[
                    s3_artifact.arn_for_objects(key_pattern="*"),
                    s3_artifact.bucket_arn,
                ],
                principals=[
                    iam.AccountRootPrincipal(),
                ],
            )
        )

        # PROD account access to objects in the bucket
        s3_artifact.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AddCrossAccountPermissions",
                actions=["s3:List*", "s3:Get*", "s3:Put*"],
                resources=[
                    s3_artifact.arn_for_objects(key_pattern="*"),
                    s3_artifact.bucket_arn,
                ],
                principals=[
                    iam.AccountPrincipal(preprod_account_id),
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
                        f"arn:{Aws.PARTITION}:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:model-package-group/"
                        f"{model_package_group_name}"
                    ],
                    principals=[
                        iam.AccountPrincipal(preprod_account_id),
                        iam.AccountPrincipal(prod_account_id),
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
                        f"arn:{Aws.PARTITION}:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:model-package/"
                        f"{model_package_group_name}/*"
                    ],
                    principals=[
                        iam.AccountPrincipal(preprod_account_id),
                        iam.AccountPrincipal(prod_account_id),
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
            s3_artifact=s3_artifact,
            pipeline_artifact_bucket=pipeline_artifact_bucket,
            model_package_group_name=model_package_group_name,
            repo_asset=build_app_asset,
        )

        DeployPipelineConstruct(
            self,
            "deploy",
            project_name=sagemaker_project_name,
            project_id=sagemaker_project_id,
            pipeline_artifact_bucket=pipeline_artifact_bucket,
            model_package_group_name=model_package_group_name,
            repo_asset=deploy_app_asset,
            preprod_account=preprod_account_id,
            preprod_region=preprod_region,
            prod_account=prod_account_id,
            prod_region=prod_region,
            deployment_region=Aws.REGION,
            preprod_vpc_id=preprod_vpc_id,
            preprod_private_subnet_ids=preprod_private_subnet_ids,
            preprod_public_subnet_ids=preprod_public_subnet_ids,
            prod_vpc_id=prodvpc_id,
            prod_private_subnet_ids=prodprivate_subnet_ids,
            prod_public_subnet_ids=prodpublic_subnet_ids,
        )
