import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import {
  ModelEndpointStack,
  ModelEndpointStackProps,
} from './model-endpoint-stack';

export interface ModelEndpointStageStageProps
  extends cdk.StageProps,
    ModelEndpointStackProps {}

export class ModelEndpointStage extends cdk.Stage {
  public readonly modelEndpointStack: ModelEndpointStack;
  constructor(
    scope: Construct,
    id: string,
    props: ModelEndpointStageStageProps,
  ) {
    super(scope, id, props);
    this.modelEndpointStack = new ModelEndpointStack(
      this,
      'ModelEndpointStack',
      {
        stackName: id,
        description: 'Model endpoint',
        ...props,
      },
    );
  }
}
