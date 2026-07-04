import re

from playwright.sync_api import Page, expect


def test_create_product_form_rendering(page: Page, demo_base_url: str):
    """Test that the create form for Product model is rendered correctly."""
    page.goto(f"{demo_base_url}/admin/product/create")
    expect(page).to_have_title("HyperAdmin")
    expect(page.get_by_role("heading", name="Create Product")).to_be_visible()
    expect(page.get_by_test_id("model-form")).to_be_visible()

    expect(page.get_by_label("Name*")).to_be_visible()
    expect(page.get_by_label("Description*")).to_be_visible()
    expect(page.get_by_label("Price*")).to_be_visible()
    expect(page.get_by_label("Is available*")).to_be_visible()
    expect(page.get_by_label("Category*")).to_be_visible()
    expect(page.get_by_role("button", name="Create")).to_be_visible()


def test_create_product_validation_error(page: Page, demo_base_url: str):
    """Test that submitting an invalid form for Product model shows an error message."""
    page.goto(f"{demo_base_url}/admin/product/create")
    page.get_by_label("Name*").fill("")
    page.get_by_role("button", name="Create").click()
    error_list = page.get_by_test_id("name-errors")
    expect(error_list).to_be_visible()
    expect(error_list).to_contain_text("String should have at least 1 character")


def test_create_product_successful_submission(page: Page, demo_base_url: str):
    """Test that successful submission for Product model redirects to the detail page."""
    page.goto(f"{demo_base_url}/admin/product/create")

    page.get_by_label("Name*").fill("Test Product")
    page.get_by_label("Description*").fill("A great product")
    page.get_by_label("Price*").fill("12.34")
    page.get_by_label("Is available*").check()
    page.get_by_label("Category*").select_option("BOOKS")

    page.get_by_role("button", name="Create").click()

    # The redirect is handled by HTMX, so we need to wait for the URL to change.
    expect(page).to_have_url(re.compile(r".*/admin/product/\d+"))
    expect(page.get_by_role("heading", name=re.compile(r"Test Product"))).to_contain_text(
        "Test Product"
    )
    expect(page.get_by_test_id("detail-fields")).to_contain_text("Test Product")
    expect(page.get_by_test_id("detail-fields")).to_contain_text("A great product")
    expect(page.get_by_test_id("detail-fields")).to_contain_text("12.34")
    expect(page.get_by_test_id("detail-fields")).to_contain_text("True")
    expect(page.get_by_test_id("detail-fields")).to_contain_text("ProductCategory.BOOKS")
