import * as cdk from 'aws-cdk-lib';
import * as codebuild from 'aws-cdk-lib/aws-codebuild';
import * as codecommit from 'aws-cdk-lib/aws-codecommit';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as snsSubscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';
import * as path from 'path';
import * as utils from '../../utils';
import {
  DEFAULT_BRANCH,
  DeploymentGroup,
  MLOpsEnvironment,
  Repository,
} from '../mlops-code-pipeline-stack-props';
import { DeployModelInfo } from '../model-endpoint/model-endpoint-stack';
import { ModelEndpointStage } from '../model-endpoint/model-endpoint-stage';

export interface ModelDeployCodePipelineStackProps extends cdk.StackProps {
  readonly projectName: string;
  readonly pipelineName?: string;
  readonly modelApprovalTopicName: string;
  readonly modelBuildRepositoryName: string;
  readonly infraRepo: Repository;
  readonly deploymentGroup: DeploymentGroup;
  readonly ssmParamName?: string;
  readonly modelPackageGroupName: string;
  readonly sagemakerArtifactsBucketName: string;
}

export class ModelDeployCodePipelineStack extends cdk.Stack {
  public readonly pipeline: cdk.pipelines.CodePipeline;

  constructor(
    scope: Construct,
    id: string,
    props: ModelDeployCodePipelineStackProps,
  ) {
    super(scope, id, props);

    const {
      projectName,
      modelPackageGroupName,
      sagemakerArtifactsBucketName,
      modelBuildRepositoryName,
      infraRepo: infraRepoProps,
      deploymentGroup,
      modelApprovalTopicName,
    } = props;

    const sourceBranch = deploymentGroup.sourceBranch;
    const pipelineName =
      props.pipelineName || `${projectName}-${sourceBranch}-deploy`;
    const buildEnv = deploymentGroup.buildEnvironment;
    const deployEnvironments = deploymentGroup.deployEnvironments || [];

    // add build env to deploy env if not already exists
    if (!deployEnvironments.find((env) => env.account === buildEnv.account)) {
      deployEnvironments.unshift(buildEnv);
    }

    // create SSM param to store the approved model version that will be deployed
    const approvedModelParam = new ssm.StringParameter(
      this,
      'ApprovedModelParam',
      {
        parameterName: `/${projectName}/${deploymentGroup.name}/approved-model`,
        stringValue: 'NONE',
        description: 'The approved model version to deploy.',
      },
    );

    const modelBuildRepo = codecommit.Repository.fromRepositoryName(
      this,
      'ModelBuildRepo',
      modelBuildRepositoryName,
    );

    const infraRepo = codecommit.Repository.fromRepositoryName(
      this,
      'InfraRepo',
      infraRepoProps.name,
    );

    const pipeline = new cdk.pipelines.CodePipeline(this, 'Pipeline', {
      pipelineName,
      // this pipeline will be updated by project-infra pipeline
      selfMutation: false,
      crossAccountKeys: true,
      artifactBucket: utils.createPipelineArtifactsBucket(this),
      synth: new cdk.pipelines.CodeBuildStep('Synth', {
        input: cdk.pipelines.CodePipelineSource.codeCommit(
          infraRepo,
          infraRepoProps.branch || DEFAULT_BRANCH,
          {
            // trigger the pipeline only when a model is approved
            // this will be triggered by the lambda function listening on model approval events
            trigger: cdk.aws_codepipeline_actions.CodeCommitTrigger.NONE,
          },
        ),
        additionalInputs: {
          modelBuildRepo: cdk.pipelines.CodePipelineSource.codeCommit(
            modelBuildRepo,
            sourceBranch,
            {
              trigger: cdk.aws_codepipeline_actions.CodeCommitTrigger.NONE,
            },
          ),
        },
        commands: ['echo hello2', 'npm install', 'npx cdk synth --no-lookups'],
        buildEnvironment: {
          environmentVariables: {
            // this will be fetched from SSM param store and set as env variable automatically by codebuild
            // set this manually for testing locally
            APPROVED_MODEL_INFO: {
              type: codebuild.BuildEnvironmentVariableType.PARAMETER_STORE,
              value: approvedModelParam.parameterName,
            },
            CACHED_SEEDFARMER_ENV: {
              value: JSON.stringify(utils.getSeedFarmerEnvVars()),
            },
          },
        },
        rolePolicyStatements: [
          new iam.PolicyStatement({
            actions: ['ssm:GetParameter', 'ssm:GetParameters'],
            resources: [approvedModelParam.parameterArn],
          }),
        ],
      }),
    });
    this.pipeline = pipeline;

    // create a lambda function to listen on model approval events and start the model deploy pipeline
    this.createPipelineTriggerLambda(
      pipelineName,
      approvedModelParam,
      buildEnv,
      modelApprovalTopicName,
    );

    /**
     * Check if there are any approved models that can be deployed.
     *
     * APPROVED_MODEL_INFO will be fetched from SSM param store and set as env variable by codebuild
     * set this manually for testing locally
     * process.env.APPROVED_MODEL_INFO = '{"modelPackageArn":"model-version-arn","modelDataUrl":"model-data-url","imageUri":"container-image-uri"}';
     */
    if (
      !process.env.APPROVED_MODEL_INFO ||
      process.env.APPROVED_MODEL_INFO.trim().toLowerCase() === 'none'
    ) {
      console.log(
        `No approved model to deploy. Skipping creation of model deploy stages in CodePipeline.`,
      );
      return;
    }

    const approvedModelInfo = JSON.parse(
      process.env.APPROVED_MODEL_INFO,
    ) as DeployModelInfo;
    console.log(`Approved model version: ${approvedModelInfo}`);

    for (const env of deployEnvironments) {
      // we only support deploying to the same region as the build environment for now
      const deployRegion = buildEnv.region;
      pipeline.addStage(
        new ModelEndpointStage(this, `${projectName}-${env.name}-Endpoint`, {
          projectName,
          modelRegistryEnv: buildEnv,
          deployEnv: env,
          modelPackageGroupName,
          sagemakerArtifactsBucketName,
          deployModelInfo: approvedModelInfo,
          env: { account: env.account, region: deployRegion },
          stageName: env.name,
        }),
      );
    }
  }

