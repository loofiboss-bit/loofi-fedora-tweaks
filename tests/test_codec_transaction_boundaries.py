"""The multimedia workflow never changes GPU or kernel drivers."""
import unittest

from services.software.rpm_transaction_helper import validate_operations
from services.software.rpm_transactions import CODEC_PACKAGES


def package(name, action, version="1"):
    return {"name": name, "action": action, "nevra": f"{name}-0:{version}-1.x86_64", "repo_id": "fixture", "checksum": "a" * 64}


class CodecDriverBoundaryTests(unittest.TestCase):
    def test_driver_install_remove_and_paired_upgrade_are_rejected(self):
        for name in ("kernel", "kernel-core", "mesa", "mesa-va-drivers", "nvidia", "nvidia-driver", "xorg-x11-drv-nvidia", "akmod-nvidia", "kmod-nvidia"):
            for operations in ((package(name, "Install"),), (package(name, "Remove"),),
                               (package(name, "Replaced"), package(name, "Upgrade", "2"))):
                with self.subTest(name=name, operations=operations), self.assertRaises(ValueError):
                    validate_operations("codecs", CODEC_PACKAGES, operations, True)

    def test_regular_application_review_can_include_gpu_dependency_upgrade(self):
        validate_operations("install", ("fixture",), (package("mesa-libGL", "Replaced"), package("mesa-libGL", "Upgrade", "2")), False)

    def test_codec_library_upgrade_is_allowed(self):
        validate_operations("codecs", CODEC_PACKAGES, (package("libavcodec-freeworld", "Replaced"), package("libavcodec-freeworld", "Upgrade", "2")), False)
