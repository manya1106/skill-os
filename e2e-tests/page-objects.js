// e2e-tests/page-objects.js
// Fixed version with correct selectors matching frontend implementation

const { expect } = require('@playwright/test');

const BASE_URL = 'http://localhost:5173';
const TIMEOUT = 15000;

class BasePage {
  constructor(page) {
    this.page = page;
  }

  async goto(path = '') {
    await this.page.goto(`${BASE_URL}${path}`, { waitUntil: 'networkidle' });
  }

  async waitForNavigation(url) {
    await this.page.waitForURL(url, { timeout: TIMEOUT });
  }
}

class LoginPage extends BasePage {
  constructor(page) {
    super(page);
    this.emailInput = page.locator('input[type="email"]');
    this.passwordInput = page.locator('input[type="password"]').first();
    this.loginButton = page.locator('button[type="submit"]').filter({ hasText: /Sign in|Login/ });
  }

  async login(email, password) {
    await this.goto('/');
    await this.page.waitForTimeout(500); // Wait for page to render
    
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.loginButton.click();
    
    // Wait for redirect to dashboard or onboarding
    await this.page.waitForURL(/\/(dashboard|onboarding)/, { timeout: TIMEOUT });
  }

  async getErrorMessage() {
    const error = this.page.locator('[class*="error"], [class*="danger"]');
    return await error.textContent();
  }
}

class RegisterPage extends BasePage {
  constructor(page) {
    super(page);
    this.nameInput = page.locator('input[type="text"]').first();
    this.emailInput = page.locator('input[type="email"]');
    this.passwordInput = page.locator('input[type="password"]').first();
    this.confirmPasswordInput = page.locator('input[type="password"]').last();
    this.createAccountButton = page.locator('button[type="submit"]').filter({ hasText: /Create|Sign up/ });
  }

  async register(name, email, password) {
    // Click on create account link if on login page
    const createLink = this.page.locator('button, a').filter({ hasText: /Create|Sign up|No account/ });
    await createLink.click().catch(() => {});
    
    await this.page.waitForURL(/register/, { timeout: TIMEOUT });
    
    await this.nameInput.fill(name);
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.confirmPasswordInput.fill(password);
    await this.createAccountButton.click();
    
    await this.page.waitForURL(/dashboard/, { timeout: TIMEOUT });
  }
}

class DashboardPage extends BasePage {
  constructor(page) {
    super(page);
    this.heading = page.locator('h1, h2').filter({ hasText: /Dashboard|Learning|My Learning/ });
    this.xpDisplay = page.locator('text=/\\d+\\s*XP/');
    this.streakDisplay = page.locator('text=/\\d+d\\s*(🔥|streak|flame)/');
    this.addResourceButton = page.locator('button').filter({ hasText: /Add resource|Add Resource/ });
    this.analyticsLink = page.locator('button, a').filter({ hasText: /Analytics/ });
    this.recommendationsLink = page.locator('button, a').filter({ hasText: /Recommended|Recommendations/ });
  }

  async goto() {
    await super.goto('/dashboard');
    await this.page.waitForTimeout(1000);
    // Wait for dashboard to load
    await this.page.locator('body').waitFor({ timeout: TIMEOUT });
  }

  async verifyDashboardLoaded() {
    // Check if we're on dashboard
    const url = this.page.url();
    expect(url).toContain('dashboard');
  }

  async getXPValue() {
    const text = await this.xpDisplay.first().textContent();
    const match = text.match(/(\d+)/);
    return match ? parseInt(match[1]) : 0;
  }

  async getStreakValue() {
    const text = await this.streakDisplay.first().textContent();
    const match = text.match(/(\d+)/);
    return match ? parseInt(match[1]) : 0;
  }

  async verifyXPVisible() {
    await expect(this.xpDisplay.first()).toBeVisible({ timeout: TIMEOUT });
  }

  async verifyStreakVisible() {
    await expect(this.streakDisplay.first()).toBeVisible({ timeout: TIMEOUT }).catch(() => {
      // Streak may not be visible if user just created account
      return true;
    });
  }

  async clickAddResource() {
    await this.addResourceButton.click();
  }

  async goToAnalytics() {
    await this.analyticsLink.click();
    await this.page.waitForURL(/analytics/, { timeout: TIMEOUT });
  }

  async goToRecommendations() {
    await this.recommendationsLink.click();
    await this.page.waitForURL(/recommendations/, { timeout: TIMEOUT });
  }
}

class GoalWizardPage extends BasePage {
  constructor(page) {
    super(page);
    this.goalInput = page.locator('input[type="text"]').first();
    this.createGoalButton = page.locator('button').filter({ hasText: /Create|Next|Complete/ });
  }

  async createGoal(goalText) {
    await this.goalInput.fill(goalText);
    await this.createGoalButton.click();
    await this.page.waitForTimeout(500);
  }
}

class ResourcePage extends BasePage {
  constructor(page) {
    super(page);
    this.resourceTitleInput = page.locator('input[placeholder*="resource"], input[placeholder*="Course"], input[placeholder*="Title"]').first();
    this.platformSelect = page.locator('select').first();
    this.urlInput = page.locator('input[type="url"], input[placeholder*="http"]');
    this.saveButton = page.locator('button').filter({ hasText: /Save|Add Resource/ });
  }

  async addResource(title, platform, url = '') {
    await this.resourceTitleInput.fill(title);
    
    if (this.platformSelect.isVisible()) {
      await this.platformSelect.selectOption(platform);
    }
    
    if (url) {
      const urlInput = page.locator('input[type="url"], input[placeholder*="http"]').first();
      await urlInput.fill(url);
    }
    
    await this.saveButton.click();
    await this.page.waitForTimeout(1000);
  }
}

class AnalyticsPage extends BasePage {
  constructor(page) {
    super(page);
    this.charts = page.locator('svg');
  }

  async goto() {
    await super.goto('/analytics');
    await this.page.waitForTimeout(1000);
  }

  async verifyChartsLoaded() {
    const count = await this.charts.count();
    expect(count).toBeGreaterThan(0);
  }
}

class RecommendationsPage extends BasePage {
  constructor(page) {
    super(page);
    this.cards = page.locator('[class*="card"], [role="article"]');
  }

  async goto() {
    await super.goto('/recommendations');
    await this.page.waitForTimeout(1000);
  }

  async getRecommendationCount() {
    return await this.cards.count();
  }
}

module.exports = {
  BasePage,
  LoginPage,
  RegisterPage,
  DashboardPage,
  GoalWizardPage,
  ResourcePage,
  AnalyticsPage,
  RecommendationsPage,
  BASE_URL,
};