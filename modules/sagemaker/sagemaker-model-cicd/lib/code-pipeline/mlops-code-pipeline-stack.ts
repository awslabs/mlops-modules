import * as cdk from 'aws-cdk-lib';
import * as codecommit from 'aws-cdk-lib/aws-codecommit';
import { NagSuppressions } from 'cdk-nag';
import { Construct } from 'constructs';
import * as utils from '../utils';
import {
  DEFAULT_BRANCH,
  MLOpsCodePipelineStackProps,
} from './mlops-code-pipeline-stack-props';
import { ModelBuildPipelineSupportStage } from './model-build-support/model-build-support-stage';
import { ModelBuildCodePipelineStage } from './model-build/model-build-code-pipeline-stage';
import { ModelDeployCodePipelineStage } from './model-deploy/model-deploy-code-pipeline-stage';

/**
 * This stack creates the necessary infrastructure for a single ML project.
 *
 * CodePipelines:
 * 1. Creates a CodePipeline in tooling environment to deploy the following project resources across all environments (project-infra-pipeline)
 * 2. Creates a CodePipeline in tooling environment to start sagemaker pipeline when model build repo code changes (model-build-pipeline)
 * 3. Create a CodePipeline in tooling environment to deploy model endpoint across all deploy environments (model-deploy-pipeline)
 *
 * Cloudformation Stacks:
 * 1. Creates a Cloudformation stack in model build environment to setup required resources for model build (build-support-stack)
 * 2. Creates a Cloudformation stack in model deploy environments to deploy model endpoint (model-endpoint-stack)
 */
export class MLOpsCodePipelineStack extends cdk.Stack {
  public readonly infraRepo: codecommit.IRepository;
  public readonly modelBuildRepo: codecommit.IRepository;
  public readonly mainInfraCodePipeline: cdk.pipelines.CodePipeline;

