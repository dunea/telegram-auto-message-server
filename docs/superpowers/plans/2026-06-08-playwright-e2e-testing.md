# Playwright E2E Testing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Playwright E2E tests for the web interface, verifying login, registration, validation errors, and dashboard redirect, using a background running FastAPI instance and database seed fixture.

**Architecture:** Use `uvicorn.Server` inside a background Python thread to run a dedicated FastAPI instance on port 8099. Initialize a dedicated test user in the database through a fixture before test execution. Use standard Playwright APIs to interact with the chromium browser in headless mode.

**Tech Stack:** pytest, pytest-playwright, uvicorn, SQLAlchemy, Playwright (Chromium)

---

### Task 1: Initialize E2E Directory and Configuration Fixtures

**Files:**
- Create: `tests/e2e/conftest.py`

- [ ] **Step 1: Write E2E conftest.py configuration with FastAPI thread and E2E user fixture**

Create `tests/e2e/conftest.py` with the following content:
```python
import threading
import time
import uvicorn
import pytest
from app.config import get_settings
from app.startup import create_api_application
from app.api.deps import get_session_factory
from app.service.auth_service import AuthService
from app.repository.user_repository import SqlAlchemyUserRepository

@pytest.fixture(scope="session")
def server_url():
    settings = get_settings()
    host = "127.0.0.1"
    port = 8099  # 使用独立端口避免冲突
    app = create_api_application(settings)
    
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning"))
    thread = threading.Thread(target=server.run)
    thread.daemon = True
    thread.start()
    
    time.sleep(1.0)  # 等待服务启动
    yield f"http://{host}:{port}"
    
    server.should_exit = True
    thread.join(timeout=5)

@pytest.fixture(scope="session")
def e2e_user(server_url):
    session_factory = get_session_factory()
    session = session_factory()
    try:
        settings = get_settings()
        user_repo = SqlAlchemyUserRepository(session)
        auth_service = AuthService(settings, session, user_repo)
        
        email = "e2e_test@example.com"
        password = "password123"
        if not user_repo.ExistsByEmail(email):
            auth_service.RegisterUser(email=email, password=password)
        session.commit()
        return {"email": email, "password": password}
    finally:
        session.close()
```

- [ ] **Step 2: Commit file initialization**

```bash
git add tests/e2e/conftest.py
git commit -m "test: add e2e conftest with server and user seed fixture"
```

---

### Task 2: Create E2E Test Auth Suite

**Files:**
- Create: `tests/e2e/test_auth.py`

- [ ] **Step 1: Write E2E auth tests verifying login, failed login, and registration redirect**

Create `tests/e2e/test_auth.py` containing three test cases:
1. `test_login_success_and_redirect`: Verify login with correct credentials redirects to `/web/dashboard` and displays the dashboard content.
2. `test_login_failure_with_wrong_password`: Verify login with incorrect credentials shows a red error message.
3. `test_registration_success_and_redirect`: Verify registration with a new unique email redirects to login page with `registered=true` query parameter and displays green success banner.

Test implementation code:
```python
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
    expect(page.locator("body")).to_contain_text("仪表盘")


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
```

- [ ] **Step 2: Commit test auth file**

```bash
git add tests/e2e/test_auth.py
git commit -m "test: add E2E tests for login, login failure, and registration flow"
```

---

### Task 3: Install Playwright and Run Verification

- [ ] **Step 1: Install Playwright pytest plugin and driver dependencies**

Run pip install and install chromium:
```bash
pip install pytest-playwright
playwright install chromium
```

- [ ] **Step 2: Run pytest to execute E2E tests and ensure all tests pass**

Run:
```bash
pytest tests/e2e -v
```

Expected output:
```text
tests/e2e/test_auth.py::test_login_success_and_redirect PASSED
tests/e2e/test_auth.py::test_login_failure_with_wrong_password PASSED
tests/e2e/test_auth.py::test_registration_success_and_redirect PASSED
```

- [ ] **Step 3: Final verification and reporting**
Verify the overall health of the codebase, confirming no regressions.
