# AIOps Modules

AIOps modules is a collection of reusable Infrastructure as Code (IAC) modules that works with [SeedFarmer CLI](https://github.com/awslabs/seed-farmer). Please see the [DOCS](https://seed-farmer.readthedocs.io/en/latest/) for all things seed-farmer.

The modules in this repository are decoupled from each other and can be aggregated together using GitOps (manifest file) principles provided by `seedfarmer` and achieve the desired use cases. It removes the undifferentiated heavy lifting for an end user by providing hardended modules and enables them to focus on building business on top of them.

## General Information

The modules in this repository are / must be generic for reuse without affiliation to any one particular project in Machine Learning and Foundation Model Operations domain.

All modules in this repository adhere to the module structure defined in the the [SeedFarmer Guide](https://seed-farmer.readthedocs.io/en/latest)

- [Project Structure](https://seed-farmer.readthedocs.io/en/latest/project_development.html)
- [Module Development](https://seed-farmer.readthedocs.io/en/latest/module_development.html)
- [Module Manifest Guide](https://seed-farmer.readthedocs.io/en/latest/manifests.html)
- [Seed-Farmer Workshop](https://catalog.us-east-1.prod.workshops.aws/workshops/dfd2f6b2-3923-4d79-80bd-7db6c4842122/en-US)

## Deployment

See deployment steps in the [Deployment Guide](DEPLOYMENT.md).

## Modules

### SageMaker Modules

| Type                                                                                                                      | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
|---------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [SageMaker Studio Module](modules/sagemaker/sagemaker-studio/README.md)                                                   | Provisions secure SageMaker Studio Domain environment, creates example User Profiles for Data Scientist and Lead Data Scientist linked to IAM Roles, and adds lifecycle config                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| [SageMaker Endpoint Module](modules/sagemaker/sagemaker-endpoint/README.md)                                               | Creates SageMaker real-time inference endpoint for the specified model package or latest approved model from the model package group                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| [SageMaker Project Templates via Service Catalog Module](modules/sagemaker/sagemaker-templates-service-catalog/README.md) | Provisions SageMaker Project Templates for an organization. The templates are available using SageMaker Studio Classic or Service Catalog. Available templates:<br/> - [Train a model on Abalone dataset using XGBoost](modules/sagemaker/sagemaker-templates-service-catalog/README.md#train-a-model-on-abalone-dataset-with-xgboost-template)<br/>- [Perform batch inference](modules/sagemaker/sagemaker-templates-service-catalog/README.md#batch-inference-template)<br/>- [Multi-account model deployment](modules/sagemaker/sagemaker-templates-service-catalog/README.md#multi-account-model-deployment-template) <br/>- [HuggingFace model import template](modules/sagemaker/sagemaker-templates-service-catalog/README.md#huggingface-model-import-template) |
| [SageMaker Notebook Instance Module](modules/sagemaker/sagemaker-notebook/README.md)                                      | Creates secure SageMaker Notebook Instance for the Data Scientist, clones the source code to the workspace                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| [SageMaker Custom Kernel Module](modules/sagemaker/sagemaker-custom-kernel/README.md)                                     | Builds custom kernel for SageMaker Studio from a Dockerfile                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| [SageMaker Model Package Group Module](modules/sagemaker/sagemaker-model-package-group/README.md)                         | Creates a SageMaker Model Package Group to register and version SageMaker Machine Learning (ML) models and setups an Amazon EventBridge Rule to send model package group state change events to an Amazon EventBridge Bus                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| [SageMaker Model Package Promote Pipeline Module](modules/sagemaker/sagemaker-model-package-promote-pipeline/README.md)   | Deploy a Pipeline to promote SageMaker Model Packages in a multi-account setup. The pipeline can be triggered through an EventBridge rule in reaction of a SageMaker Model Package Group state event change (Approved/Rejected). Once the pipeline is triggered, it will promote the latest approved model package, if one is found.                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| [SageMaker Model Monitoring Module](modules/sagemaker/sagemaker-model-monitoring/README.md)                        | Deploy data quality, model quality, model bias, and model explainability monitoring jobs which run against a SageMaker Endpoint.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| [SageMaker Model CICD Module](modules/sagemaker/sagemaker-model-cicd/README.md) | Creates a comprehensive CICD pipeline using AWS CodePipelines to build and deploy a ML model on SageMaker.|

### Mlflow Modules

| Type                                                                    | Description                                                                                                                                                                                       |
|-------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [Mlflow Image Module](modules/mlflow/mlflow-image/README.md)            | Creates Mlflow Docker container image and pushes the image to Elastic Container Registry                                                                                                          |
| [Mlflow on AWS Fargate Module](modules/mlflow/mlflow-fargate/README.md) | Runs Mlflow container on AWS Fargate in a load-balanced Elastic Container Service. Supports Elastic File System and Relational Database Store for metadata persistence, and S3 for artifact store |

### FMOps/LLMOps Modules

| Type                                                                                                               | Description                                                                                                                            |
|--------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------|
| [SageMaker JumpStart Foundation Model Endpoint Module](modules/fmops/sagemaker-jumpstart-fm-endpoint/README.md)    | Creates an endpoint for a SageMaker JumpStart Foundation Model.                                                                        |
| [SageMaker Hugging Face Foundation Model Endpoint Module](modules/fmops/sagemaker-hugging-face-endpoint/README.md) | Creates an endpoint for a SageMaker Hugging Face Foundation Model.                                                                     |
| [Amazon Bedrock Finetuning Module](modules/fmops/bedrock-finetuning/README.md)                                     | Creates a pipeline that automatically triggers Amazon Bedrock Finetuning.                                                              |
| [AppSync Knowledge Base Ingestion and Question and Answering RAG Module](modules/fmops/qna-rag/README.md)          | Creates an Graphql endpoint for ingestion of data and and use ingested as knowledge base for a Question and Answering model using RAG. |

### MWAA Modules

| Type                                                                    | Description                                                                              |
|-------------------------------------------------------------------------|------------------------------------------------------------------------------------------|
| [Example DAG for MLOps Module](modules/examples/airflow-dags/README.md) |  Deploys a Sample DAG in MWAA demonstrating MLOPs and it is using MWAA module from IDF   |


### EKS Modules

| Type                                                  | Description                                                                                                      |
|-------------------------------------------------------|------------------------------------------------------------------------------------------------------------------|
| [Ray on EKS Module](modules/eks/ray-on-eks/README.md) | Provisions Ray on EKS cluster using IDF EKS module, Ray Operator, and RayJob or RayCluster via Custom Resources. |

### Example Modules

| Type                                                      | Description                                                                         |
|-----------------------------------------------------------|-------------------------------------------------------------------------------------|
| [Event Bus Module](modules/examples/event-bus/README.md)  | Creates an Amazon EventBridge Bus for cross-account events.                         |
| [Personas Module](modules/examples/personas/README.md)    | This module is an example that creates various roles required for an AI/ML project. |


### Industry Data Framework (IDF) Modules

The modules in this repository are compatible with [Industry Data Framework (IDF) Modules](https://github.com/awslabs/idf-modules) and can be used together within the same deployment. Refer to `examples/manifests` for examples.

### Autonomous Driving Data Framework (ADDF) Modules

The modules in this repository are compatible with [Autonomous Driving Data Framework (ADDF) Modules](https://github.com/awslabs/autonomous-driving-data-framework) and can be used together within the same deployment.