  constructor(
    scope: Construct,
    id: string,
    props: MLOpsCodePipelineStackProps,
  ) {
    super(scope, id, props);

    const {
      projectName,
      env: toolingEnvironment,
      infraRepo,
      modelBuildRepo,
      deploymentGroups,
      tags,
    } = props;

    // get the infra codecommit repo that will be used as source for model deploy codepipeline
    this.infraRepo = codecommit.Repository.fromRepositoryName(
      this,
      'InfraRepo',
      infraRepo.name,
    );

    // get the ml codecommit repo that will be used as source for model build codepipeline
    this.modelBuildRepo = codecommit.Repository.fromRepositoryName(
      this,
      'ModelBuildRepo',
      modelBuildRepo.name,
    );

    // The main infra pipeline to deploy all other code pipelines and cloudformation stacks
    this.mainInfraCodePipeline = new cdk.pipelines.CodePipeline(
      this,
      'MLOpsCodePipeline',
      {
        pipelineName: `${projectName}-infra`,
        // this pipeline will already be updated during `seedfarmer apply`
        selfMutation: false,
        crossAccountKeys: true,
        artifactBucket: utils.createPipelineArtifactsBucket(this),
        synth: new cdk.pipelines.CodeBuildStep('Synth', {
          input: cdk.pipelines.CodePipelineSource.codeCommit(
            this.infraRepo,
            infraRepo.branch || DEFAULT_BRANCH,
          ),
          commands: ['npm install', 'npx cdk synth --no-lookups'],
          buildEnvironment: {
            environmentVariables: {
              CACHED_SEEDFARMER_ENV: {
                value: JSON.stringify(utils.getSeedFarmerEnvVars()),
              },
            },
          },
        }),
      },
    );

    for (const deploymentGroup of deploymentGroups) {
      const {
        sourceBranch,
        buildEnvironment,
        deployEnvironments = [],
      } = deploymentGroup;

      // create unique prefix for each deployment group, to support deploying multiple deployment groups targeting same account
      const prefix = `${projectName}-${deploymentGroup.name}`;
      const {
        sagemakerArtifactsBucketName,
        sagemakerExecutionRoleName,
        codeBuildAssumeRoleName,
        modelPackageGroupName,
        modelApprovalNotificationsTopicName,
      } = this.getModelBuildSupportResourceNames(prefix);

      // deploy the build support stack in model build account
      // these resources are used to build and deploy the model
      const modelBuildSupport = new ModelBuildPipelineSupportStage(
        this,
        `${prefix}-BuildSupport`,
        {
          projectName: projectName,
          toolingEnvironment: toolingEnvironment!,
          sagemakerArtifactsBucketName,
          sagemakerExecutionRoleName,
          codeBuildRoleName: codeBuildAssumeRoleName,
          modelPackageGroupName,
          modelApprovalTopicName: modelApprovalNotificationsTopicName,
          deployEnvironments,
          // Model build support resources stack should be deployed to model build account
          env: {
            account: buildEnvironment.account,
            region: buildEnvironment.region,
          },
          description: `Model build support resources for ${projectName} ${deploymentGroup.name}`,
          tags,
        },
      );
      this.mainInfraCodePipeline.addStage(modelBuildSupport);

      // create a separate codepipeline to build the model in model build account
      // The reason for separate pipeline is:
      // - Model training should only be triggered when the model build repo code changes.
      const modelBuildPipeline = new ModelBuildCodePipelineStage(
        this,
        `${prefix}-BuildPipeline`,
        {
          projectName: projectName,
          sourceBranch,
          modelBuildEnvironment: buildEnvironment,
          modelBuildSourceRepoName: modelBuildRepo.name,
          sagemakerArtifactsBucketName,
          sagemakerExecutionRoleName,
          codeBuildAssumeRoleName,
          modelPackageGroupName,
          // this pipeline should be created in tooling account, which will trigger the model build in target account
          env: toolingEnvironment,
          description: `Model build pipeline for ${projectName} ${deploymentGroup.name}`,
          tags,
        },
      );
      this.mainInfraCodePipeline.addStage(modelBuildPipeline);

      // create a separate codepipeline to deploy the model in model deploy accounts
      // The reason for separate pipeline is:
      // - Model deploy should only be triggered when the model build pipeline completes successfully and the model is approved
      const modelDeployPipeline = new ModelDeployCodePipelineStage(
        this,
        `${prefix}-DeployPipeline`,
        {
          projectName: projectName,
          modelApprovalTopicName: modelApprovalNotificationsTopicName,
          modelBuildRepositoryName: modelBuildRepo.name,
          infraRepo: infraRepo,
          deploymentGroup,
          modelPackageGroupName,
          sagemakerArtifactsBucketName,
          // this pipeline should be created in tooling account, which will trigger the model deploy in target accounts
          env: toolingEnvironment,
          description: `Model deploy pipeline for ${projectName} ${deploymentGroup.name}`,
          tags,
        },
      );
      this.mainInfraCodePipeline.addStage(modelDeployPipeline);
    }

    NagSuppressions.addStackSuppressions(
      this,
      [
        {
          id: 'AwsSolutions-IAM4',
          reason: 'Allow use of AWS managed policies',
        },
        {
          id: 'AwsSolutions-IAM5',
          reason:
            'All IAM policies are auto created by the CDK with least privilege',
        },
      ],
      true,
    );
  }

  /**
   * Create unique resource names for model build support resources such as sagemaker artifacts bucket, execution role etc.
   * This is to avoid cross-stage resouce sharing issues in the pipeline.
   */
  private getModelBuildSupportResourceNames(prefix: string) {
    const disambigutor = prefix.toLowerCase();
    const sagemakerArtifactsBucketName = utils.createResourceName(
      `sm-artifacts-${disambigutor}`,
      63,
    );
    const sagemakerExecutionRoleName = utils.createResourceName(
      `sm-execution-role-${disambigutor}`,
      64,
    );
    const codeBuildAssumeRoleName = utils.createResourceName(
      `codebuild-role-${disambigutor}`,
      64,
    );
    const modelPackageGroupName = utils.createResourceName(
      `model-pkg-group-${disambigutor}`,
      63,
    );
    const modelApprovalNotificationsTopicName = utils.createResourceName(
      `model-approval-events-${disambigutor}`,
      256,
    );
    return {
      sagemakerArtifactsBucketName,
      sagemakerExecutionRoleName,
      codeBuildAssumeRoleName,
      modelPackageGroupName,
      modelApprovalNotificationsTopicName,
    };
  }
}
