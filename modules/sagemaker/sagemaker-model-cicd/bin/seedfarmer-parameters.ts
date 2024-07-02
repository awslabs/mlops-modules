import { fromError } from 'zod-validation-error';
import { MLOpsCodePipelinePropsSchema } from '../lib';

/**
 * Load SeedFarmer environment variables from cache for CodePipeline deployments initiated externally,
 * such as updates to model build or infrastructure repositories.
 * These variables are stored in the CodePipeline build project following the initial build by SeedFarmer.
 */
export function loadSeedFarmerEnvVars() {
  // check if this build is running from SeedFarmer codebuild project
  if (
    process.env.SEEDFARMER_PROJECT_NAME &&
    process.env.SEEDFARMER_DEPLOYMENT_NAME &&
    process.env.SEEDFARMER_MODULE_NAME
  ) {
    // nothing to do, environment variables are already set by SeedFarmer
    return;
  }

  // if here, this build is running from codepipeline build step
  console.log(
    'Missing SeedFarmer environment variables. Checking cached environments from prior build',
  );
  const cachedEnv = process.env.CACHED_SEEDFARMER_ENV;
  if (!cachedEnv || cachedEnv === '{}') {
    // if here, running `cdk synth` directly instead of `seedfarmer apply`
    throw new Error('Missing SeedFarmer module parameters');
  }
  const seedFarmerEnv = JSON.parse(cachedEnv);
  process.env = { ...process.env, ...seedFarmerEnv };
}

export function getSeedFarmerParamter(name: string) {
  const envVar = `SEEDFARMER_PARAMETER_${name}`;
  const value = process.env[envVar];
  if (!value) {
    throw new Error(`Missing SeedFarmer parmeter: ${name}`);
  }
  try {
    return JSON.parse(value);
  } catch (e) {
    return value;
  }
}

export function getModuleInfo() {
  const sfProjectName = process.env.SEEDFARMER_PROJECT_NAME!;
  const sfDeploymentName = process.env.SEEDFARMER_DEPLOYMENT_NAME!;
  const sfModuleName = process.env.SEEDFARMER_MODULE_NAME!;
  return { sfProjectName, sfDeploymentName, sfModuleName };
}

export function getModuleParameters() {
  const { sfProjectName, sfDeploymentName, sfModuleName } = getModuleInfo();
  const mlopsProjectName = `${sfProjectName}-${sfDeploymentName}-${sfModuleName}`;
  const infraRepo = getSeedFarmerParamter('INFRA_REPO');
  const modelBuildRepo = getSeedFarmerParamter('MODEL_BUILD_REPO');
  const deploymentGroups = getSeedFarmerParamter('DEPLOYMENT_GROUPS');

  // validate parameters
  try {
    return MLOpsCodePipelinePropsSchema.parse({
      projectName: mlopsProjectName,
      infraRepo,
      modelBuildRepo,
      deploymentGroups,
    });
  } catch (err) {
    const validationError = fromError(err, {
      prefix: 'Invalid SeedFarmer module parameters',
    });
    throw validationError;
  }
}
