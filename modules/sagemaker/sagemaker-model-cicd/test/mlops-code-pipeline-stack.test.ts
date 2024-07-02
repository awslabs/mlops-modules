import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { MLOpsCodePipelineStack } from '../lib';

test('MLOpsCodePipelineStack to match snapshot', () => {
  const app = new cdk.App();
  const stack = new MLOpsCodePipelineStack(app, 'MyTestStack', {
    env: { account: '123456789011', region: 'us-east-1' }, // tooling account
    projectName: 'TestProject',
    deploymentGroups: [
      // experimenation deployment group to train model on test dataset
      {
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
      // prod deployment group with retraining on prod dataset
      {
        name: 'prod-deployment-group',
        sourceBranch: 'main',
        buildEnvironment: {
          name: 'prod-train-env',
          account: '123456789015',
          region: 'us-east-1',
          type: 'preprod',
        },
        deployEnvironments: [
          {
            name: 'prod-approval-env',
            account: '123456789016',
            type: 'preprod',
          },
          {
            name: 'prod-env',
            account: '123456789017',
            type: 'prod',
          },
        ],
      },
    ],
    modelBuildRepo: {
      host: 'codecommit',
      name: 'model-build-repo',
    },
    infraRepo: {
      host: 'codecommit',
      name: 'model-deploy-repo',
      branch: 'main',
    },
  });
  const template = Template.fromStack(stack);
  expect(template.toJSON()).toMatchSnapshot();
});
