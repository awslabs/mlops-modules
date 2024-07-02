import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { ModelBuildSupportStack } from '../lib';

test('ModelBuildSupportStack to match snapshot', () => {
  const app = new cdk.App();
  const stack = new ModelBuildSupportStack(app, 'MyTestStack', {
    projectName: 'test-project',
    toolingEnvironment: {
      account: '123456789012',
      region: 'us-east-1',
    },
    sagemakerArtifactsBucketName: 'sagemaker-artifacts-bucket',
    sagemakerExecutionRoleName: 'sagemaker-execution-role',
    modelPackageGroupName: 'model-package-group',
    codeBuildRoleName: 'code-build-role',
    modelApprovalTopicName: 'model-approval-topic',
    deployEnvironments: [
      {
        name: 'gamma-env',
        account: '123456789013',
        type: 'preprod',
      },
      {
        name: 'prod-env',
        account: '123456789014',
        type: 'prod',
      },
    ],
  });
  const template = Template.fromStack(stack);
  expect(template.toJSON()).toMatchSnapshot();
});
