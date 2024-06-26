# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List

import constructs
from aws_cdk import Aws, Stack, Tags
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sagemaker as sagemaker
from config.config_mux import StageYamlDataClassConfig
from config.constants import (
    DEV_ACCOUNT_ID,
    ECR_REPO_ARN,
    MODEL_BUCKET_ARN,
    MODEL_PACKAGE_GROUP_NAME,
    PROJECT_ID,
    PROJECT_NAME,
)
from yamldataclassconfig import create_file_path_field

from .get_approved_package import get_approved_package


@dataclass
class EndpointConfigProductionVariant(StageYamlDataClassConfig):  # type:ignore[misc]
    """
    Endpoint Config Production Variant Dataclass
    a dataclass to handle mapping yml file configs to python class for endpoint configs
    """

    initial_instance_count: float = 1
    initial_variant_weight: float = 1
    instance_type: str = "ml.m5.2xlarge"
    variant_name: str = "AllTraffic"

    FILE_PATH: Path = create_file_path_field("endpoint-config.yml", path_is_absolute=True)

    def get_endpoint_config_production_variant(
        self, model_name: str
    ) -> sagemaker.CfnEndpointConfig.ProductionVariantProperty:
        """
        Function to handle creation of cdk glue job. It use the class fields for the job parameters.

        Parameters:
            model_name: name of the sagemaker model resource the sagemaker endpoint would use

        Returns:
            CfnEndpointConfig: CDK SageMaker CFN Endpoint Config resource
        """

        production_variant = sagemaker.CfnEndpointConfig.ProductionVariantProperty(
            initial_instance_count=self.initial_instance_count,
            initial_variant_weight=self.initial_variant_weight,
            instance_type=self.instance_type,
            variant_name=self.variant_name,
            model_name=model_name,
        )

        return production_variant


class DeployEndpointStack(Stack):
    """
    Deploy Endpoint Stack
    Deploy Endpoint stack which provisions SageMaker Model Endpoint resources.
    """

    def __init__(
        self,
        scope: constructs.Construct,
        id: str,
        vpc_id: str,
        subnet_ids: List[str],
        security_group_ids: List[str],
        **kwargs: Any,
    ):
        super().__init__(scope, id, **kwargs)

        Tags.of(self).add("sagemaker:project-id", PROJECT_ID)
        Tags.of(self).add("sagemaker:project-name", PROJECT_NAME)
        Tags.of(self).add("sagemaker:deployment-stage", Stack.of(self).stack_name)

        # iam role that would be used by the model endpoint to run the inference
        model_execution_policy = iam.ManagedPolicy(
            self,
            "ModelExecutionPolicy",
            document=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        actions=[
                            "kms:Encrypt",
                            "kms:ReEncrypt*",
                            "kms:GenerateDataKey*",
                            "kms:Decrypt",
                            "kms:DescribeKey",
                        ],
                        effect=iam.Effect.ALLOW,
                        resources=[f"arn:{Aws.PARTITION}:kms:{Aws.REGION}:{DEV_ACCOUNT_ID}:key/*"],
                    ),
                    iam.PolicyStatement(
                        actions=[
                            "ec2:CreateNetworkInterface",
                            "ec2:CreateNetworkInterfacePermission",
                            "ec2:DeleteNetworkInterface",
                            "ec2:DeleteNetworkInterfacePermission",
                            "ec2:DescribeNetworkInterfaces",
                            "ec2:DescribeVpcs",
                            "ec2:DescribeVpnGateways",
                            "ec2:DescribeDhcpOptions",
                            "ec2:DescribeRouteTables",
                            "ec2:DescribeSubnets",
                            "ec2:DescribeSecurityGroups",
                        ],
                        effect=iam.Effect.ALLOW,
                        resources=["*"],
                    ),
                ]
            ),
        )

        model_bucket = s3.Bucket.from_bucket_arn(self, "ModelBucket", MODEL_BUCKET_ARN)
        model_bucket.grant_read_write(model_execution_policy)

        if ECR_REPO_ARN:
            model_execution_policy.add_statements(
                iam.PolicyStatement(
                    actions=["ecr:Get*"],
                    effect=iam.Effect.ALLOW,
                    resources=[ECR_REPO_ARN],
                )
            )

        model_execution_role = iam.Role(
            self,
            "ModelExecutionRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            managed_policies=[model_execution_policy],
        )

        # setup timestamp to be used to trigger the custom resource update event to retrieve
        # latest approved model and to be used with model and endpoint config resources' names
        now = datetime.now().replace(tzinfo=timezone.utc)

        timestamp = now.strftime("%Y%m%d%H%M%S")

        # get latest approved model package from the model registry (only from a specific model package group)
        latest_approved_model_package = get_approved_package()

        # Sagemaker Model
        model_name = f"{MODEL_PACKAGE_GROUP_NAME}-{id}-{timestamp}"

        vpc_config = None
        if subnet_ids:
            if not security_group_ids:  # Create a security group if not provided
                vpc = ec2.Vpc.from_lookup(self, "VPC", vpc_id=vpc_id)

                security_group_ids = [ec2.SecurityGroup(self, "Security Group", vpc=vpc).security_group_id]

            vpc_config = sagemaker.CfnModel.VpcConfigProperty(
                subnets=subnet_ids,
                security_group_ids=security_group_ids,
            )

        model = sagemaker.CfnModel(
            self,
            "Model",
            execution_role_arn=model_execution_role.role_arn,
            model_name=model_name,
            containers=[
                sagemaker.CfnModel.ContainerDefinitionProperty(model_package_name=latest_approved_model_package)
            ],
            vpc_config=vpc_config,
        )

        # Sagemaker Endpoint Config
        endpoint_config_name = f"{MODEL_PACKAGE_GROUP_NAME}-{id}-ec-{timestamp}"

        endpoint_config_production_variant = EndpointConfigProductionVariant()

        endpoint_config_production_variant.load_for_stack(self)

        # create kms key to be used by the assets bucket
        kms_key = kms.Key(
            self,
            "endpoint-kms-key",
            description="key used for encryption of data in Amazon SageMaker Endpoint",
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

        endpoint_config = sagemaker.CfnEndpointConfig(
            self,
            "EndpointConfig",
            endpoint_config_name=endpoint_config_name,
            kms_key_id=kms_key.key_id,
            production_variants=[
                endpoint_config_production_variant.get_endpoint_config_production_variant(
                    model.model_name  # type: ignore[arg-type]
                )
            ],
        )

        endpoint_config.add_depends_on(model)

        # Sagemaker Endpoint
        endpoint_name = f"{MODEL_PACKAGE_GROUP_NAME}-{id}-endpoint"

        endpoint = sagemaker.CfnEndpoint(
            self,
            "Endpoint",
            endpoint_config_name=endpoint_config.endpoint_config_name,  # type: ignore[arg-type]
            endpoint_name=endpoint_name,
        )

        endpoint.add_depends_on(endpoint_config)

        self.endpoint = endpoint
