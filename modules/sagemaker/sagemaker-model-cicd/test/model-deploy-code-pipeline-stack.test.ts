import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { ModelDeployCodePipelineStack } from '../lib';

test('ModelDeployCodePipelineStack to match snapshot', () => {
  const app = new cdk.App();
  const stack = new ModelDeployCodePipelineStack(app, 'MyTestStack', {
    projectName: 'test-project',
    deploymentGroup: {
      name: 'experimenation-deployment-group',
      sourceBranch: 'dev',
      buildEnvironment: {
        name: 'experiment-env1',
        account: '123456789012',
        region: 'us-east-1',
        type: 'dev',
      },
      deployEnvironments: [
        {
          name: 'experiment-env2',
          account: '123456789013',
          type: 'dev',
        },
        {
          name: 'experiment-env3',
          account: '123456789014',
          type: 'dev',
        },
      ],
    },
    modelApprovalTopicName: 'model-approval-topic',
    modelBuildRepositoryName: 'model-build-repo',
    infraRepo: {
      host: 'codecommit',
      name: 'infra-repo',
      branch: 'main',
    },
    modelPackageGroupName: 'model-package-group',
    ssmParamName: 'ssm-param',
    sagemakerArtifactsBucketName: 'sagemaker-artifacts-bucket',
  });
  const template = Template.fromStack(stack);
  expect(template.toJSON()).toMatchSnapshot();
});
