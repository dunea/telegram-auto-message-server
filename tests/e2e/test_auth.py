import uuid
from playwright.sync_api import Page, expect

def test_login_success_and_redirect(page: Page, server_url: str, e2e_user: dict) -> None:
    page.goto(f"{server_url}/web/login")
    
    # Fill login form
    page.fill('input[name="email"]', e2e_user["email"])
    page.fill('input[name="password"]', e2e_user["password"])
    page.click('button[type="submit"]')
    
    # Verify redirect to dashboard
    page.wait_for_url(f"{server_url}/web/dashboard")
    expect(page).to_have_url(f"{server_url}/web/dashboard")
    
    # Verify content rendering
    expect(page.locator("body")).to_contain_text("数据主页 & 仪表盘")


def test_login_failure_with_wrong_password(page: Page, server_url: str, e2e_user: dict) -> None:
    page.goto(f"{server_url}/web/login")
    
    # Fill login form with wrong password
    page.fill('input[name="email"]', e2e_user["email"])
    page.fill('input[name="password"]', "wrongpassword!")
    page.click('button[type="submit"]')
    
    # Verify remains on the login page or re-renders
    expect(page.locator("body")).to_contain_text("邮箱或密码错误")


def test_registration_success_and_redirect(page: Page, server_url: str) -> None:
    page.goto(f"{server_url}/web/register")
    
    # Use a dynamic random email to avoid duplicate key errors on rerun
    random_email = f"e2e_new_{uuid.uuid4().hex[:8]}@example.com"
    
    # Fill registration form
    page.fill('input[name="email"]', random_email)
    page.fill('input[name="password"]', "Password123!")
    page.click('button[type="submit"]')
    
    # Verify redirects to login page with parameter
    page.wait_for_url(f"{server_url}/web/login?registered=true")
    expect(page).to_have_url(f"{server_url}/web/login?registered=true")
    
    # Verify registered notification exists
    expect(page.locator("body")).to_contain_text("注册成功")
