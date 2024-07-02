import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import {
  ModelDeployCodePipelineStack,
  ModelDeployCodePipelineStackProps,
} from './model-deploy-code-pipeline-stack';

export interface ModelDeployCodePipelineStageProps
  extends cdk.StageProps,
    ModelDeployCodePipelineStackProps {}

export class ModelDeployCodePipelineStage extends cdk.Stage {
  public readonly modelDeployCodePipelineStack: ModelDeployCodePipelineStack;
  constructor(
    scope: Construct,
    id: string,
    props: ModelDeployCodePipelineStageProps,
  ) {
    super(scope, id, props);
    this.modelDeployCodePipelineStack = new ModelDeployCodePipelineStack(
      this,
      'ModelDeployCodePipelineStack',
      {
        stackName: id,
        ...props,
      },
    );
  }
}
