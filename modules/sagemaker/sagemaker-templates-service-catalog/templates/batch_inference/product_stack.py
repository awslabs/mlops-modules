from typing import Any

import aws_cdk
import aws_cdk.aws_servicecatalog as servicecatalog
from aws_cdk import Aws, Tags
from aws_cdk import aws_kms as kms
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_assets as s3_assets
from constructs import Construct

from templates.batch_inference.pipeline_constructs.build_pipeline_construct import BuildPipelineConstruct


class Product(servicecatalog.ProductStack):
    DESCRIPTION: str = "Creates a SageMaker pipeline for executing batch transforms."
    TEMPLATE_NAME: str = "Invoke Batch Transforms on SageMaker Pipelines"

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        build_app_asset: s3_assets.Asset,
        deploy_app_asset: None,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Define required parmeters
        sagemaker_project_name = aws_cdk.CfnParameter(
            self,
            "SageMakerProjectName",
            type="String",
            description="The name of the SageMaker project.",
            min_length=1,
            max_length=32,
        ).value_as_string

        sagemaker_project_id = aws_cdk.CfnParameter(
            self,
            "SageMakerProjectId",
            type="String",
            min_length=1,
            max_length=16,
            description="Service generated ID of the project.",
        ).value_as_string

        model_package_group_name = aws_cdk.CfnParameter(
            self,
            "Model Package Group Name",
            type="String",
            min_length=1,
            description="Model package group name",
        ).value_as_string

        model_bucket_name = aws_cdk.CfnParameter(
            self,
            "Model Bucket Name",
            type="String",
            min_length=1,
            description="Name of the model S3 bucket.",
        ).value_as_string

        base_job_prefix = aws_cdk.CfnParameter(
            self,
            "Base Job Prefix",
            type="String",
            min_length=1,
            description="Prefix for the base job name.",
            default="transformer-output/",
        ).value_as_string

        Tags.of(self).add("sagemaker:project-id", sagemaker_project_id)
        Tags.of(self).add("sagemaker:project-name", sagemaker_project_name)

        # Get Model bucket
        model_bucket = s3.Bucket.from_bucket_name(self, "Model Bucket", model_bucket_name)

        # create kms key to be used by the assets bucket
        kms_key_artifact = kms.Key(
            self,
            "Artifacts Bucket KMS Key",
            description="key used for encryption of data in Amazon S3",
            enable_key_rotation=True,
        )

        pipeline_artifact_bucket = s3.Bucket(
            self,
            "Pipeline Artifacts Bucket",
            bucket_name=f"mlops-{sagemaker_project_name}-{sagemaker_project_id}-{Aws.ACCOUNT_ID}",
            encryption_key=kms_key_artifact,
            versioned=True,
            enforce_ssl=True,  # Blocks insecure requests to the bucket
            removal_policy=aws_cdk.RemovalPolicy.DESTROY,
        )

        BuildPipelineConstruct(
            self,
            "Build",
            project_name=sagemaker_project_name,
            project_id=sagemaker_project_id,
            pipeline_artifact_bucket=pipeline_artifact_bucket,
            model_bucket=model_bucket,
            repo_asset=build_app_asset,
            model_package_group_name=model_package_group_name,
            base_job_prefix=base_job_prefix,
        )
