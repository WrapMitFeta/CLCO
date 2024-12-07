"""Project II: IaaS-Group-10"""

import pulumi
from pulumi_azure_native import (
    storage,
    resources,
    network,
    compute,
    insights,
)

from pulumi_azuread import get_user
import pulumi_azure_native.authorization as auth

subscription_id = "f0225753-f6de-42b8-b862-8c4003ccf2be"

# Create an Azure Resource Group
resource_group = resources.ResourceGroup(
    "resource_group",
    resource_group_name="IaaS_Group_10",
)

# Create a Storage Account
storage_account = storage.StorageAccount(
    "storage_account",
    account_name="metricstorageiaas",
    resource_group_name=resource_group.name,
    sku=storage.SkuArgs(
        name=storage.SkuName.STANDARD_LRS,
    ),
    kind=storage.Kind.STORAGE_V2,
)

# Create a VNet
vnet = network.VirtualNetwork(
    "v-net",
    resource_group_name=resource_group.name,
    virtual_network_name=pulumi.Output.concat(
        resource_group.name,
        "-vnet",
    ),
    address_space=network.AddressSpaceArgs(
        address_prefixes=["10.0.0.0/16"],
    ),
)

# Create a subnet within the VNet
subnet = network.Subnet(
    "subnet",
    resource_group_name=resource_group.name,
    virtual_network_name=vnet.name,
    subnet_name=pulumi.Output.concat(
        resource_group.name,
        "-subnet",
    ),
    address_prefix="10.0.1.0/24",
)

# Create a Network Security Group
network_security_group = network.NetworkSecurityGroup(
    "network-security-group",
    network_security_group_name=pulumi.Output.concat(
        resource_group.name,
        "-nsg",
    ),
    resource_group_name=resource_group.name,
)

# Create a Security Rule within the Network Security Group
security_rule = network.SecurityRule(
    "security-rule",
    name="allow-80-inbound",
    network_security_group_name=network_security_group.name.apply(
        lambda name: name,
    ),
    resource_group_name=resource_group.name,
    priority=110,
    source_address_prefix="*",
    source_port_range="*",
    destination_address_prefix="*",
    destination_port_range="80",
    access=network.SecurityRuleAccess.ALLOW,
    direction=network.SecurityRuleDirection.INBOUND,
    protocol=network.SecurityRuleProtocol.TCP,
)

# Create a Public IP Address
public_ip = network.PublicIPAddress(
    "public-ip",
    resource_group_name=resource_group.name,
    public_ip_address_name="public-ip",
    location=resource_group.location,
    sku=network.PublicIPAddressSkuArgs(
        name=network.PublicIPAddressSkuName.STANDARD,
    ),
    public_ip_allocation_method=network.IpAllocationMethod.STATIC,
)


def create_load_balancing_id(input: str):
    return pulumi.Output.concat(
        "/subscriptions/",
        subscription_id,
        "/resourceGroups/",
        resource_group.name,
        "/providers/Microsoft.Network/loadBalancers/load-balancer/",
        input,
    )


frontend_name = "frontend-ip"
backend_name = "backend-pool"
probe_name = "probe"

# Create a Load Balancer
load_balancer = network.LoadBalancer(
    "load-balancer",
    resource_group_name=resource_group.name,
    load_balancer_name="load-balancer",
    sku=network.LoadBalancerSkuArgs(
        name=network.LoadBalancerSkuName.STANDARD,
    ),
    frontend_ip_configurations=[
        network.FrontendIPConfigurationArgs(
            name=frontend_name,
            public_ip_address=network.PublicIPAddressArgs(
                id=public_ip.id,
            ),
        ),
    ],
    backend_address_pools=[
        network.BackendAddressPoolArgs(
            name=backend_name,
        )
    ],
    probes=[
        network.ProbeArgs(
            name=probe_name,
            protocol=network.ProbeProtocol.HTTP,
            port=80,
            request_path="/",
            interval_in_seconds=10,
            number_of_probes=2,
        ),
    ],
    load_balancing_rules=[
        network.LoadBalancingRuleArgs(
            name="load-balancing-rule",
            frontend_ip_configuration=network.SubResourceArgs(
                id=create_load_balancing_id(
                    input=f"frontendIPConfigurations/{frontend_name}",
                ),
            ),
            backend_address_pool=network.SubResourceArgs(
                id=create_load_balancing_id(
                    input=f"backendAddressPools/{backend_name}",
                ),
            ),
            probe=network.SubResourceArgs(
                id=create_load_balancing_id(
                    input=f"probes/{probe_name}",
                ),
            ),
            protocol=network.TransportProtocol.TCP,
            frontend_port=80,
            backend_port=80,
            idle_timeout_in_minutes=4,
            enable_floating_ip=False,
            load_distribution=network.LoadDistribution.DEFAULT,
        ),
    ],
)

