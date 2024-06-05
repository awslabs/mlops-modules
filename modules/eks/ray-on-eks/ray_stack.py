# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
from typing import Any, cast, List

import yaml
from aws_cdk import Stack, Tags
from aws_cdk import aws_eks as eks
from aws_cdk.lambda_layer_kubectl_v29 import KubectlV29Layer
from constructs import Construct, IConstruct

_logger: logging.Logger = logging.getLogger(__name__)


class RayOnEKS(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        project_name: str,
        deployment_name: str,
        module_name: str,
        eks_cluster_name: str,
        eks_admin_role_arn: str,
        eks_openid_connect_provider_arn: str,
        eks_cluster_endpoint: str,
        eks_cert_auth_data: str,
        namespace_name: str,
        service_account_role,
        custom_manifest_paths: List[str],
        **kwargs: Any,
    ) -> None:
        self.project_name = project_name
        self.deployment_name = deployment_name
        self.module_name = module_name

        super().__init__(
            scope,
            id,
            **kwargs,
        )

        dep_mod = f"{project_name}-{deployment_name}-{module_name}"
        # used to tag AWS resources. Tag Value length can't exceed 256 characters
        full_dep_mod = dep_mod[:256] if len(dep_mod) > 256 else dep_mod
        Tags.of(scope=cast(IConstruct, self)).add(key="Deployment", value=full_dep_mod)

        provider = eks.OpenIdConnectProvider.from_open_id_connect_provider_arn(
            self, "OIDCProvider", eks_openid_connect_provider_arn
        )
        cluster = eks.Cluster.from_cluster_attributes(
            self,
            "EKSCluster",
            cluster_name=eks_cluster_name,
            open_id_connect_provider=provider,
            kubectl_role_arn=eks_admin_role_arn,
            kubectl_layer=KubectlV29Layer(self, "Kubectlv29Layer"),
        )

        cluster.add_helm_chart(
            "RayOperator",
            chart="kuberay-operator",
            release="kuberay-operator",
            repository="https://ray-project.github.io/kuberay-helm/",
            namespace=namespace_name,
            version="1.1.1",
            wait=True,
        )

        # Add optional custom resource (CR) manifests
        for custom_manifest_path in custom_manifest_paths:
            with open(custom_manifest_path) as f:
                for manifest in yaml.load_all(f, Loader=yaml.FullLoader):
                    cluster.add_manifest(f"{manifest['metadata']['name']}", manifest)
