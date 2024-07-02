import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { ModelBuildCodePipelineStack } from '../lib';

test('ModelBuildCodePipelineStack to match snapshot', () => {
  const app = new cdk.App();
  const stack = new ModelBuildCodePipelineStack(app, 'MyTestStack', {
    projectName: 'test-project',
    sourceBranch: 'main',
    modelBuildEnvironment: {
      name: 'model-build',
      account: '123456789012',
      region: 'us-east-1',
      type: 'dev',
    },
    modelBuildSourceRepoName: 'model-build-repo',
    sagemakerArtifactsBucketName: 'sagemaker-artifacts-bucket',
    sagemakerExecutionRoleName: 'sagemaker-execution-role',
    codeBuildAssumeRoleName: 'codebuild-assume-role',
    modelPackageGroupName: 'model-package-group',
  });
  const template = Template.fromStack(stack);
  expect(template.toJSON()).toMatchSnapshot();
});
