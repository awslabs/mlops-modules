# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Any, List
import aws_cdk
from aws_cdk import Aws, CfnCapabilities
from aws_cdk import aws_codebuild as codebuild
from aws_cdk import aws_codecommit as codecommit
from aws_cdk import aws_codepipeline as codepipeline
from aws_cdk import aws_codepipeline_actions as codepipeline_actions
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_assets as s3_assets
from constructs import Construct


class DeployPipelineConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        project_name: str,
        project_id: str,
        pipeline_artifact_bucket: s3.IBucket,
        model_package_group_name: str,
        repo_asset: s3_assets.Asset,
        preprod_account: str,
        preprod_region: str,
        prod_account: str,
        prod_region: str,
        deployment_region: str,
        preprod_vpc_id: str = None,
        preprod_private_subnet_ids: List[str]= None,
        preprod_public_subnet_ids: List[str] = None,
        prod_vpc_id: str = None,
        prod_private_subnet_ids: List[str ] = None,
        prod_public_subnet_ids: List[str ] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Define resource names
        pipeline_name = f"{project_name}-{construct_id}"

        # Create source repo from seed bucket/key
        deploy_app_repository = codecommit.Repository(
            self,
            "DeployAppCodeRepo",
            repository_name=f"{project_name}-{construct_id}",
            code=codecommit.Code.from_asset(
                asset=repo_asset,
                branch="main",
            ),
        )
        aws_cdk.Tags.of(deploy_app_repository).add("sagemaker:project-id", project_id)
        aws_cdk.Tags.of(deploy_app_repository).add("sagemaker:project-name", project_name)

        cdk_synth_build_role = iam.Role(
            self,
            "CodeBuildRole",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
            path="/service-role/",
        )

        cdk_synth_build_role.add_to_policy(
            iam.PolicyStatement(
                actions=["sagemaker:ListModelPackages"],
                resources=[
                    f"arn:{Aws.PARTITION}:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:model-package-group/"
                    f"{project_name}-{project_id}*",
                    f"arn:{Aws.PARTITION}:sagemaker:{Aws.REGION}:{Aws.ACCOUNT_ID}:model-package/"
                    f"{project_name}-{project_id}/*",
                ],
            )
        )

        cdk_synth_build_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[
                    f"arn:{Aws.PARTITION}:ssm:{Aws.REGION}:{Aws.ACCOUNT_ID}:parameter/*",
                ],
            )
        )

        cdk_synth_build_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "kms:Encrypt",
                    "kms:ReEncrypt*",
                    "kms:GenerateDataKey*",
                    "kms:Decrypt",
                    "kms:DescribeKey",
                ],
                effect=iam.Effect.ALLOW,
                resources=[f"arn:aws:kms:{Aws.REGION}:{Aws.ACCOUNT_ID}:key/*"],
            ),
        )

        cdk_synth_build = codebuild.PipelineProject(
            self,
            "CDKSynthBuild",
            role=cdk_synth_build_role,
            build_spec=codebuild.BuildSpec.from_object(
                {
                    "version": "0.2",
                    "phases": {
                        "build": {
                            "commands": [
                                "npm install -g aws-cdk",
                                "pip install -r requirements.txt",
                                'cdk synth --no-lookups --app "python app.py"',
                            ]
                        }
                    },
                    "artifacts": {"base-directory": "cdk.out", "files": "**/*"},
                }
            ),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_5_0,
                environment_variables={
                    "MODEL_PACKAGE_GROUP_NAME": codebuild.BuildEnvironmentVariable(value=model_package_group_name),
                    "PROJECT_ID": codebuild.BuildEnvironmentVariable(value=project_id),
                    "PROJECT_NAME": codebuild.BuildEnvironmentVariable(value=project_name),
                    "DEPLOYMENT_ACCOUNT": codebuild.BuildEnvironmentVariable(value=Aws.ACCOUNT_ID),
                    "DEPLOYMENT_REGION": codebuild.BuildEnvironmentVariable(value=deployment_region),
                    "PREPROD_ACCOUNT": codebuild.BuildEnvironmentVariable(value=preprod_account),
                    "PREPROD_REGION": codebuild.BuildEnvironmentVariable(value=preprod_region),
                    "PROD_ACCOUNT": codebuild.BuildEnvironmentVariable(value=prod_account),
                    "PROD_REGION": codebuild.BuildEnvironmentVariable(value=prod_region),
                    "PRE_PROD_VPC_ID": codebuild.BuildEnvironmentVariable(value=preprod_vpc_id),
                    "PRE_PROD_PRIVATE_SUBNET_IDS": codebuild.BuildEnvironmentVariable(value=preprod_private_subnet_ids),
                    "PRE_PROD_PUBLIC_SUBNET_IDS": codebuild.BuildEnvironmentVariable(value=preprod_public_subnet_ids),
                    "PROD_VPC_ID": codebuild.BuildEnvironmentVariable(value=prod_vpc_id),
                    "PROD_PRIVATE_SUBNET_IDS": codebuild.BuildEnvironmentVariable(value=prod_private_subnet_ids),
                    "PROD_PUBLIC_SUBNET_IDS": codebuild.BuildEnvironmentVariable(value=prod_public_subnet_ids),
                },
            ),
        )

        # code build to include security scan over cloudformation template
        security_scan = codebuild.Project(
            self,
            "SecurityScanTooling",
            build_spec=codebuild.BuildSpec.from_object(
                {
                    "version": 0.2,
                    "env": {
                        "shell": "bash",
                        "variables": {
                            "TemplateFolder": "./*.template.json",
                            "FAIL_BUILD": "true",
                        },
                    },
                    "phases": {
                        "install": {
                            "runtime-versions": {"ruby": 2.6},
                            "commands": [
                                "export date=`date +%Y-%m-%dT%H:%M:%S.%NZ`",
                                "echo Installing cfn_nag - `pwd`",
                                "gem install cfn-nag",
                                "echo cfn_nag installation complete `date`",
                            ],
                        },
                        "build": {
                            "commands": [
                                "echo Starting cfn scanning `date` in `pwd`",
                                "echo 'RulesToSuppress:\n- id: W58\n  reason: W58 is an warning raised due to Lambda "
                                "functions require permission to write CloudWatch Logs, although the lambda role "
                                "contains the policy that support these permissions cgn_nag continues to through "
                                "this problem (https://github.com/stelligent/cfn_nag/issues/422)' > cfn_nag_ignore.yml",
                                'mkdir report || echo "dir report exists"',
                                "SCAN_RESULT=$(cfn_nag_scan --fail-on-warnings --deny-list-path cfn_nag_ignore.yml "
                                "--input-path  ${TemplateFolder} -o json > ./report/cfn_nag.out.json && echo OK || "
                                "echo FAILED)",
                                "echo Completed cfn scanning `date`",
                                "echo $SCAN_RESULT",
                                "echo $FAIL_BUILD",
                                """if [[ "$FAIL_BUILD" = "true" && "$SCAN_RESULT" = "FAILED" ]]; then printf "\n\n
                                Failiing pipeline as possible insecure configurations were detected
                                \n\n" && exit 1; fi""",
                            ]
                        },
                    },
                    "artifacts": {"files": "./report/cfn_nag.out.json"},
                }
            ),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_5_0,
                environment_variables={
                    "DEPLOYMENT_ACCOUNT": codebuild.BuildEnvironmentVariable(value=Aws.ACCOUNT_ID),
                    "DEPLOYMENT_REGION": codebuild.BuildEnvironmentVariable(value=deployment_region),
                    "PREPROD_ACCOUNT": codebuild.BuildEnvironmentVariable(value=preprod_account),
                    "PREPROD_REGION": codebuild.BuildEnvironmentVariable(value=preprod_region),
                    "PROD_ACCOUNT": codebuild.BuildEnvironmentVariable(value=prod_account),
                    "PROD_REGION": codebuild.BuildEnvironmentVariable(value=prod_region),
                    "PRE_PROD_VPC_ID": codebuild.BuildEnvironmentVariable(value=preprod_vpc_id),
                    "PRE_PROD_PRIVATE_SUBNET_IDS": codebuild.BuildEnvironmentVariable(value=preprod_private_subnet_ids),
                    "PRE_PROD_PUBLIC_SUBNET_IDS": codebuild.BuildEnvironmentVariable(value=preprod_public_subnet_ids),
                    "PROD_VPC_ID": codebuild.BuildEnvironmentVariable(value=prod_vpc_id),
                    "PROD_PRIVATE_SUBNET_IDS": codebuild.BuildEnvironmentVariable(value=prod_private_subnet_ids),
                    "PROD_PUBLIC_SUBNET_IDS": codebuild.BuildEnvironmentVariable(value=prod_public_subnet_ids),
                },
            ),
        )

        source_artifact = codepipeline.Artifact(artifact_name="GitSource")
        cdk_synth_artifact = codepipeline.Artifact(artifact_name="CDKSynth")
        cfn_nag_artifact = codepipeline.Artifact(artifact_name="CfnNagScanReport")

        deploy_code_pipeline = codepipeline.Pipeline(
            self,
            "DeployPipeline",
            cross_account_keys=True,
            pipeline_name=pipeline_name,
            artifact_bucket=pipeline_artifact_bucket,
        )

        # add a source stage
        source_stage = deploy_code_pipeline.add_stage(stage_name="Source")
        source_stage.add_action(
            codepipeline_actions.CodeCommitSourceAction(
                action_name="Source",
                output=source_artifact,
                repository=deploy_app_repository,
                branch="main",
            )
        )

        # add a build stage
        build_stage = deploy_code_pipeline.add_stage(stage_name="Build")

        build_stage.add_action(
            codepipeline_actions.CodeBuildAction(
                action_name="Synth",
                input=source_artifact,
                outputs=[cdk_synth_artifact],
                project=cdk_synth_build,
            )
        )

        # add a security evaluation stage for cloudformation templates
        security_stage = deploy_code_pipeline.add_stage(stage_name="SecurityEvaluation")

        security_stage.add_action(
            codepipeline_actions.CodeBuildAction(
                action_name="CFNNag",
                input=cdk_synth_artifact,
                outputs=[cfn_nag_artifact],
                project=security_scan,
            )
        )

        # add stages to deploy to the different environments
        deploy_code_pipeline.add_stage(
            stage_name="DeployDev",
            actions=[
                codepipeline_actions.CloudFormationCreateUpdateStackAction(
                    action_name="Deploy_CFN_Dev",
                    run_order=1,
                    template_path=cdk_synth_artifact.at_path("dev.template.json"),
                    stack_name=f"{project_name}-{construct_id}-dev",
                    admin_permissions=False,
                    replace_on_failure=True,
                    role=iam.Role.from_role_arn(
                        self,
                        "DevActionRole",
                        f"arn:{Aws.PARTITION}:iam::{Aws.ACCOUNT_ID}:role/"
                        f"cdk-hnb659fds-deploy-role-{Aws.ACCOUNT_ID}-{Aws.REGION}",
                    ),
                    deployment_role=iam.Role.from_role_arn(
                        self,
                        "DevDeploymentRole",
                        f"arn:{Aws.PARTITION}:iam::{Aws.ACCOUNT_ID}:role/"
                        f"cdk-hnb659fds-cfn-exec-role-{Aws.ACCOUNT_ID}-{Aws.REGION}",
                    ),
                    cfn_capabilities=[
                        CfnCapabilities.AUTO_EXPAND,
                        CfnCapabilities.NAMED_IAM,
                    ],
                ),
                codepipeline_actions.ManualApprovalAction(
                    action_name="Approve_PreProd",
                    run_order=2,
                    additional_information="Approving deployment for preprod",
                ),
            ],
        )

        deploy_code_pipeline.add_stage(
            stage_name="DeployPreProd",
            actions=[
                codepipeline_actions.CloudFormationCreateUpdateStackAction(
                    action_name="Deploy_CFN_PreProd",
                    run_order=1,
                    template_path=cdk_synth_artifact.at_path("preprod.template.json"),
                    stack_name=f"{project_name}-{construct_id}-preprod",
                    admin_permissions=False,
                    replace_on_failure=True,
                    role=iam.Role.from_role_arn(
                        self,
                        "PreProdActionRole",
                        f"arn:{Aws.PARTITION}:iam::{preprod_account}:role/"
                        f"cdk-hnb659fds-deploy-role-{preprod_account}-{deployment_region}",
                    ),
                    deployment_role=iam.Role.from_role_arn(
                        self,
                        "PreProdDeploymentRole",
                        f"arn:{Aws.PARTITION}:iam::{preprod_account}:role/"
                        f"cdk-hnb659fds-cfn-exec-role-{preprod_account}-{deployment_region}",
                    ),
                    cfn_capabilities=[
                        CfnCapabilities.AUTO_EXPAND,
                        CfnCapabilities.NAMED_IAM,
                    ],
                ),
                codepipeline_actions.ManualApprovalAction(
                    action_name="Approve_Prod",
                    run_order=2,
                    additional_information="Approving deployment for prod",
                ),
            ],
        )

        deploy_code_pipeline.add_stage(
            stage_name="DeployProd",
            actions=[
                codepipeline_actions.CloudFormationCreateUpdateStackAction(
                    action_name="Deploy_CFN_Prod",
                    run_order=1,
                    template_path=cdk_synth_artifact.at_path("prod.template.json"),
                    stack_name=f"{project_name}-{construct_id}-prod",
                    admin_permissions=False,
                    replace_on_failure=True,
                    role=iam.Role.from_role_arn(
                        self,
                        "ProdActionRole",
                        f"arn:{Aws.PARTITION}:iam::{prod_account}:role/"
                        f"cdk-hnb659fds-deploy-role-{prod_account}-{deployment_region}",
                    ),
                    deployment_role=iam.Role.from_role_arn(
                        self,
                        "ProdDeploymentRole",
                        f"arn:{Aws.PARTITION}:iam::{prod_account}:role/"
                        f"cdk-hnb659fds-cfn-exec-role-{prod_account}-{deployment_region}",
                    ),
                    cfn_capabilities=[
                        CfnCapabilities.AUTO_EXPAND,
                        CfnCapabilities.NAMED_IAM,
                    ],
                ),
            ],
        )

        # CloudWatch rule to trigger model pipeline when a status change event happens to the model package group
        events.Rule(
            self,
            "ModelEventRule",
            event_pattern=events.EventPattern(
                source=["aws.sagemaker"],
                detail_type=["SageMaker Model Package State Change"],
                detail={
                    "ModelPackageGroupName": [model_package_group_name],
                    "ModelApprovalStatus": ["Approved", "Rejected"],
                },
            ),
            targets=[targets.CodePipeline(deploy_code_pipeline)],
        )
