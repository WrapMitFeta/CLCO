import pulumi
import pulumi_azure_native as azure_native

config = pulumi.Config()
azure_native_location = config.get("azure-native:location")

resource_group = azure_native.resources.ResourceGroup(
    "resourceGroup",
    location=azure_native_location,
)

budget_name = "MonthlyBudget"
budget_amount = 10

budget = azure_native.consumption.Budget(
    resource_name=budget_name,
    scope="/subscriptions/f0225753-f6de-42b8-b862-8c4003ccf2be",
    amount=budget_amount,
    category=azure_native.consumption.CategoryType.COST,
    time_grain=azure_native.consumption.TimeGrainType.MONTHLY,
    time_period=azure_native.consumption.BudgetTimePeriodArgs(
        start_date="2024-11-01",
        end_date="2024-12-30",
    ),
    notifications={
        azure_native.consumption.ThresholdType.ACTUAL: azure_native.consumption.NotificationArgs(
            enabled=True,
            operator=azure_native.consumption.OperatorType.GREATER_THAN,
            threshold=50,
            contact_emails=["wi22b114@technikum-wien.at"],
        ),
        azure_native.consumption.ThresholdType.FORECASTED: azure_native.consumption.NotificationArgs(
            enabled=True,
            operator=azure_native.consumption.OperatorType.GREATER_THAN,
            threshold=50,
            contact_emails=["wi22b114@technikum-wien.at"],
        ),
    },
)

pulumi.export("budget_name", budget.name)
pulumi.export("budget_scope", budget.scope)
