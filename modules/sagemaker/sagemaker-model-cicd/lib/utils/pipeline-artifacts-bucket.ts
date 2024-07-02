import * as cdk from 'aws-cdk-lib';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { NagSuppressions } from 'cdk-nag';
import { Construct } from 'constructs';

export function createPipelineArtifactsBucket(scope: Construct): s3.Bucket {
  const removalPolicy = cdk.RemovalPolicy.DESTROY;
  const autoDeleteObjects = removalPolicy === cdk.RemovalPolicy.DESTROY;

  const pipelineArtifactsBucketKms = new kms.Key(
    scope,
    'PipelineArtifactsBucketKms',
    {
      removalPolicy,
      enableKeyRotation: true,
    },
  );

  const pipelineArtifactsBucket = new s3.Bucket(
    scope,
    'PipelineArtifactBucket',
    {
      encryptionKey: pipelineArtifactsBucketKms,
      removalPolicy,
      autoDeleteObjects,
      bucketKeyEnabled: true,
      enforceSSL: true,
    },
  );
  NagSuppressions.addResourceSuppressions(pipelineArtifactsBucket, [
    {
      id: 'AwsSolutions-S1',
      reason: 'The bucket stores pipeline artifacts, no logging required.',
    },
  ]);
  return pipelineArtifactsBucket;
}
