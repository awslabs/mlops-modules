import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { ModelEndpointStack } from '../lib';

test('ModelEndpointStack to match snapshot', () => {
  // timestamp is used to generate unique names for resources in this stack
  jest.spyOn(Date, 'now').mockReturnValue(123456789);
  const app = new cdk.App();
  const stack = new ModelEndpointStack(app, 'MyTestStack', {
    projectName: 'test-project',
    modelRegistryEnv: {
      name: 'model-registry',
      account: '123456789012',
      region: 'us-east-1',
      type: 'dev',
    },
    sagemakerArtifactsBucketName: 'sagemaker-artifacts-bucket',
    deployEnv: {
      name: 'deploy-env',
      account: '123456789013',
      type: 'dev',
    },
    modelPackageGroupName: 'model-package-group',
    deployModelInfo: {
      modelPackageArn: 'model-package-arn',
      modelDataUrl: 'model-data-url',
      imageUri: 'image-uri',
    },
  });
  const template = Template.fromStack(stack);
  expect(template.toJSON()).toMatchSnapshot();
  jest.restoreAllMocks();
});
