import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as sagemaker from 'aws-cdk-lib/aws-sagemaker';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

import {
  BuildEnvironment,
  DeployEnvironment,
  MLOpsEnvironment,
} from '../mlops-code-pipeline-stack-props';

export interface DeployModelInfo {
  /**
   * The arn of the model package version to deploy
   */
  readonly modelPackageArn: string;
  /**
   * The model data location
   */
  readonly modelDataUrl: string;
  /**
   * The container image URI
   * Required if `modelPackageArn` is not provided
   */
  readonly imageUri?: string;
}

export interface ModelEndpointStackProps extends cdk.StackProps {
  readonly projectName: string;
  readonly modelRegistryEnv: BuildEnvironment;
  readonly deployEnv: DeployEnvironment;
  readonly modelPackageGroupName: string;
  /**
   * The S3 bucket in the model registry environment that has the model artifacts stored after the model training is complete
   */
  readonly sagemakerArtifactsBucketName: string;
  /**
   * Describes the container, as part of model definition.
   */
  readonly deployModelInfo: DeployModelInfo;
  /**
   * Specifies the resources to deploy for hosting the model
   */
  readonly productionVariant?: sagemaker.CfnEndpointConfig.ProductionVariantProperty;
  /**
   * SSM parameter name used to retrieve Subnet IDs for deploying the model endpoint
   *
   * @default `/${projectName}/vpc/subnets/private/ids`
   */
  readonly subnetIdsParameter?: string;
  /**
   * SSM parameter name used to retrieve Security Group ID for deploying the model endpoint
   *
   * @default `/${projectName}/vpc/sg/id`
   */
  readonly securityGroupIdParameter?: string;
}

export class ModelEndpointStack extends cdk.Stack {
  public readonly endpoint: sagemaker.CfnEndpoint;
  public readonly model: sagemaker.CfnModel;

  constructor(scope: Construct, id: string, props: ModelEndpointStackProps) {
    super(scope, id, props);

    const {
      projectName,
      deployModelInfo,
      sagemakerArtifactsBucketName,
      modelRegistryEnv,
      modelPackageGroupName,
      productionVariant = {
        variantName: 'AllTraffic',
        initialInstanceCount: 1,
        initialVariantWeight: 1,
        instanceType: 'ml.m5.xlarge',
      },
      subnetIdsParameter = `/${projectName}/vpc/subnets/private/ids`,
      securityGroupIdParameter = `/${projectName}/vpc/sg/id`,
    } = props;

    const subnetIds = ssm.StringListParameter.valueForTypedListParameter(
      this,
      subnetIdsParameter,
      ssm.ParameterValueType.AWS_EC2_SUBNET_ID,
    );

    const sgId = ssm.StringParameter.valueForTypedStringParameterV2(
      this,
      securityGroupIdParameter,
      ssm.ParameterValueType.AWS_EC2_SECURITYGROUP_ID,
    );

    const timestamp = Date.now();

    // iam role that would be used by the model endpoint to run the inference
    const modelExecutionRole = this.createSagemakerExecutionRole(
      modelRegistryEnv,
      sagemakerArtifactsBucketName,
    );

    // KMS key that will be used to encrypt the storage volume attached to compute instance
    const endpointKmsKey = this.createEndpointKmsKey();

    const modelPackageArn = deployModelInfo.modelPackageArn;

    // Specify the containers in the inference pipeline.
    const containerDef: sagemaker.CfnModel.ContainerDefinitionProperty = {
      modelPackageName: modelPackageArn,
    };

    // Create a model to host at an Amazon SageMaker endpoint
    const modelName =
      productionVariant.modelName || `${modelPackageGroupName}-${timestamp}`;
    const model = new sagemaker.CfnModel(this, 'Model', {
      modelName,
      executionRoleArn: modelExecutionRole.roleArn,
      containers: [containerDef],
      vpcConfig: {
        securityGroupIds: [sgId],
        subnets: subnetIds,
      },
    });
    this.model = model;

    // Create a configuration for an Amazon SageMaker endpoint
    const endpointConfigName = `${projectName}-ec-${timestamp}`;
    const endpointConfig = new sagemaker.CfnEndpointConfig(
      this,
      'EndpointConfig',
      {
        endpointConfigName,
        kmsKeyId: endpointKmsKey.keyId,
        productionVariants: [productionVariant],
      },
    );
    endpointConfig.node.addDependency(model);

    // Create an endpoint using the specified configuration
    const endpointName = `${projectName}-e`;
    const endpoint = new sagemaker.CfnEndpoint(this, 'Endpoint', {
      endpointConfigName,
      endpointName: endpointName,
    });
    endpoint.node.addDependency(endpointConfig);
    this.endpoint = endpoint;
  }

  /**
   * Creates a KMS key that Amazon SageMaker uses to encrypt data on the storage volume
   * attached to the ML compute instance that hosts the endpoint.
   */
  private createEndpointKmsKey() {
    return new kms.Key(this, 'EndpointKmsKey', {
      description:
        'Key used for encryption of data in Amazon SageMaker Endpoint',
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
  }

  /**
   * Creates the IAM role that SageMaker can assume to access model artifacts and
   * docker image for deployment on ML compute instances or for batch transform jobs.
   */
  private createSagemakerExecutionRole(
    modelRegistryEnv: MLOpsEnvironment,
    sagemakerArtifactsBucketName: string,
  ) {
    const sagemakerArtifactsBucket = s3.Bucket.fromBucketAttributes(
      this,
      'ModelArtifactsBucket',
      {
        bucketName: sagemakerArtifactsBucketName,
        account: modelRegistryEnv.account,
        region: modelRegistryEnv.region,
      },
    );

    const modelExecutionPolicy = new iam.ManagedPolicy(
      this,
      'ModelExecutionPolicy',
      {
        statements: [
          // grant cross account kms access used for encrypting the model artifacts bucket in model registry environment
          new iam.PolicyStatement({
            sid: 'ModelArtifactsBucketKeyAccess',
            effect: iam.Effect.ALLOW,
            actions: [
              'kms:Encrypt',
              'kms:Decrypt',
              'kms:ReEncrypt*',
              'kms:GenerateDataKey*',
              'kms:CreateGrant',
              'kms:ListGrants',
              'kms:DescribeKey',
            ],
            resources: [
              `arn:aws:kms:${modelRegistryEnv.region}:${modelRegistryEnv.account}:key/*`,
            ],
            // since this is typically a cross account key with a autogenerated key id,
            // we use kms key resource alias condition to restrict access
            // instead of having to require this as stack parameter
            conditions: {
              'ForAnyValue:StringEquals': {
                'kms:ResourceAliases': `alias/${sagemakerArtifactsBucketName}`,
              },
              StringEquals: {
                'kms:ViaService': `s3.${modelRegistryEnv.region}.amazonaws.com`,
              },
            },
          }),
        ],
      },
    );

    const modelExecutionRole = new iam.Role(this, 'ModelExecutionRole', {
      assumedBy: new iam.ServicePrincipal('sagemaker.amazonaws.com'),
      managedPolicies: [
        modelExecutionPolicy,
        iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonSageMakerFullAccess'),
      ],
    });

    sagemakerArtifactsBucket.grantReadWrite(modelExecutionRole);

    return modelExecutionRole;
  }
}
