from playwright.sync_api import Page, expect


def test_admin_dashboard_loads_correctly(page: Page, demo_base_url):
    """Test that the admin dashboard loads correctly and displays expected content."""
    page.goto(f"{demo_base_url}/admin/")

    # Expect a successful response
    expect(page).to_have_url(f"{demo_base_url}/admin/")
    expect(page.get_by_role("heading", name="Welcome to HyperAdmin Dashboard")).to_be_visible()

    # Verify that the navbar and sidebar are present
    expect(page.get_by_role("navigation", name="Main navigation")).to_be_visible()
    expect(page.get_by_test_id("sidebar")).to_be_visible()
