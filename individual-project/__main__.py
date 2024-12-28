import base64
import pulumi
from pulumi_azure_native import (
    resources,
    network,
    containerservice,
    containerregistry,
    managedidentity,
    authorization,
    operationalinsights,
)
import pulumi_kubernetes as k8s
import pulumi_tls as tls

# Project Configuration
config = pulumi.Config()
k8s_version = config.get("k8sVersion", " 1.30.6")
node_count = config.get_int("nodeCount", 2)
node_size = config.get("nodeSize", "Standard_D2s_v3")
admin_user = config.get("adminUser", "aksadmin")
ingress_namespace_config = config.get("ingressNamespace", "ingress-nginx")
app_namespace_config = config.get("appNamespace", "linkstack")
regions = config.require_object("regions")

tm_resource_group = resources.ResourceGroup(
    "tm-resource-group",
    resource_group_name="global-tm-rg",
    location="northeurope",
)

tm_profile = network.Profile(
    "tm-profile",
    resource_group_name=tm_resource_group.name,
    traffic_routing_method=network.TrafficRoutingMethod.WEIGHTED,  # Options: Performance, Priority, Weighted, etc.
    dns_config=network.DnsConfigArgs(
        relative_name="linkstack",  # DNS name, resulting in linkstack.trafficmanager.net
        ttl=30,  # DNS Time-to-Live
    ),
    monitor_config=network.MonitorConfigArgs(
        protocol="HTTP",  # Health probe protocol
        port=80,  # Health probe port
        path="/",  # Health probe path
    ),
    location="global",
    profile_status=network.ProfileStatus.ENABLED,
)


