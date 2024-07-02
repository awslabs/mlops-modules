import * as cdk from 'aws-cdk-lib';
import * as codebuild from 'aws-cdk-lib/aws-codebuild';
import * as codecommit from 'aws-cdk-lib/aws-codecommit';
import * as codepipeline from 'aws-cdk-lib/aws-codepipeline';
import * as codepipeline_actions from 'aws-cdk-lib/aws-codepipeline-actions';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import * as utils from '../../utils';
import { MLOpsEnvironment } from '../mlops-code-pipeline-stack-props';

export interface ModelBuildCodePipelineProps extends cdk.StackProps {
  readonly projectName: string;
  readonly pipelineName?: string;
  readonly pipelineDescription?: string;
  readonly sourceBranch: string;
  readonly modelBuildEnvironment: MLOpsEnvironment;
  readonly modelBuildSourceRepoName: string;
  readonly sagemakerArtifactsBucketName: string;
  readonly sagemakerExecutionRoleName: string;
  readonly codeBuildAssumeRoleName: string;
  readonly modelPackageGroupName: string;
}

export class ModelBuildCodePipelineStack extends cdk.Stack {
  public readonly pipeline: codepipeline.Pipeline;

  constructor(
    scope: Construct,
    id: string,
    props: ModelBuildCodePipelineProps,
  ) {
    super(scope, id, props);

    const {
      projectName,
      sourceBranch,
      modelBuildEnvironment,
      modelBuildSourceRepoName,
      sagemakerArtifactsBucketName,
      sagemakerExecutionRoleName,
      codeBuildAssumeRoleName,
      modelPackageGroupName,
      pipelineName = `${projectName}-${sourceBranch}-build`,
      pipelineDescription = `${projectName} model build pipeline for ${sourceBranch} branch`,
    } = props;

    const codeBuildRole = new iam.Role(this, 'CodeBuildRole', {
      assumedBy: new iam.ServicePrincipal('codebuild.amazonaws.com'),
      path: '/service-role/',
    });

    // CodeBuild will assume this cross-account role in the model build account to start the SageMaker pipeline
    const codeBuildAssumeRole = iam.Role.fromRoleArn(
      this,
      'CodeBuildAssumeRole',
      `arn:aws:iam::${modelBuildEnvironment.account}:role/${codeBuildAssumeRoleName}`,
    );

    // this role will be used by model build code (i.e., sagemaker service) to access aws resources in the model build environment
    const sageMakerExecutionRoleArn = `arn:aws:iam::${modelBuildEnvironment.account}:role/service-role/${sagemakerExecutionRoleName}`;

    const codeBuildPolicy = new iam.Policy(this, 'CodeBuildPolicy', {
      document: new iam.PolicyDocument({
        statements: [
          new iam.PolicyStatement({
            sid: 'AssumeSageMakerAccessRole',
            actions: ['sts:AssumeRole'],
            resources: [codeBuildAssumeRole.roleArn],
          }),
          new iam.PolicyStatement({
            sid: 'LogsAccess',
            actions: [
              'logs:CreateLogGroup',
              'logs:CreateLogStream',
              'logs:PutLogEvents',
            ],
            resources: ['*'],
          }),
          new iam.PolicyStatement({
            sid: 'MetricsAccess',
            actions: ['cloudwatch:PutMetricData'],
            resources: ['*'],
          }),
        ],
      }),
    });
    codeBuildPolicy.attachToRole(codeBuildRole);

    const smPipelineBuild = new codebuild.PipelineProject(
      this,
      'SMPipelineBuild',
      {
        projectName: pipelineName,
        role: codeBuildRole,
        buildSpec: codebuild.BuildSpec.fromSourceFilename('buildspec.yml'),
        environment: {
          buildImage: codebuild.LinuxBuildImage.STANDARD_7_0,
          environmentVariables: {
            // set aws sdk calls to correct region incase of cross region pipeline
            AWS_REGION: { value: modelBuildEnvironment.region },
            // this role will be assumed by codebuild to start the sagemaker pipeline in model build environment
            ASSUME_ROLE_ARN: { value: codeBuildAssumeRole.roleArn },
            ENV_TYPE: { value: modelBuildEnvironment.type },
            PROJECT_NAME: { value: projectName },
            MODEL_PACKAGE_GROUP_NAME: { value: modelPackageGroupName },
            SAGEMAKER_PIPELINE_NAME: { value: pipelineName },
            SAGEMAKER_PIPELINE_DESCRIPTION: { value: pipelineDescription },
            // this role will be assumed by sagemaker service to access aws resources in the model build environment
            SAGEMAKER_PIPELINE_ROLE_ARN: { value: sageMakerExecutionRoleArn },
            ARTIFACT_BUCKET: { value: sagemakerArtifactsBucketName },
            ARTIFACT_BUCKET_KMS_KEY: {
              value: `alias/${sagemakerArtifactsBucketName}`,
            },
          },
        },
      },
    );

    const buildPipeline = new codepipeline.Pipeline(this, 'BuildPipeline', {
      pipelineName,
      artifactBucket: utils.createPipelineArtifactsBucket(this),
    });
    this.pipeline = buildPipeline;

    // Add a source stage
    const sourceStage = buildPipeline.addStage({ stageName: 'Source' });
    const buildRepository = codecommit.Repository.fromRepositoryName(
      this,
      'BuildRepo',
      modelBuildSourceRepoName,
    );
    const sourceArtifact = new codepipeline.Artifact('GitSource');
    sourceStage.addAction(
      new codepipeline_actions.CodeCommitSourceAction({
        actionName: 'Source',
        output: sourceArtifact,
        repository: buildRepository,
        branch: sourceBranch,
      }),
    );

    // Add a build stage
    const buildStage = buildPipeline.addStage({ stageName: 'StartModelBuild' });
    buildStage.addAction(
      new codepipeline_actions.CodeBuildAction({
        actionName: 'SMPipeline',
        input: sourceArtifact,
        project: smPipelineBuild,
      }),
    );
  }
}
