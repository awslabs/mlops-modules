#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { AwsSolutionsChecks } from 'cdk-nag';
import 'source-map-support/register';
import { MLOpsCodePipelineStack } from '../lib';
import {
  getModuleInfo,
  getModuleParameters,
  loadSeedFarmerEnvVars,
} from './seedfarmer-parameters';

// load seedfarmer environment variables from cache for codepipeline deployments
loadSeedFarmerEnvVars();

const account = process.env.CDK_DEFAULT_ACCOUNT;
const region = process.env.CDK_DEFAULT_REGION;
const { sfProjectName, sfDeploymentName, sfModuleName } = getModuleInfo();
const moduleParameters = getModuleParameters();

const app = new cdk.App();
const stackName = moduleParameters.projectName;
new MLOpsCodePipelineStack(app, stackName, {
  env: {
    account,
    region,
  },
  tags: {
    SeedFarmerProjectName: sfProjectName,
    SeedFarmerDeploymentName: sfDeploymentName,
    SeedFarmerModuleName: sfModuleName,
  },
  ...moduleParameters,
});

cdk.Tags.of(app).add('SeedFarmerProjectName', sfProjectName);
cdk.Tags.of(app).add('SeedFarmerDeploymentName', sfDeploymentName);
cdk.Tags.of(app).add('SeedFarmerModuleName', sfModuleName);

cdk.Aspects.of(app).add(new AwsSolutionsChecks());

app.synth();