def deploy_in_region(region, index):
    app_namespace = f"{app_namespace_config}-{index}"
    ingress_namespace = f"{ingress_namespace_config}-{index}"
    # Create Azure Resource Group
    resource_group = resources.ResourceGroup(
        f"resource_group_{index}",
        resource_group_name=f"group-10-{index}",
        location=region,
    )

    log_analytics_workspace = operationalinsights.Workspace(
        f"logAnalyticsWorkspace-{index}",
        resource_group_name=resource_group.name,
        location=resource_group.location,
        sku=operationalinsights.WorkspaceSkuArgs(
            name=operationalinsights.WorkspaceSkuNameEnum.PER_GB2018,
        ),
        retention_in_days=30,
    )

    # Create Azure Virtual Network
    v_net = network.VirtualNetwork(
        f"v_net-{index}",
        address_space=network.AddressSpaceArgs(
            address_prefixes=["10.0.0.0/8"],
        ),
        resource_group_name=resource_group.name,
        location=resource_group.location,
    )

    # Create Azure Subnet for Nodes
    node_subnet = network.Subnet(
        f"node_subnet-{index}",
        address_prefix="10.240.0.0/16",
        resource_group_name=resource_group.name,
        virtual_network_name=v_net.name,
        subnet_name="node_subnet",
    )

    # Create Azure Subnet for Pods
    pod_subnet = network.Subnet(
        f"pod_subnet-{index}",
        address_prefix="10.241.0.0/16",
        resource_group_name=resource_group.name,
        delegations=[
            network.DelegationArgs(
                name="aksDelegation",
                service_name="Microsoft.ContainerService/managedClusters",
            )
        ],
        subnet_name="pod_subnet",
        virtual_network_name=v_net.name,
    )

    # Create Azure Container Registry
    container_registry = containerregistry.Registry(
        f"containerRegistry{index}",
        resource_group_name=resource_group.name,
        sku=containerregistry.SkuArgs(
            name=containerregistry.SkuName.STANDARD,
        ),
        admin_user_enabled=True,
        location=resource_group.location,
    )

    # Create Azure Kubernetes Service
    private_key = tls.PrivateKey(
        f"privateKey-{index}",
        algorithm="RSA",
        rsa_bits=4096,
    )

    # Create Azure Managed Identity
    identity = managedidentity.UserAssignedIdentity(
        f"identity-{index}",
        resource_group_name=resource_group.name,
        location=resource_group.location,
    )

    # Create Azure Kubernetes Service
    managed_cluster = containerservice.ManagedCluster(
        f"cluster-{index}",
        resource_group_name=resource_group.name,
        location=resource_group.location,
        identity=containerservice.ManagedClusterIdentityArgs(
            type=containerservice.ResourceIdentityType.USER_ASSIGNED,
            user_assigned_identities=[identity.id],
        ),
        agent_pool_profiles=[
            containerservice.ManagedClusterAgentPoolProfileArgs(
                name="agentpool",
                count=node_count,
                max_pods=110,
                mode=containerservice.AgentPoolMode.SYSTEM,
                os_disk_size_gb=30,
                os_type=containerservice.OSType.LINUX,
                type=containerservice.AgentPoolType.VIRTUAL_MACHINE_SCALE_SETS,
                vm_size=node_size,
                vnet_subnet_id=node_subnet.id,
                pod_subnet_id=pod_subnet.id,
            )
        ],
        dns_prefix=resource_group.name,
        enable_rbac=True,
        kubernetes_version=k8s_version,
        linux_profile=containerservice.ContainerServiceLinuxProfileArgs(
            admin_username=admin_user,
            ssh=containerservice.ContainerServiceSshConfigurationArgs(
                public_keys=[
                    containerservice.ContainerServiceSshPublicKeyArgs(
                        key_data=private_key.public_key_openssh,
                    ),
                ],
            ),
        ),
        network_profile=containerservice.ContainerServiceNetworkProfileArgs(
            network_plugin=containerservice.NetworkPlugin.AZURE,
        ),
        addon_profiles={
            "omsagent": containerservice.ManagedClusterAddonProfileArgs(
                enabled=True,  # Enable monitoring
                config={
                    "logAnalyticsWorkspaceResourceID": log_analytics_workspace.id
                },
            )
        },
    )

    # Create Azure Role Assignment for Container Registry
    authorization.RoleAssignment(
        f"acrPullRoleAssignment-{index}",
        principal_id=identity.principal_id,
        principal_type="ServicePrincipal",
        role_definition_id=authorization.get_role_definition_output(
            role_definition_id="7f951dda-4ed3-4680-a7ca-43fe172d538d",
            scope=container_registry.id,
        ).apply(lambda x: x.id),
        scope=container_registry.id,
    )

    # Create Azure User Credentials for Kubernetes
    user_cred = containerservice.list_managed_cluster_user_credentials_output(
        resource_group_name=resource_group.name,
        resource_name=managed_cluster.name,
    )

    # Create Azure Kubernetes Provider
    user_kubeconfig = user_cred.kubeconfigs[0].value.apply(
        lambda enc: base64.b64decode(enc).decode()
    )

    k8s_provider = k8s.Provider(
        f"k8s_provider-{index}",
        kubeconfig=user_kubeconfig,
    )

    # Create Azure Kubernetes Namespace for Application
    app_namespace_obj = k8s.core.v1.Namespace(
        f"namespace-{index}",
        metadata=k8s.meta.v1.ObjectMetaArgs(name=app_namespace),
        opts=pulumi.ResourceOptions(
            provider=k8s_provider, depends_on=k8s_provider
        ),
    )

    # Create Azure Kubernetes Namespace for Ingress
    k8s.core.v1.Namespace(
        f"namespace-ingress-{index}",
        metadata=k8s.meta.v1.ObjectMetaArgs(name=ingress_namespace),
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=k8s_provider,
        ),
    )

    pvc = k8s.core.v1.PersistentVolumeClaim(
        f"pvc-{index}",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name="linkstack-pvc",
            namespace=app_namespace,
        ),
        spec=k8s.core.v1.PersistentVolumeClaimSpecArgs(
            access_modes=["ReadWriteOnce"],
            resources=k8s.core.v1.VolumeResourceRequirementsArgs(
                requests={"storage": "100Mi"},
            ),
        ),
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=app_namespace_obj,
        ),
    )

    # Create Azure Kubernetes Ingress Controller
    nginx_ingress_controller = k8s.helm.v4.Chart(
        f"nginx-ingress-controller-{index}",
        args=k8s.helm.v4.ChartArgs(
            chart="nginx-ingress-controller",
            namespace=ingress_namespace,
            version="11.4.1",
            repository_opts=k8s.helm.v4.RepositoryOptsArgs(
                repo="https://charts.bitnami.com/bitnami"
            ),
            values={
                "controller": {"service": {"type": "LoadBalancer"}},
                "resources": {
                    "limits": {"cpu": "500m", "memory": "512Mi"},
                    "requests": {"cpu": "250m", "memory": "256Mi"},
                },
            },
        ),
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
        ),
    )

    # Create Azure Kubernetes Deployment for Application
    name = "linkstack"
    linkstack_deployment = k8s.apps.v1.Deployment(
        f"linkstack-deployment-{index}",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name=name,
            namespace=app_namespace,
            labels={"app": name},
        ),
        spec=k8s.apps.v1.DeploymentSpecArgs(
            replicas=1,
            selector=k8s.meta.v1.LabelSelectorArgs(match_labels={"app": name}),
            template=k8s.core.v1.PodTemplateSpecArgs(
                metadata=k8s.meta.v1.ObjectMetaArgs(labels={"app": name}),
                spec=k8s.core.v1.PodSpecArgs(
                    containers=[
                        k8s.core.v1.ContainerArgs(
                            name=name,
                            image="linkstackorg/linkstack:latest",
                            env=[
                                k8s.core.v1.EnvVarArgs(
                                    name="HTTP_SERVER_NAME",
                                    value="linkstack.local",
                                ),
                                k8s.core.v1.EnvVarArgs(
                                    name="SESSION_SECURE_COOKIE",
                                    value="false",
                                ),
                                k8s.core.v1.EnvVarArgs(
                                    name="HTTPS_SERVER_NAME",
                                    value="linkstack.local",
                                ),
                                k8s.core.v1.EnvVarArgs(
                                    name="SERVER_ADMIN",
                                    value="wi22b114@technikum-wien.at",
                                ),
                                k8s.core.v1.EnvVarArgs(
                                    name="TZ",
                                    value="Europe/Vienna",
                                ),
                            ],
                            resources=k8s.core.v1.ResourceRequirementsArgs(
                                requests={
                                    "cpu": "50m",
                                    "memory": "20Mi",
                                },
                            ),
                            ports=[
                                k8s.core.v1.ContainerPortArgs(
                                    container_port=80,
                                )
                            ],
                            liveness_probe=k8s.core.v1.ProbeArgs(
                                http_get=k8s.core.v1.HTTPGetActionArgs(
                                    path="/",
                                    port=80,
                                ),
                                initial_delay_seconds=30,
                                period_seconds=10,
                                timeout_seconds=5,
                                failure_threshold=3,
                            ),
                            readiness_probe=k8s.core.v1.ProbeArgs(
                                http_get=k8s.core.v1.HTTPGetActionArgs(
                                    path="/",
                                    port=80,
                                ),
                                initial_delay_seconds=15,
                                period_seconds=5,
                                timeout_seconds=3,
                                failure_threshold=3,
                            ),
                            volume_mounts=[
                                k8s.core.v1.VolumeMountArgs(
                                    name=f"linkstack-storage-{index}",
                                    mount_path="/database",
                                )
                            ],
                        )
                    ],
                    volumes=[
                        k8s.core.v1.VolumeArgs(
                            name=f"linkstack-storage-{index}",
                            persistent_volume_claim=k8s.core.v1.PersistentVolumeClaimVolumeSourceArgs(
                                claim_name=pvc.metadata.name,
                            ),
                        )
                    ],
                ),
            ),
        ),
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=[
                pvc,
                app_namespace_obj,
            ],  # Add explicit dependency
        ),
    )

    # Add Horizontal Pod Autoscaler (HPA) for Deployment
    hpa = k8s.autoscaling.v2.HorizontalPodAutoscaler(
        f"hpa-{index}",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name=f"linkstack-hpa-{index}",
            namespace=app_namespace,
        ),
        spec=k8s.autoscaling.v2.HorizontalPodAutoscalerSpecArgs(
            scale_target_ref=k8s.autoscaling.v2.CrossVersionObjectReferenceArgs(
                api_version="apps/v1",
                kind="Deployment",
                name=linkstack_deployment.metadata.name,
            ),
            min_replicas=1,
            max_replicas=3,
            metrics=[
                k8s.autoscaling.v2.MetricSpecArgs(
                    type="Resource",
                    resource=k8s.autoscaling.v2.ResourceMetricSourceArgs(
                        name="cpu",
                        target=k8s.autoscaling.v2.MetricTargetArgs(
                            type="Utilization",
                            average_utilization=50,
                        ),
                    ),
                ),
            ],
        ),
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=[linkstack_deployment],
        ),
    )

    # Create Azure Kubernetes Service for Application
    linkstack_service = k8s.core.v1.Service(
        f"linkstack-service-{index}",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name=name,
            namespace=app_namespace,
            labels={"app": name},
        ),
        spec=k8s.core.v1.ServiceSpecArgs(
            type=k8s.core.v1.ServiceSpecType.CLUSTER_IP,
            selector={
                "app": name,
            },
            ports=[
                k8s.core.v1.ServicePortArgs(
                    port=80,
                    target_port=80,
                ),
            ],
        ),
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=[linkstack_deployment],
        ),
    )

    # Create Azure Kubernetes Ingress for Application
    linkstack_ingress = k8s.networking.v1.Ingress(
        f"linkstack-ingress-{index}",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            namespace=app_namespace,
            name="linkstack-ingress",
            annotations={
                "kubernetes.io/ingress.class": "nginx",
                "nginx.ingress.kubernetes.io/proxy-body-size": "10m",
                "nginx.ingress.kubernetes.io/proxy-buffer-size": "64k",
                "nginx.ingress.kubernetes.io/proxy-read-timeout": "600",
                "nginx.ingress.kubernetes.io/proxy-send-timeout": "600",
                "nginx.ingress.kubernetes.io/affinity": "cookie",
                "nginx.ingress.kubernetes.io/session-cookie-name": "linkstack_session",
                "nginx.ingress.kubernetes.io/session-cookie-path": "/",
                "nginx.ingress.kubernetes.io/session-cookie-samesite": "Lax",
                "nginx.ingress.kubernetes.io/session-cookie-hash": "sha1",
            },
        ),
        spec=k8s.networking.v1.IngressSpecArgs(
            rules=[
                k8s.networking.v1.IngressRuleArgs(
                    http=k8s.networking.v1.HTTPIngressRuleValueArgs(
                        paths=[
                            k8s.networking.v1.HTTPIngressPathArgs(
                                path="/",
                                path_type="Prefix",
                                backend=k8s.networking.v1.IngressBackendArgs(
                                    service=k8s.networking.v1.IngressServiceBackendArgs(
                                        name=name,
                                        port=k8s.networking.v1.ServiceBackendPortArgs(
                                            number=80
                                        ),
                                    )
                                ),
                            )
                        ]
                    ),
                )
            ],
        ),
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=[linkstack_service],
        ),
    )

    # Get the LoadBalancer Service for the NGINX Ingress Controller
    return k8s.core.v1.Service.get(
        f"nginxIngressControllerService-{index}",
        f"{ingress_namespace}/nginx-ingress-controller-{index}",
        opts=pulumi.ResourceOptions(
            provider=k8s_provider,
            depends_on=nginx_ingress_controller,
        ),
    )


for index, region in enumerate(regions):
    nginx_service = deploy_in_region(region, index)

    endpoint = network.Endpoint(
        f"tm-endpoint-{index}",
        always_serve=network.AlwaysServe.ENABLED,
        resource_group_name=tm_resource_group.name,
        profile_name=tm_profile.name,
        endpoint_type="ExternalEndpoints",
        type="Microsoft.network/TrafficManagerProfiles/ExternalEndpoints",
        endpoint_status=network.EndpointStatus.ENABLED,
        endpoint_location=region,
        target=nginx_service.status.load_balancer.ingress[0].ip.apply(
            lambda ip: ip
        ),
    )

    pulumi.export(
        f"ingress_ip_{region}",
        nginx_service.status.load_balancer.ingress[0].ip,
    )
