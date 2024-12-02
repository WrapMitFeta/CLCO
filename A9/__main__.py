"""An Azure RM Python Pulumi program"""

from pulumi_azure_native import resources
from pulumi_azure_native import network
from pulumi_azure_native import compute

import pulumi

resource_group = resources.ResourceGroup(
    "resource-group",
    resource_group_name="resource-group-a9",
    location="westeurope",
)

vnet = network.VirtualNetwork(
    "v-net",
    resource_group_name=resource_group.name.apply(
        lambda name: name,
    ),
    virtual_network_name=pulumi.Output.concat(
        resource_group.name,
        "-vnet",
    ),
    address_space=network.AddressSpaceArgs(
        address_prefixes=["10.0.0.0/16"],
    ),
)

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

network_security_group = network.NetworkSecurityGroup(
    "network-security-group",
    network_security_group_name=pulumi.Output.concat(
        resource_group.name,
        "-nsg",
    ),
    resource_group_name=resource_group.name,
    location=resource_group.location,
)

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
                )
            ],
            network_security_group=network.NetworkSecurityGroupArgs(
                id=network_security_group.id,
            ),
        )
    )

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
            hardware_profile=compute.HardwareProfileArgs(
                vm_size=compute.VirtualMachineSizeTypes.STANDARD_DS1_V2,
            ),
            storage_profile=compute.StorageProfileArgs(
                image_reference=compute.ImageReferenceArgs(
                    publisher="Canonical",
                    offer="0001-com-ubuntu-server-jammy",
                    sku="22_04-lts",
                    version="latest",
                ),
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
            ),
            os_profile=compute.OSProfileArgs(
                computer_name=f"vm-{i}",
                admin_username="adminuser",
                admin_password="Password@secure1234!",
            ),
        )
    )

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


pulumi.export("disk 1", disks[0].unique_id)
pulumi.export("disk 2", disks[1].unique_id)
