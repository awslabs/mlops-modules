from typing import Any

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
        pipeline_artifact_bucket: s3.IBucket,
        repo_asset: s3_assets.Asset,
        model_package_group_name: str,
        model_bucket: s3.IBucket,
        base_job_prefix: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

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

        sagemaker_seedcode_bucket = s3.Bucket.from_bucket_name(
            self, "SageMaker Seedcode Bucket", f"sagemaker-servicecatalog-seedcode-{Aws.REGION}"
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

        # Create a policy statement for both the SageMaker and CodeBuild roles
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
        sagemaker_execution_role.grant_pass_role(sagemaker_policy)  # type: ignore[arg-type]

        # Attach the policy
        sagemaker_policy.attach_to_role(sagemaker_execution_role)
        sagemaker_policy.attach_to_role(codebuild_role)

        # Grant extra permissions for the SageMaker role
        sagemaker_seedcode_bucket.grant_read(sagemaker_execution_role)

        sagemaker_execution_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sagemaker:CreateModel",
                    "sagemaker:DeleteModel",
                    "sagemaker:DescribeModel",
                    "sagemaker:CreateProcessingJob",
                    "sagemaker:DescribeProcessingJob",
                    "sagemaker:StopProcessingJob",
                    "sagemaker:CreateTransformJob",
                    "sagemaker:DescribeTransformJob",
                    "sagemaker:StopTransformJob",
                    "sagemaker:AddTags",
                    "sagemaker:DeleteTags",
                ],
                resources=[
                    f"arn:{Aws.PARTITION}:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:model/*",
                    f"arn:{Aws.PARTITION}:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:processing-job/*",
                    f"arn:{Aws.PARTITION}:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:transform-job/*",
                ],
            ),
        )

        # Grant extra permissions for the CodeBuild role
        codebuild_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sagemaker:ListModelPackages",
                    "sagemaker:DescribeModelPackage",
                ],
                resources=[
                    f"arn:{Aws.PARTITION}:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:model-package/{model_package_group_name}/*"
                ],
            ),
        )
        codebuild_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sagemaker:CreatePipeline",
                    "sagemaker:UpdatePipeline",
                    "sagemaker:DeletePipeline",
                    "sagemaker:AddTags",
                    "sagemaker:DeleteTags",
                    "sagemaker:ListTags",
                ],
                resources=[f"arn:{Aws.PARTITION}:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:pipeline/{project_name}"],
            ),
        )

        # Create the CodeBuild project
        sm_pipeline_build = codebuild.PipelineProject(
            self,
            "SageMaker Pipeline Build",
            project_name=f"{project_name}-{construct_id}",
            role=codebuild_role,
            build_spec=codebuild.BuildSpec.from_source_filename("buildspec.yml"),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_5_0,
                environment_variables={
                    "SAGEMAKER_PROJECT_NAME": codebuild.BuildEnvironmentVariable(value=project_name),
                    "SAGEMAKER_PROJECT_ID": codebuild.BuildEnvironmentVariable(value=project_id),
                    "MODEL_PACKAGE_GROUP_NAME": codebuild.BuildEnvironmentVariable(value=model_package_group_name),
                    "AWS_REGION": codebuild.BuildEnvironmentVariable(value=Aws.REGION),
                    "SAGEMAKER_PIPELINE_ROLE_ARN": codebuild.BuildEnvironmentVariable(
                        value=sagemaker_execution_role.role_arn,
                    ),
                    "ARTIFACT_BUCKET": codebuild.BuildEnvironmentVariable(value=model_bucket.bucket_name),
                    "BASE_JOB_PREFIX": codebuild.BuildEnvironmentVariable(value=base_job_prefix),
                },
            ),
        )

        source_artifact = codepipeline.Artifact(artifact_name="GitSource")

        build_pipeline = codepipeline.Pipeline(
            self,
            "CodePipeline",
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
