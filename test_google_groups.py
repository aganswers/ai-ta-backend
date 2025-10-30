"""
Test script for Google Groups service.
Run this to verify the service account and scopes are configured correctly.
"""

from ai_ta_backend.integrations.google_groups import GoogleGroupsService


def test_sanitize_project_name():
    """Test project name sanitization."""
    service = GoogleGroupsService()
    
    test_cases = [
        ("My Farm", "my-farm"),
        ("Test!@#$% Project", "test-project"),
        ("AgAnswers 2024", "aganswers-2024"),
        ("Multiple   Spaces", "multiple-spaces"),
        ("---leading-trailing---", "leading-trailing"),
    ]
    
    print("Testing project name sanitization:")
    for input_name, expected in test_cases:
        result = service.sanitize_project_name(input_name)
        status = "✅" if result == expected else "❌"
        print(f"  {status} '{input_name}' -> '{result}' (expected: '{expected}')")


def test_service_account_auth():
    """Test service account authentication."""
    print("\nTesting service account authentication:")
    try:
        service = GoogleGroupsService()
        print("  ✅ Service account initialized successfully")
        print(f"  ✅ Admin service: {service.admin_service is not None}")
        print(f"  ✅ Settings service: {service.settings_service is not None}")
        print(f"  ✅ Drive service: {service.drive_service is not None}")
        return True
    except Exception as e:
        print(f"  ❌ Failed to initialize service: {e}")
        return False


def test_list_groups():
    """Test listing existing groups (read-only test)."""
    print("\nTesting group listing (read-only):")
    try:
        service = GoogleGroupsService()
        # Try to list groups (this is a read operation)
        response = service.admin_service.groups().list(domain='aganswers.ai', maxResults=5).execute()
        groups = response.get('groups', [])
        print(f"  ✅ Successfully listed groups: {len(groups)} found")
        for group in groups[:3]:
            print(f"    - {group.get('email')}: {group.get('name')}")
        return True
    except Exception as e:
        print(f"  ❌ Failed to list groups: {e}")
        print(f"     This might indicate missing scopes or permissions")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Google Groups Service Test")
    print("=" * 60)
    
    test_sanitize_project_name()
    
    if test_service_account_auth():
        test_list_groups()
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)

