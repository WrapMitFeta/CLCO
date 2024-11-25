import pulumi
import unittest


class MyMocks(pulumi.runtime.Mocks):
    def new_resource(self, args: pulumi.runtime.MockResourceArgs):
        return [args.name + "_id", args.inputs]

    def call(self, args: pulumi.runtime.MockCallArgs):
        return {}


pulumi.runtime.set_mocks(
    MyMocks(),
    preview=False,  # Sets the flag `dry_run`, which is true at runtime during a preview.
)

from resources.resources import blob_container  # noqa: E402


class TestIntegration(unittest.TestCase):
    @pulumi.runtime.test
    def test_public_access(self):
        def check_tags(args):
            public_access = args[0]
            self.assertEqual(public_access, "Blob")

        return pulumi.Output.all(blob_container.public_access).apply(check_tags)
