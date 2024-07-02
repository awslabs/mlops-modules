# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Any, List

import aws_cdk
from aws_cdk import Aws
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_codebuild as codebuild
from aws_cdk import aws_codecommit as codecommit
from aws_cdk import aws_codepipeline as codepipeline
from aws_cdk import aws_codepipeline_actions as codepipeline_actions
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_assets as s3_assets
from constructs import Construct


class BuildPipelineConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        project_name: str,
        project_id: str,
        model_package_group_name: str,
        model_bucket: s3.IBucket,
        pipeline_artifact_bucket: s3.IBucket,
        repo_asset: s3_assets.Asset,
        vpc_id: str,
        subnet_ids: List[str],
        security_group_ids: List[str],
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Define resource name
        sagemaker_pipeline_name = f"{project_name}-{project_id}"
        sagemaker_pipeline_description = f"{project_name} Model Build Pipeline"

        # Create source repo from seed bucket/key
        build_app_repository = codecommit.Repository(
            self,
            "Build App Code Repo",
            repository_name=f"{project_name}-{construct_id}",
            code=codecommit.Code.from_asset(
                asset=repo_asset,
                branch="main",
            ),
        )
        aws_cdk.Tags.of(build_app_repository).add("sagemaker:project-id", project_id)
        aws_cdk.Tags.of(build_app_repository).add("sagemaker:project-name", project_name)

        sagemaker_seedcode_bucket = s3.Bucket.from_bucket_name(
            self,
            "SageMaker Seedcode Bucket",
            f"sagemaker-servicecatalog-seedcode-{Aws.REGION}",
        )

        codebuild_role = iam.Role(
            self,
            "CodeBuild Role",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
            path="/service-role/",
        )

        sagemaker_execution_role = iam.Role(
            self,
            "SageMaker Execution Role",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            path="/service-role/",
        )

        # Create a policy statement for SM and ECR pull
        sagemaker_policy = iam.Policy(
            self,
            "SageMaker Policy",
            document=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        actions=[
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                        ],
                        resources=["*"],
                    ),
                    iam.PolicyStatement(
                        actions=[
                            "ecr:BatchCheckLayerAvailability",
                            "ecr:BatchGetImage",
                            "ecr:Describe*",
                            "ecr:GetAuthorizationToken",
                            "ecr:GetDownloadUrlForLayer",
                        ],
                        resources=["*"],
                    ),
                    iam.PolicyStatement(
                        actions=[
                            "kms:Encrypt",
                            "kms:ReEncrypt*",
                            "kms:GenerateDataKey*",
                            "kms:Decrypt",
                            "kms:DescribeKey",
                        ],
                        effect=iam.Effect.ALLOW,
                        resources=[f"arn:{Aws.PARTITION}:kms:{Aws.REGION}:{Aws.ACCOUNT_ID}:key/*"],
                    ),
                ]
            ),
        )

        cloudwatch.Metric.grant_put_metric_data(sagemaker_policy)
        model_bucket.grant_read_write(sagemaker_policy)
        sagemaker_seedcode_bucket.grant_read_write(sagemaker_policy)

        sagemaker_execution_role.grant_pass_role(codebuild_role)
        sagemaker_execution_role.grant_pass_role(sagemaker_execution_role)

        # Attach the policy
        sagemaker_policy.attach_to_role(sagemaker_execution_role)
        sagemaker_policy.attach_to_role(codebuild_role)

        # Grant extra permissions for the SageMaker role
        sagemaker_execution_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sagemaker:CreateModel",
                    "sagemaker:DeleteModel",
                    "sagemaker:DescribeModel",
                    "sagemaker:CreateProcessingJob",
                    "sagemaker:DescribeProcessingJob",
                    "sagemaker:StopProcessingJob",
                    "sagemaker:CreateTrainingJob",
                    "sagemaker:DescribeTrainingJob",
                    "sagemaker:StopTrainingJob",
                    "sagemaker:AddTags",
                    "sagemaker:DeleteTags",
                    "sagemaker:ListTags",
                ],
                resources=[
                    f"arn:{Aws.PARTITION}:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:model/*",
                    f"arn:{Aws.PARTITION}:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:processing-job/*",
                    f"arn:{Aws.PARTITION}:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:training-job/*",
                ],
            )
        )
        sagemaker_execution_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sagemaker:CreateModelPackageGroup",
                    "sagemaker:DeleteModelPackageGroup",
                    "sagemaker:DescribeModelPackageGroup",
                    "sagemaker:CreateModelPackage",
                    "sagemaker:DeleteModelPackage",
                    "sagemaker:UpdateModelPackage",
                    "sagemaker:DescribeModelPackage",
                    "sagemaker:ListModelPackages",
                    "sagemaker:AddTags",
                    "sagemaker:DeleteTags",
                    "sagemaker:ListTags",
                ],
                resources=[
                    f"arn:{Aws.PARTITION}:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:model-package-group/"
                    f"{model_package_group_name}",
                    f"arn:{Aws.PARTITION}:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:model-package/"
                    f"{model_package_group_name}/*",
                ],
            ),
        )

        # Grant extra permissions for the CodeBuild role
        codebuild_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sagemaker:DescribeModelPackage",
                    "sagemaker:ListModelPackages",
                    "sagemaker:UpdateModelPackage",
                    "sagemaker:AddTags",
                    "sagemaker:DeleteTags",
                    "sagemaker:ListTags",
                ],
                resources=[
                    f"arn:{Aws.PARTITION}:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:model-package/"
                    f"{model_package_group_name}/*"
                ],
            )
        )
        codebuild_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sagemaker:CreatePipeline",
                    "sagemaker:UpdatePipeline",
                    "sagemaker:DeletePipeline",
                    "sagemaker:StartPipelineExecution",
                    "sagemaker:StopPipelineExecution",
                    "sagemaker:DescribePipelineExecution",
                    "sagemaker:ListPipelineExecutionSteps",
                    "sagemaker:AddTags",
                    "sagemaker:DeleteTags",
                    "sagemaker:ListTags",
                ],
                resources=[
                    f"arn:{Aws.PARTITION}:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:pipeline/"
                    f"{sagemaker_pipeline_name}",
                    f"arn:{Aws.PARTITION}:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:pipeline/"
                    f"{sagemaker_pipeline_name}/execution/*",
                ],
            ),
        )
        codebuild_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sagemaker:DescribeImageVersion",
                ],
                resources=[
                    f"arn:{Aws.PARTITION}:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:image-version/*",
                ],
            )
        )

        # Create the CodeBuild project
        sm_pipeline_build = codebuild.PipelineProject(
            self,
            "SM Pipeline Build",
            project_name=f"{project_name}-{construct_id}",
            role=codebuild_role,  # figure out what actually this role would need
            build_spec=codebuild.BuildSpec.from_source_filename("buildspec.yml"),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_5_0,
                environment_variables={
                    "VPC_ID": codebuild.BuildEnvironmentVariable(value=vpc_id),
                    "SUBNET_IDS": codebuild.BuildEnvironmentVariable(value=subnet_ids),
                    "SECURITY_GROUP_IDS": codebuild.BuildEnvironmentVariable(value=security_group_ids),
                    "SAGEMAKER_PROJECT_NAME": codebuild.BuildEnvironmentVariable(value=project_name),
                    "SAGEMAKER_PROJECT_ID": codebuild.BuildEnvironmentVariable(value=project_id),
                    "MODEL_PACKAGE_GROUP_NAME": codebuild.BuildEnvironmentVariable(value=model_package_group_name),
                    "AWS_REGION": codebuild.BuildEnvironmentVariable(value=Aws.REGION),
                    "SAGEMAKER_PIPELINE_NAME": codebuild.BuildEnvironmentVariable(
                        value=sagemaker_pipeline_name,
                    ),
                    "SAGEMAKER_PIPELINE_DESCRIPTION": codebuild.BuildEnvironmentVariable(
                        value=sagemaker_pipeline_description,
                    ),
                    "SAGEMAKER_PIPELINE_ROLE_ARN": codebuild.BuildEnvironmentVariable(
                        value=sagemaker_execution_role.role_arn,
                    ),
                    "ARTIFACT_BUCKET": codebuild.BuildEnvironmentVariable(value=model_bucket.bucket_name),
                    "ARTIFACT_BUCKET_KMS_ID": codebuild.BuildEnvironmentVariable(
                        value=model_bucket.encryption_key.key_id  # type: ignore[union-attr]
                    ),
                },
            ),
        )

        source_artifact = codepipeline.Artifact(artifact_name="GitSource")

        build_pipeline = codepipeline.Pipeline(
            self,
            "Pipeline",
            pipeline_name=f"{project_name}-{construct_id}",
            artifact_bucket=pipeline_artifact_bucket,
        )

        # add a source stage
        source_stage = build_pipeline.add_stage(stage_name="Source")
        source_stage.add_action(
            codepipeline_actions.CodeCommitSourceAction(
                action_name="Source",
                output=source_artifact,
                repository=build_app_repository,
                branch="main",
            )
        )

        # add a build stage
        build_stage = build_pipeline.add_stage(stage_name="Build")
        build_stage.add_action(
            codepipeline_actions.CodeBuildAction(
                action_name="SMPipeline",
                input=source_artifact,
                project=sm_pipeline_build,
            )
        )