# Create Network Interfaces
nics = []

for i in range(1, 3):
    nics.append(
        network.NetworkInterface(
            f"nic-{i}",
            resource_group_name=resource_group.name,
            network_interface_name=f"nic-{i}",
            ip_configurations=[
                network.NetworkInterfaceIPConfigurationArgs(
                    name=f"ipconfig-{i}",
                    subnet=network.SubnetArgs(id=subnet.id),
                    private_ip_allocation_method=network.IpAllocationMethod.DYNAMIC,
                    load_balancer_backend_address_pools=[
                        network.SubResourceArgs(
                            id=pulumi.Output.concat(
                                load_balancer.id,
                                "/backendAddressPools/backend-pool",
                            )
                        )
                    ],
                )
            ],
            network_security_group=network.NetworkSecurityGroupArgs(
                id=network_security_group.id,
            ),
        )
    )

# Create Storage Disks
disks = []

for i in range(1, 3):
    disks.append(
        compute.Disk(
            f"disk{i}",
            resource_group_name=resource_group.name,
            location=resource_group.location,
            sku=compute.DiskSkuArgs(
                name=compute.DiskStorageAccountTypes.PREMIUM_LRS,
            ),
            disk_size_gb=1024,
            creation_data=compute.CreationDataArgs(
                create_option=compute.DiskCreateOptionTypes.EMPTY,
            ),
        )
    )

# Create Virtual Machines
vms = []

for i in range(1, 3):
    vms.append(
        compute.VirtualMachine(
            f"vm-{i}",
            resource_group_name=resource_group.name,
            vm_name=f"vm-{i}",
            network_profile={
                "network_interfaces": [
                    {
                        "id": nics[i - 1].id,
                    }
                ],
            },
            # Enabled Boot Diagnostics
            diagnostics_profile=compute.DiagnosticsProfileArgs(
                boot_diagnostics=compute.BootDiagnosticsArgs(
                    enabled=True,
                    storage_uri=storage_account.primary_endpoints.apply(
                        lambda endpoints: endpoints.blob
                    ),
                ),
            ),
            hardware_profile=compute.HardwareProfileArgs(
                vm_size=compute.VirtualMachineSizeTypes.STANDARD_DS1_V2,
            ),
            storage_profile=compute.StorageProfileArgs(
                # Attach Data Disk
                data_disks=[
                    compute.DataDiskArgs(
                        lun=i,
                        create_option=compute.DiskCreateOptionTypes.ATTACH,
                        managed_disk=compute.ManagedDiskParametersArgs(
                            id=disks[i - 1].id.apply(
                                lambda unique_id: unique_id,
                            ),
                        ),
                    )
                ],
                image_reference=compute.ImageReferenceArgs(
                    publisher="Canonical",
                    offer="0001-com-ubuntu-server-jammy",
                    sku="22_04-lts",
                    version="latest",
                ),
            ),
            os_profile=compute.OSProfileArgs(
                computer_name=f"vm-{i}",
                admin_username="adminuser",
                admin_password="Password@secure1234!",
            ),
        )
    )

