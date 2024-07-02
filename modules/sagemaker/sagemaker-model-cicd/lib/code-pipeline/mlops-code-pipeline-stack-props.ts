import * as cdk from 'aws-cdk-lib';
import { z } from 'zod';

export const DEFAULT_BRANCH = 'main';

/**
 * Type of environment
 */
const EnvTypeSchema = z.enum(['dev', 'preprod', 'prod']);

/**
 * Supported repository hosts
 */
const SupportedRepositoryHostsSchema = z.enum(['codecommit']);

/**
 * Schema for repository properties
 */
const RepositorySchema = z.object({
  /**
   * Host of the repository.
   */
  host: SupportedRepositoryHostsSchema,
  /**
   * Name of the repository.
   */
  name: z.string(),
  /**
   * Source branch to trigger the pipeline.
   * @default main
   */
  branch: z.string().default(DEFAULT_BRANCH).optional(),
});

/**
 * Schema for MLOps environment properties
 */
const MLOpsEnvironmentSchema = z.object({
  /**
   * The name of the environment.
   */
  name: z.string(),
  /**
   * The AWS account associated with the environment.
   */
  account: z.string(),
  /**
   * The AWS region associated with the environment.
   */
  region: z.string(),
  /**
   * Indicates whether the environment is a dev, preprod or prod environment.
   */
  type: EnvTypeSchema,
});

/**
 * Schema for build environment, same as MLOps environment
 */
const BuildEnvironmentSchema = MLOpsEnvironmentSchema;

/**
 * Schema for deploy environment
 */
const DeployEnvironmentSchema = MLOpsEnvironmentSchema.omit({
  region: true,
});

/**
 * Schema for deployment group properties
 */
const DeploymentGroupSchema = z.object({
  /**
   * The name of the deployment group.
   * This will be used to name the code pipelines.
   */
  name: z.string(),
  /**
   * Source branch to trigger the pipeline for model build.
   */
  sourceBranch: z.string(),
  /**
   * The environment to build the model.
   */
  buildEnvironment: BuildEnvironmentSchema,
  /**
   * The environments to deploy the model to.
   * The build environment will be added to the deploy environments if not already exists.
   * For now, we only support deploying to the same region as the build environment.
   * @default - Deploy to only the build environment.
   */
  deployEnvironments: DeployEnvironmentSchema.array().default([]).optional(),
});

/**
 * Main schema for MLOps code pipeline
 */
export const MLOpsCodePipelinePropsSchema = z.object({
  /**
   * The unique identifier for this MLOps project within an AWS account.
   * Caution: To prevent destructive outcomes, avoid altering this value post-initial deployment.
   */
  projectName: z.string(),
  /**
   * Deployment groups organize the model build(train) and model deploy code pipelines by specific criteria or environments.
   * Use Case:
   * Ideal for scenarios requiring model retraining with different datasets and deployment across various environments.
   * Key Features:
   * - Each group corresponds to a unique set of build and deploy pipelines.
   * - Triggered by commits to a designated source branch.
   * - Utilizes a build environment for model training and deploy environments for model deployment.
   */
  deploymentGroups: DeploymentGroupSchema.array(),
  /**
   * The repository for model build.
   */
  modelBuildRepo: RepositorySchema.omit({ branch: true }),
  /**
   * The repository for model deployment.
   */
  infraRepo: RepositorySchema,
});

export type MLOpsCodePipelineStackProps = z.infer<
  typeof MLOpsCodePipelinePropsSchema
> &
  cdk.StackProps;
export type DeploymentGroup = z.infer<typeof DeploymentGroupSchema>;
export type MLOpsEnvironment = z.infer<typeof MLOpsEnvironmentSchema>;
export type EnvType = z.infer<typeof EnvTypeSchema>;
export type Repository = z.infer<typeof RepositorySchema>;
export type BuildEnvironment = z.infer<typeof BuildEnvironmentSchema>;
export type DeployEnvironment = z.infer<typeof DeployEnvironmentSchema>;
