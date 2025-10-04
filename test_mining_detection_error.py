#!/usr/bin/env python3
"""
Test that mining detection errors are clear and informative
"""

import asyncio
from unittest.mock import Mock, AsyncMock, patch
import sys

sys.path.insert(0, ".")

from mcp_server import SandboxManager


async def test_mining_detection_error_message():
    """Test that mining detection produces a clear error message"""
    print("=" * 70)
    print("Testing Mining Detection Error Messages")
    print("=" * 70)
    print()

    # Mock a container that was killed for mining
    mock_container = Mock()
    mock_container.attrs = {"State": {"ExitCode": 137, "Error": "", "OOMKilled": False}}
    mock_container.logs = Mock(return_value=b"mining simulation running...")

    # Mock monitor that reports mining detection
    mock_monitor = Mock()
    mock_monitor.get_crash_by_container = Mock(
        return_value={
            "crash_reason": "Container terminated for suspected mining activity",
            "exit_code": 137,
            "oom_killed": False,
        }
    )

    # Patch the monitor
    with patch("mcp_server.MONITORING_ENABLED", True):
        with patch("mcp_server.get_monitor", return_value=mock_monitor):
            result = await SandboxManager._handle_container_crash(
                mock_container,
                "test123",
                "# mining code\nimport hashlib\nwhile True:\n    hashlib.sha256(b'test').hexdigest()",
            )

    # Check the result
    print("✅ Crash handled")
    print()
    print("Result status:", result.get("status"))
    print()
    print("Error message:")
    print("-" * 70)
    error_content = result["results"][0]["content"]
    print(error_content)
    print("-" * 70)
    print()

    # Verify key elements
    checks = [
        (
            "⛏️  CONTAINER TERMINATED - MINING ACTIVITY DETECTED" in error_content,
            "Mining detection header",
        ),
        (
            "monitoring system detected" in error_content.lower(),
            "Mentions monitoring system",
        ),
        ("Mining Activity Indicators" in error_content, "Shows indicators"),
        (
            "security feature" in error_content.lower(),
            "Explains it's a security feature",
        ),
        (result["crash_info"]["mining_detected"] == True, "Sets mining_detected flag"),
    ]

    print("Verification checks:")
    all_passed = True
    for passed, description in checks:
        status = "✅" if passed else "❌"
        print(f"  {status} {description}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("🎉 All checks passed! Mining detection error is clear and informative.")
        return True
    else:
        print("❌ Some checks failed!")
        return False


async def test_regular_crash_error_message():
    """Test that regular crashes still have clear messages"""
    print()
    print("=" * 70)
    print("Testing Regular Crash Error Messages")
    print("=" * 70)
    print()

    # Mock a container that crashed due to OOM
    mock_container = Mock()
    mock_container.attrs = {"State": {"ExitCode": 137, "Error": "", "OOMKilled": True}}
    mock_container.logs = Mock(return_value=b"MemoryError: Out of memory")

    # Mock monitor that reports OOM (not mining)
    mock_monitor = Mock()
    mock_monitor.get_crash_by_container = Mock(
        return_value={
            "crash_reason": "Out of memory",
            "exit_code": 137,
            "oom_killed": True,
        }
    )

    # Patch the monitor
    with patch("mcp_server.MONITORING_ENABLED", True):
        with patch("mcp_server.get_monitor", return_value=mock_monitor):
            result = await SandboxManager._handle_container_crash(
                mock_container,
                "test456",
                "# memory intensive code\ndata = [0] * (10**9)",
            )

    print("✅ Crash handled")
    print()
    print("Result status:", result.get("status"))
    print()
    print("Error message (first 500 chars):")
    print("-" * 70)
    error_content = result["results"][0]["content"]
    print(error_content[:500])
    print("...")
    print("-" * 70)
    print()

    # Verify it's NOT a mining detection
    checks = [
        (
            "🔥 CONTAINER CRASHED DURING EXECUTION" in error_content,
            "Regular crash header",
        ),
        ("OUT_OF_MEMORY" in error_content, "Shows OOM reason"),
        (
            result["crash_info"]["mining_detected"] == False,
            "mining_detected flag is False",
        ),
        ("⛏️" not in error_content, "No mining emoji"),
    ]

    print("Verification checks:")
    all_passed = True
    for passed, description in checks:
        status = "✅" if passed else "❌"
        print(f"  {status} {description}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("🎉 All checks passed! Regular crash error is clear.")
        return True
    else:
        print("❌ Some checks failed!")
        return False


async def main():
    """Run all tests"""
    results = []

    try:
        results.append(await test_mining_detection_error_message())
        results.append(await test_regular_crash_error_message())
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback

        traceback.print_exc()
        return False

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if all(results):
        print("✅ ALL TESTS PASSED!")
        print()
        print("The error messages are now clear and informative:")
        print("  • Mining detection shows specific warning")
        print("  • Regular crashes show appropriate troubleshooting")
        print("  • Both include full context and logs")
        return True
    else:
        print("❌ SOME TESTS FAILED")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