  private createPipelineTriggerLambda(
    pipelineName: string,
    approvedModelParam: ssm.StringParameter,
    buildEnv: MLOpsEnvironment,
    modelApprovalTopicName: string,
  ) {
    const triggerPipelineLambda = new lambda.Function(
      this,
      'TriggerPipelineLambda',
      {
        description:
          'This function listens for model approval events and starts the model deploy pipeline',
        runtime: lambda.Runtime.PYTHON_3_12,
        handler: 'trigger_pipeline_lambda.handler',
        code: lambda.Code.fromAsset(path.join(__dirname, './trigger-pipeline')),
        environment: {
          PIPELINE_NAME: pipelineName,
          APPROVED_MODEL_PARAM_NAME: approvedModelParam.parameterName,
        },
      },
    );

    approvedModelParam.grantWrite(triggerPipelineLambda);
    const stack = cdk.Stack.of(this);
    triggerPipelineLambda.role?.addToPrincipalPolicy(
      new iam.PolicyStatement({
        actions: ['codepipeline:StartPipelineExecution'],
        resources: [
          `arn:${stack.partition}:codepipeline:${stack.region}:${stack.account}:${pipelineName}`,
        ],
      }),
    );

    const modelApprovalTopic = sns.Topic.fromTopicArn(
      this,
      'ModelApprovalTopic',
      `arn:${cdk.Aws.PARTITION}:sns:${buildEnv.region}:${buildEnv.account}:${modelApprovalTopicName}`,
    );

    modelApprovalTopic.addSubscription(
      new snsSubscriptions.LambdaSubscription(triggerPipelineLambda),
    );
  }
}
