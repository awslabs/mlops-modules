import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import {
  ModelBuildCodePipelineProps,
  ModelBuildCodePipelineStack,
} from './model-build-code-pipeline-stack';

export interface ModelBuildCodePipelineStageProps
  extends cdk.StageProps,
    ModelBuildCodePipelineProps {}

export class ModelBuildCodePipelineStage extends cdk.Stage {
  public readonly modelBuildCodePipelineStack: ModelBuildCodePipelineStack;
  constructor(
    scope: Construct,
    id: string,
    props: ModelBuildCodePipelineStageProps,
  ) {
    super(scope, id, props);
    this.modelBuildCodePipelineStack = new ModelBuildCodePipelineStack(
      this,
      'ModelBuildCodePipelineStack',
      {
        stackName: id,
        ...props,
      },
    );
  }
}