# Create Virtual Machine Extensions for Nginx
for i in range(1, 3):
    compute.VirtualMachineExtension(
        f"vm-extension-{i}",
        resource_group_name=resource_group.name,
        vm_name=vms[i - 1].name.apply(
            lambda name: name,
        ),
        vm_extension_name=f"vm-extension-{i}",
        publisher="Microsoft.Azure.Extensions",
        type="CustomScript",
        type_handler_version="2.1",
        auto_upgrade_minor_version=True,
        settings={
            "commandToExecute": f"sudo apt-get update && sudo apt-get install -y nginx && echo '<head><title>Web server {i}</title></head><body><h1>Web Portal</h1><p>Web server {i}</p></body>' > /var/www/html/index.html && sudo systemctl start nginx"
        },
    )


# Create Role Assignments for Team Members
team_member_1_email = "wi22b114@technikum-wien.at"
team_member_2_email = "wi22b075@technikum-wien.at"

team_member_1 = get_user(
    user_principal_name=team_member_1_email,
)
team_member_2 = get_user(
    user_principal_name=team_member_2_email,
)

owner_role_definition_id = pulumi.Output.concat(
    "/subscriptions/",
    subscription_id,
    "/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635",
)

# Create a Role Assignment for Team Member 1
role_assignment_1 = auth.RoleAssignment(
    "owner-role-assignment",
    principal_id=team_member_1.object_id,
    role_assignment_name="5d60b860-ae36-41c8-9b45-ae854864be30",  # any valid GUID
    principal_type=auth.PrincipalType.USER,
    role_definition_id=owner_role_definition_id,
    scope=resource_group.id,
)

# Create a Role Assignment for Team Member 2
role_assignment_2 = auth.RoleAssignment(
    "owner-role-assignment-2",
    principal_id=team_member_2.object_id,
    role_assignment_name="8fa84aa9-9f19-421b-b469-21bb684ec80b",  # any valid GUID
    principal_type=auth.PrincipalType.USER,
    role_definition_id=owner_role_definition_id,
    scope=resource_group.id,
)


# Create Action Group
action_group = insights.ActionGroup(
    "action-group",
    location="global",
    resource_group_name=resource_group.name,
    action_group_name=pulumi.Output.concat(
        resource_group.name,
        "-action-group",
    ),
    group_short_name="action-short",
    enabled=True,
    email_receivers=[
        insights.EmailReceiverArgs(
            name="Team Member 1",
            email_address=team_member_1_email,
        ),
        insights.EmailReceiverArgs(
            name="Team Member 2",
            email_address=team_member_2_email,
        ),
    ],
)

# Apply the alert to all VMs
alert_scopes = [vm.id.apply(lambda id: id) for vm in vms]

# Create CPU Metric Alert
cpu_metric_alert = insights.MetricAlert(
    "cpu-metric-alert",
    resource_group_name=resource_group.name,
    rule_name="high cpu alert",
    description="Alert when CPU usage exceeds 80 percent over a 5-minute period",
    severity=3,
    enabled=True,
    location="global",
    target_resource_region="westeurope",
    target_resource_type="Microsoft.Compute/virtualMachines",
    scopes=alert_scopes,
    criteria=insights.MetricAlertMultipleResourceMultipleMetricCriteriaArgs(
        odata_type="Microsoft.Azure.Monitor.MultipleResourceMultipleMetricCriteria",
        all_of=[
            insights.MetricCriteriaArgs(
                criterion_type="StaticThresholdCriterion",
                name="high cpu usage",
                metric_name="Percentage CPU",
                metric_namespace="Microsoft.Compute/virtualMachines",
                time_aggregation=insights.AggregationTypeEnum.AVERAGE,
                operator=insights.ConditionOperator.GREATER_THAN,
                threshold=80,
            )
        ],
    ),
    actions=[
        insights.MetricAlertActionArgs(
            action_group_id=action_group.id.apply(
                lambda id: id,
            ),
        )
    ],
    evaluation_frequency="PT1M",
    window_size="PT5M",
)

# Export the Public IP Address
pulumi.export(
    "public_ip",
    public_ip.ip_address,
)
