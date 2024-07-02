import * as cdk from 'aws-cdk-lib';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as sagemaker from 'aws-cdk-lib/aws-sagemaker';
import * as sns from 'aws-cdk-lib/aws-sns';
import { Construct } from 'constructs';
import { DeployEnvironment } from '../mlops-code-pipeline-stack-props';

export interface ModelBuildSupportStackProps extends cdk.StackProps {
  readonly projectName: string;
  readonly toolingEnvironment: cdk.Environment;
  readonly sagemakerArtifactsBucketName: string;
  readonly sagemakerExecutionRoleName: string;
  readonly codeBuildRoleName: string;
  readonly modelPackageGroupName: string;
  readonly modelApprovalTopicName: string;
  readonly deployEnvironments: DeployEnvironment[];
}

export class ModelBuildSupportStack extends cdk.Stack {
  public readonly modelApprovalTopicArn: string;

  constructor(
    scope: Construct,
    id: string,
    props: ModelBuildSupportStackProps,
  ) {
    super(scope, id, props);

    const {
      projectName,
      sagemakerArtifactsBucketName,
      sagemakerExecutionRoleName,
      codeBuildRoleName,
      modelPackageGroupName,
      modelApprovalTopicName,
      deployEnvironments,
      toolingEnvironment,
    } = props;

    const deploymentAccountPrincipals: iam.AccountPrincipal[] =
      deployEnvironments.map((env) => new iam.AccountPrincipal(env.account));

    const toolingAccountPrincipal = new iam.AccountPrincipal(
      toolingEnvironment.account,
    );
    const allCrossAccountPrincipals = [
      toolingAccountPrincipal,
      ...deploymentAccountPrincipals,
    ];

    const kmsKey = new kms.Key(this, 'ArtifactsBucketKMSKey', {
      description: 'key used for encryption of data in Amazon S3',
      enableKeyRotation: true,
      policy: new iam.PolicyDocument({
        statements: [
          new iam.PolicyStatement({
            actions: ['kms:*'],
            effect: iam.Effect.ALLOW,
            resources: ['*'],
            principals: [new iam.AccountRootPrincipal()],
          }),
        ],
      }),
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    kmsKey.addToResourcePolicy(
      new iam.PolicyStatement({
        actions: [
          'kms:Encrypt',
          'kms:Decrypt',
          'kms:ReEncrypt*',
          'kms:GenerateDataKey*',
          'kms:DescribeKey',
        ],
        resources: ['*'],
        principals: allCrossAccountPrincipals,
      }),
    );

    new kms.Alias(this, 'ArtifactsBucketKMSKeyAlias', {
      aliasName: `alias/${sagemakerArtifactsBucketName}`,
      targetKey: kmsKey,
    });

    const logsBucket = new s3.Bucket(this, 'LogsBucket', {
      encryption: s3.BucketEncryption.KMS,
      encryptionKey: kmsKey,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      enforceSSL: true,
    });

    const sagemakerArtifactsBucket = new s3.Bucket(this, 'ArtifactsBucket', {
      bucketName: sagemakerArtifactsBucketName,
      encryption: s3.BucketEncryption.KMS,
      encryptionKey: kmsKey,
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      enforceSSL: true,
      serverAccessLogsBucket: logsBucket,
      serverAccessLogsPrefix: `${sagemakerArtifactsBucketName}/`,
      // allow sagemaker studio ui to read model metrics from this bucket
      cors: [
        {
          allowedMethods: [s3.HttpMethods.GET, s3.HttpMethods.HEAD],
          allowedOrigins: [
            `https://*.studio.${cdk.Stack.of(this).region}.sagemaker.aws`,
          ],
          allowedHeaders: ['*'],
          exposedHeaders: ['Access-Control-Allow-Origin'],
        },
      ],
    });

    sagemakerArtifactsBucket.addToResourcePolicy(
      new iam.PolicyStatement({
        sid: 'AddCurrentAccountPermissions',
        actions: ['s3:*'],
        resources: [
          sagemakerArtifactsBucket.arnForObjects('*'),
          sagemakerArtifactsBucket.bucketArn,
        ],
        principals: [new iam.AccountRootPrincipal()],
      }),
    );

    sagemakerArtifactsBucket.addToResourcePolicy(
      new iam.PolicyStatement({
        sid: 'AddCrossAccountPermissions',
        actions: ['s3:List*', 's3:Get*', 's3:Put*'],
        resources: [
          sagemakerArtifactsBucket.arnForObjects('*'),
          sagemakerArtifactsBucket.bucketArn,
        ],
        principals: allCrossAccountPrincipals,
      }),
    );

    const modelPackageGroupPolicy = new iam.PolicyDocument({
      statements: [
        new iam.PolicyStatement({
          sid: 'ModelPackageGroup',
          actions: ['sagemaker:DescribeModelPackageGroup'],
          resources: [
            `arn:aws:sagemaker:${cdk.Stack.of(this).region}:${cdk.Stack.of(this).account}:model-package-group/${modelPackageGroupName}`,
          ],
          principals: allCrossAccountPrincipals,
        }),
        new iam.PolicyStatement({
          sid: 'ModelPackage',
          actions: [
            'sagemaker:DescribeModelPackage',
            'sagemaker:ListModelPackages',
            'sagemaker:UpdateModelPackage',
            'sagemaker:CreateModel',
          ],
          resources: [
            `arn:aws:sagemaker:${cdk.Stack.of(this).region}:${cdk.Stack.of(this).account}:model-package/${modelPackageGroupName}/*`,
          ],
          principals: allCrossAccountPrincipals,
        }),
      ],
    });

    new sagemaker.CfnModelPackageGroup(this, 'ModelPackageGroup', {
      modelPackageGroupName: modelPackageGroupName,
      modelPackageGroupDescription: `Model Package Group for ${projectName}`,
      modelPackageGroupPolicy: modelPackageGroupPolicy.toJSON(),
    });

    const sagemakerExecutionRole = new iam.Role(
      this,
      'SageMakerExecutionRole',
      {
        assumedBy: new iam.ServicePrincipal('sagemaker.amazonaws.com'),
        path: '/service-role/',
        roleName: sagemakerExecutionRoleName,
        description: `This role is assumed by SageMaker service for executing the pipeline for ${projectName}`,
      },
    );

    const codebuildRole = new iam.Role(this, 'ToolingCodeBuildRole', {
      assumedBy: toolingAccountPrincipal,
      roleName: codeBuildRoleName,
      description: `This role is assumed by CodeBuild in tooling account for executing SageMaker pipeline for ${projectName}`,
    });

    const sagemakerPolicy = new iam.Policy(this, 'SageMakerPolicy', {
      document: new iam.PolicyDocument({
        statements: [
          new iam.PolicyStatement({
            actions: [
              'logs:CreateLogGroup',
              'logs:CreateLogStream',
              'logs:PutLogEvents',
            ],
            resources: ['*'],
          }),
          new iam.PolicyStatement({
            actions: ['sagemaker:*'],
            notResources: [
              'arn:aws:sagemaker:*:*:domain/*',
              'arn:aws:sagemaker:*:*:user-profile/*',
              'arn:aws:sagemaker:*:*:app/*',
              'arn:aws:sagemaker:*:*:flow-definition/*',
            ],
          }),
          new iam.PolicyStatement({
            actions: [
              'ecr:BatchCheckLayerAvailability',
              'ecr:BatchGetImage',
              'ecr:Describe*',
              'ecr:GetAuthorizationToken',
              'ecr:GetDownloadUrlForLayer',
            ],
            resources: ['*'],
          }),
          new iam.PolicyStatement({
            actions: ['cloudwatch:PutMetricData'],
            resources: ['*'],
          }),
          new iam.PolicyStatement({
            actions: [
              's3:AbortMultipartUpload',
              's3:DeleteObject',
              's3:GetBucket*',
              's3:GetObject*',
              's3:List*',
              's3:PutObject*',
              's3:Create*',
            ],
            resources: [
              sagemakerArtifactsBucket.bucketArn,
              `${sagemakerArtifactsBucket.bucketArn}/*`,
              'arn:aws:s3:::sagemaker-*',
            ],
          }),
          new iam.PolicyStatement({
            actions: ['iam:PassRole'],
            resources: [sagemakerExecutionRole.roleArn],
          }),
          new iam.PolicyStatement({
            actions: [
              'kms:Encrypt',
              'kms:ReEncrypt*',
              'kms:GenerateDataKey*',
              'kms:Decrypt',
              'kms:DescribeKey',
            ],
            effect: iam.Effect.ALLOW,
            resources: [
              `arn:aws:kms:${cdk.Stack.of(this).region}:${cdk.Stack.of(this).account}:key/*`,
            ],
          }),
        ],
      }),
    });
    sagemakerPolicy.attachToRole(sagemakerExecutionRole);
    sagemakerPolicy.attachToRole(codebuildRole);

    const modelApprovalTopic = new sns.Topic(this, modelApprovalTopicName, {
      displayName: 'Model Approval Topic',
      topicName: modelApprovalTopicName,
    });
    this.modelApprovalTopicArn = modelApprovalTopic.topicArn;

    const modelApprovalRule = new events.Rule(this, 'ModelApprovalRule', {
      eventPattern: {
        source: ['aws.sagemaker'],
        detailType: ['SageMaker Model Package State Change'],
        detail: {
          ModelPackageGroupName: [modelPackageGroupName],
          ModelApprovalStatus: ['Approved'],
        },
      },
      targets: [new targets.SnsTopic(modelApprovalTopic)],
    });

    modelApprovalTopic.addToResourcePolicy(
      new iam.PolicyStatement({
        actions: ['sns:Publish'],
        principals: [new iam.ServicePrincipal('events.amazonaws.com')],
        resources: [modelApprovalTopic.topicArn],
        conditions: {
          ArnLike: {
            'aws:SourceArn': modelApprovalRule.ruleArn,
          },
        },
      }),
    );

    modelApprovalTopic.addToResourcePolicy(
      new iam.PolicyStatement({
        actions: ['sns:Subscribe'],
        principals: [toolingAccountPrincipal],
        resources: [this.modelApprovalTopicArn],
      }),
    );
  }
}
