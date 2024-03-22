import logging
from typing import TYPE_CHECKING

import boto3
import sagemaker
import sagemaker.session
from sagemaker import ModelPackage
from sagemaker.inputs import TransformInput
from sagemaker.processing import ProcessingOutput
from sagemaker.sklearn.processing import SKLearnProcessor
from sagemaker.transformer import Transformer
from sagemaker.workflow.execution_variables import ExecutionVariables
from sagemaker.workflow.functions import Join
from sagemaker.workflow.model_step import ModelStep
from sagemaker.workflow.parameters import ParameterInteger, ParameterString
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.pipeline_context import PipelineSession
from sagemaker.workflow.retry import (
    SageMakerJobExceptionTypeEnum,
    SageMakerJobStepRetryPolicy,
    StepExceptionTypeEnum,
    StepRetryPolicy,
)
from sagemaker.workflow.steps import ProcessingStep, TransformStep

if TYPE_CHECKING:
    from mypy_boto3_sagemaker.client import SageMakerClient

logger = logging.getLogger(__name__)


def get_sagemaker_client(region_name: str) -> "SageMakerClient":
    boto_session = boto3.Session(region_name=region_name)
    return boto_session.client("sagemaker")


def get_session(region_name: str, bucket_name: str) -> sagemaker.session.Session:
    boto_session = boto3.Session(region_name=region_name)

    sagemaker_client = boto_session.client("sagemaker")
    runtime_client = boto_session.client("sagemaker-runtime")

    return sagemaker.session.Session(
        boto_session=boto_session,
        sagemaker_client=sagemaker_client,
        sagemaker_runtime_client=runtime_client,
        default_bucket=bucket_name,
    )


def get_pipeline_session(region_name: str, default_bucket_name: str) -> PipelineSession:
    boto_session = boto3.Session(region_name=region_name)
    sagemaker_client = boto_session.client("sagemaker")

    return PipelineSession(
        boto_session=boto_session,
        sagemaker_client=sagemaker_client,
        default_bucket=default_bucket_name,
    )


def get_pipeline(
    region: str,
    role_arn: str,
    artifact_bucket: str,
    pipeline_name: str,
    base_job_prefix: str,
    model_package_arn: str,
) -> Pipeline:
    pipeline_session = get_pipeline_session(region, artifact_bucket)

    ############################################
    # Pipeline Parameters for pipeline execution
    ############################################
    processing_instance_type = ParameterString(name="ProcessingInstanceType", default_value="ml.m5.large")
    processing_instance_count = ParameterInteger(name="ProcessingInstanceCount", default_value=1)
    transform_instance_type = ParameterString(name="TransformInstanceType", default_value="ml.m5.large")
    transform_instance_count = ParameterInteger(name="TransformInstanceCount", default_value=1)

    input_data = ParameterString(
        name="InputDataUrl",
        default_value=f"s3://sagemaker-servicecatalog-seedcode-{region}/dataset/abalone-dataset.csv",
    )

    outputs_bucket = ParameterString(name="OutputsBucketName", default_value=artifact_bucket)

    # Retry policies
    # https://docs.aws.amazon.com/sagemaker/latest/dg/pipelines-retry-policy.html
    retry_policies = [
        # override the default
        StepRetryPolicy(
            exception_types=[StepExceptionTypeEnum.SERVICE_FAULT, StepExceptionTypeEnum.THROTTLING],
            max_attempts=3,
            interval_seconds=10,
            backoff_rate=2.0,
        ),
        # retry when resource limit quota gets exceeded
        SageMakerJobStepRetryPolicy(
            exception_types=[SageMakerJobExceptionTypeEnum.RESOURCE_LIMIT],
            max_attempts=3,
            interval_seconds=60,
            backoff_rate=2.0,
        ),
        # retry when job failed due to transient error or EC2 ICE.
        SageMakerJobStepRetryPolicy(
            failure_reason_types=[
                SageMakerJobExceptionTypeEnum.INTERNAL_ERROR,
                SageMakerJobExceptionTypeEnum.CAPACITY_ERROR,
            ],
            max_attempts=3,
            interval_seconds=30,
            backoff_rate=2.0,
        ),
    ]

    ############################################
    # Pipeline Steps definition
    ############################################

    # Create a model from latest model package in SM Model Registry
    model_package = ModelPackage(
        role=role_arn,
        model_package_arn=model_package_arn,
        sagemaker_session=pipeline_session,
    )

    step_create_model = ModelStep(
        name="CreateModel",
        step_args=model_package.create(instance_type=transform_instance_type),
    )

    # Processing step for feature engineering
    sklearn_processor = SKLearnProcessor(
        framework_version="0.20.0",
        instance_type=processing_instance_type,
        instance_count=processing_instance_count,
        base_job_name=f"{base_job_prefix}/sklearn-abalone-preprocess",
        sagemaker_session=pipeline_session,
        role=role_arn,
    )
    step_process = ProcessingStep(
        name="PreprocessData",
        processor=sklearn_processor,
        outputs=[
            ProcessingOutput(output_name="output_data", source="/opt/ml/processing/output_data"),
        ],
        code="source_scripts/preprocessing/prepare_abalone_data/main.py",
        job_arguments=[
            "--input-data",
            input_data,
            "--do-train-test-split",
            "False",
        ],
    )

    # Define qgen transformer and TransformStep
    output_transform = Join(
        on="/", values=["s3:/", outputs_bucket, base_job_prefix, ExecutionVariables.PIPELINE_EXECUTION_ID, "batch/"]
    )

    transformer = Transformer(
        model_name=step_create_model.properties.ModelName,
        instance_count=transform_instance_count,
        instance_type=transform_instance_type,
        max_concurrent_transforms=64,
        max_payload=1,
        strategy="SingleRecord",
        assemble_with="Line",
        output_path=output_transform,
    )

    input_path_transform_step = step_process.properties.ProcessingOutputConfig.Outputs["output_data"].S3Output.S3Uri

    step_transformer = TransformStep(
        name="Transformer",
        transformer=transformer,
        inputs=TransformInput(data=input_path_transform_step, content_type="text/csv", split_type="Line"),
        retry_policies=retry_policies,
        # cache_config=cache_config
    )

    ############################################
    # Pipeline Definition
    ############################################
    pipeline = Pipeline(
        sagemaker_session=pipeline_session,
        name=pipeline_name,
        parameters=[
            input_data,
            outputs_bucket,
            transform_instance_count,
            transform_instance_type,
            processing_instance_count,
            processing_instance_type,
        ],
        steps=[
            step_create_model,
            step_process,
            step_transformer,
        ],
    )
    return pipeline
