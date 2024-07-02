import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import {
  ModelBuildSupportStack,
  ModelBuildSupportStackProps,
} from './model-build-support-stack';

export interface MLOpsBuildPipelineSupportStageProps
  extends cdk.StageProps,
    ModelBuildSupportStackProps {}

export class ModelBuildPipelineSupportStage extends cdk.Stage {
  public readonly buildSupportStack: ModelBuildSupportStack;
  constructor(
    scope: Construct,
    id: string,
    props: MLOpsBuildPipelineSupportStageProps,
  ) {
    super(scope, id, props);
    this.buildSupportStack = new ModelBuildSupportStack(
      this,
      'ModelBuildSupportStack',
      {
        stackName: id,
        ...props,
      },
    );
  }
}
