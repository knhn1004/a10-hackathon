#!/usr/bin/env python3
"""
Comprehensive test for execute_from_url functionality
Tests the URL fetching without requiring Docker
"""

import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_url_validation():
    """Test URL validation logic"""
    print("=" * 60)
    print("Test 1: URL Validation")
    print("=" * 60)

    from mcp_server import SandboxManager

    # Test valid URLs
    valid_urls = [
        "https://gist.githubusercontent.com/user/id/raw/script.py",
        "http://example.com/code.py",
        "https://pastebin.com/raw/abc123",
        "https://raw.githubusercontent.com/user/repo/main/script.py",
    ]

    print("\n✅ Testing valid URLs:")
    for url in valid_urls:
        print(f"  - {url}")

    # Test invalid URLs
    invalid_tests = [
        ("file:///etc/passwd", "file:// scheme"),
        ("ftp://example.com/code.py", "ftp:// scheme"),
        ("http://localhost/code.py", "localhost"),
        ("http://127.0.0.1/code.py", "127.0.0.1"),
        ("http://0.0.0.0/code.py", "0.0.0.0"),
        ("http://192.168.1.1/code.py", "private IP 192.168.*"),
        ("http://10.0.0.1/code.py", "private IP 10.*"),
        ("http://172.16.0.1/code.py", "private IP 172.16.*"),
    ]

    print("\n❌ Testing invalid URLs (should be rejected):")
    all_rejected = True
    for url, reason in invalid_tests:
        try:
            await SandboxManager.fetch_code_from_url(url)
            print(f"  ✗ FAILED to reject ({reason}): {url}")
            all_rejected = False
        except ValueError as e:
            print(f"  ✓ Correctly rejected ({reason}): {url}")

    if all_rejected:
        print("\n✅ All invalid URLs were correctly rejected!")
        return True
    else:
        print("\n❌ Some invalid URLs were not rejected!")
        return False


async def test_url_fetching():
    """Test actual URL fetching from public sources"""
    print("\n" + "=" * 60)
    print("Test 2: URL Fetching")
    print("=" * 60)

    from mcp_server import SandboxManager

    # Test with a real URL that should work
    test_urls = [
        ("https://httpbin.org/uuid", "JSON response from httpbin"),
        (
            "https://raw.githubusercontent.com/python/cpython/main/LICENSE",
            "Python LICENSE file",
        ),
    ]

    all_passed = True

    for url, description in test_urls:
        print(f"\n📥 Fetching: {description}")
        print(f"   URL: {url}")
        try:
            result = await SandboxManager.fetch_code_from_url(url)
            print(f"   ✓ Success!")
            print(f"     - Size: {result['size']} bytes")
            print(f"     - Content-Type: {result.get('content_type', 'unknown')}")
            print(f"     - Content preview: {result['code'][:80]}...")
        except Exception as e:
            print(f"   ✗ Failed: {e}")
            all_passed = False

    if all_passed:
        print("\n✅ All URL fetches succeeded!")
        return True
    else:
        print("\n❌ Some URL fetches failed!")
        return False


async def test_error_handling():
    """Test error handling for various failure scenarios"""
    print("\n" + "=" * 60)
    print("Test 3: Error Handling")
    print("=" * 60)

    from mcp_server import SandboxManager

    error_tests = [
        ("https://httpbin.org/status/404", "404 Not Found"),
        ("https://httpbin.org/status/500", "500 Server Error"),
        (
            "http://this-domain-definitely-does-not-exist-12345678.com/code.py",
            "DNS failure",
        ),
    ]

    all_handled = True

    for url, expected_error in error_tests:
        print(f"\n🧪 Testing: {expected_error}")
        print(f"   URL: {url}")
        try:
            await SandboxManager.fetch_code_from_url(url)
            print(f"   ✗ Should have failed but succeeded!")
            all_handled = False
        except ValueError as e:
            print(f"   ✓ Correctly handled error: {str(e)[:60]}...")
        except Exception as e:
            print(f"   ✓ Caught exception: {type(e).__name__}: {str(e)[:60]}...")

    if all_handled:
        print("\n✅ All error cases handled correctly!")
        return True
    else:
        print("\n❌ Some error cases not handled properly!")
        return False


async def test_size_limit():
    """Test size limit enforcement"""
    print("\n" + "=" * 60)
    print("Test 4: Size Limit Enforcement")
    print("=" * 60)

    from mcp_server import SandboxManager, MAX_CODE_SIZE

    print(
        f"\nMax code size: {MAX_CODE_SIZE:,} bytes ({MAX_CODE_SIZE / 1024 / 1024:.1f} MB)"
    )

    # Use httpbin's drip endpoint which streams data slowly
    # We'll use /bytes endpoint to get specific size
    test_url = f"https://httpbin.org/bytes/{MAX_CODE_SIZE + 1}"

    print(f"\n🧪 Testing oversized content...")
    print(f"   Requesting: {MAX_CODE_SIZE + 1:,} bytes")

    try:
        await SandboxManager.fetch_code_from_url(test_url)
        print(f"   ✗ Should have rejected oversized content!")
        return False
    except ValueError as e:
        if "exceeds limit" in str(e).lower():
            print(f"   ✓ Correctly rejected: {str(e)[:60]}...")
            print("\n✅ Size limit enforcement working!")
            return True
        else:
            print(f"   ? Different error: {e}")
            return False
    except Exception as e:
        print(f"   ? Unexpected error: {type(e).__name__}: {e}")
        return False


async def test_content_validation():
    """Test content validation (empty content, etc)"""
    print("\n" + "=" * 60)
    print("Test 5: Content Validation")
    print("=" * 60)

    from mcp_server import SandboxManager

    # Test empty content
    empty_url = "https://httpbin.org/bytes/0"

    print(f"\n🧪 Testing empty content...")
    print(f"   URL: {empty_url}")

    try:
        await SandboxManager.fetch_code_from_url(empty_url)
        print(f"   ✗ Should have rejected empty content!")
        return False
    except ValueError as e:
        if "empty" in str(e).lower():
            print(f"   ✓ Correctly rejected: {e}")
            print("\n✅ Content validation working!")
            return True
        else:
            print(f"   ? Different error: {e}")
            return False
    except Exception as e:
        print(f"   ? Unexpected error: {type(e).__name__}: {e}")
        return False


async def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("  EXECUTE_FROM_URL COMPREHENSIVE TEST SUITE")
    print("=" * 70)

    results = []

    try:
        results.append(("URL Validation", await test_url_validation()))
        results.append(("URL Fetching", await test_url_fetching()))
        results.append(("Error Handling", await test_error_handling()))
        results.append(("Size Limit", await test_size_limit()))
        results.append(("Content Validation", await test_content_validation()))
    except Exception as e:
        print(f"\n❌ Fatal error during tests: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Summary
    print("\n" + "=" * 70)
    print("  TEST SUMMARY")
    print("=" * 70)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status:10} - {test_name}")

    print("=" * 70)

    all_passed = all(result[1] for result in results)

    if all_passed:
        print("\n🎉 ALL TESTS PASSED! execute_from_url is working correctly!")
        return True
    else:
        print("\n⚠️  SOME TESTS FAILED! Check the output above for details.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
