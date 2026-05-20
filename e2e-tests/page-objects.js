// e2e-tests/page-objects.js
// Reusable Playwright page objects for Skill-OS

const { expect } = require('@playwright/test');

const BASE_URL = 'http://localhost:5173';
const TIMEOUT = 10000;

class BasePage {
  constructor(page) {
    this.page = page;
  }

  async goto(path = '') {
    await this.page.goto(`${BASE_URL}${path}`);
  }

  async waitForNavigation() {
    await this.page.waitForNavigation({ waitUntil: 'networkidle', timeout: TIMEOUT });
  }
}

class LoginPage extends BasePage {
  constructor(page) {
    super(page);
    this.emailInput = page.locator('input[type="email"]');
    this.passwordInput = page.locator('input[type="password"]');
    this.loginButton = page.locator('button:has-text("Login"), button:has-text("Sign in")');
    this.errorMessage = page.locator('[data-testid="error-message"], .error');
  }

  async login(email, password) {
    await this.goto('/login');
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.loginButton.click();
    await this.page.waitForURL('**/dashboard', { timeout: TIMEOUT });
  }

  async getErrorMessage() {
    return await this.errorMessage.textContent();
  }
}

class RegisterPage extends BasePage {
  constructor(page) {
    super(page);
    this.nameInput = page.locator('input[placeholder*="name"], input[name="name"]');
    this.emailInput = page.locator('input[type="email"]');
    this.passwordInput = page.locator('input[type="password"]').first();
    this.confirmPasswordInput = page.locator('input[type="password"]').last();
    this.createAccountButton = page.locator('button:has-text("Create account"), button:has-text("Sign up")');
  }

  async register(name, email, password) {
    await this.goto('/register');
    await this.nameInput.fill(name);
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.confirmPasswordInput.fill(password);
    await this.createAccountButton.click();
    await this.page.waitForURL('**/dashboard|**/onboarding', { timeout: TIMEOUT });
  }
}

class DashboardPage extends BasePage {
  constructor(page) {
    super(page);
    this.dashboardHeading = page.locator('text=Dashboard, text=My Learning');
    this.xpCard = page.locator('[data-testid="xp-card"], text=/\d+\s*XP/');
    this.streakCard = page.locator('[data-testid="streak-card"], text=/\d+\s*day\s*streak/');
    this.goalSection = page.locator('[data-testid="goal-section"], text=Learning Goals');
    this.addResourceButton = page.locator('button:has-text("Add resource"), button:has-text("Add Resource")');
    this.analyticsLink = page.locator('a:has-text("Analytics"), button:has-text("Analytics")');
    this.recommendationsLink = page.locator('a:has-text("Recommendations"), button:has-text("Recommendations")');
  }

  async goto() {
    await super.goto('/dashboard');
    await this.page.waitForSelector(this.dashboardHeading, { timeout: TIMEOUT });
  }

  async verifyDashboardLoaded() {
    await expect(this.dashboardHeading).toBeVisible();
  }

  async getXPValue() {
    const text = await this.xpCard.textContent();
    const match = text.match(/(\d+)/);  
    return match ? parseInt(match[1]) : 0;
  }

  async getStreakValue() {
    const text = await this.streakCard.textContent();
    const match = text.match(/(\d+)/);  
    return match ? parseInt(match[1]) : 0;
  }

  async verifyXPVisible() {
    await expect(this.xpCard).toBeVisible();
  }

  async verifyStreakVisible() {
    await expect(this.streakCard).toBeVisible();
  }

  async verifyGoalsVisible() {
    await expect(this.goalSection).toBeVisible();
  }

  async clickAddResource() {
    await this.addResourceButton.click();
  }

  async goToAnalytics() {
    await this.analyticsLink.click();
    await this.page.waitForURL('**/analytics', { timeout: TIMEOUT });
  }

  async goToRecommendations() {
    await this.recommendationsLink.click();
    await this.page.waitForURL('**/recommendations', { timeout: TIMEOUT });
  }
}

class GoalWizardPage extends BasePage {
  constructor(page) {
    super(page);
    this.goalInput = page.locator('input[name="goal"], input[placeholder*="goal" i]');
    this.goalSelect = page.locator('select, [role="listbox"]');
    this.createGoalButton = page.locator('button:has-text("Create Goal"), button:has-text("Create"), button:has-text("Next")');
    this.goalTitle = page.locator('h1, h2');
  }

  async createGoal(goalText) {
    await this.goalInput.fill(goalText);
    await this.createGoalButton.click();
    await this.page.waitForTimeout(500);
  }

  async selectGoalFromList(goalText) {
    await this.page.locator(`text="${goalText}"`).click();
    await this.page.waitForTimeout(500);
  }
}

class ResourcePage extends BasePage {
  constructor(page) {
    super(page);
    this.resourceTitleInput = page.locator('input[placeholder*="Course"], input[placeholder*="Title"], input[name="title"]');
    this.platformSelect = page.locator('select');
    this.urlInput = page.locator('input[type="url"], input[placeholder*="url" i]');
    this.saveButton = page.locator('button:has-text("Save"), button:has-text("Add Resource")');
    this.cancelButton = page.locator('button:has-text("Cancel")');
  }

  async addResource(title, platform, url = '') {
    await this.resourceTitleInput.fill(title);
    await this.platformSelect.selectOption(platform);
    if (url) {
      await this.urlInput.fill(url);
    }
    await this.saveButton.click();
    await this.page.waitForTimeout(1000);
  }
}

class AnalyticsPage extends BasePage {
  constructor(page) {
    super(page);
    this.weeklyLearningChart = page.locator('text=Weekly learning time, text=Learning time');
    this.proficiencyChart = page.locator('text=Platform proficiency, text=Proficiency');
    this.retentionChart = page.locator('text=Knowledge retention, text=Retention');
    this.charts = page.locator('svg');
  }

  async goto() {
    await super.goto('/analytics');
    await this.page.waitForSelector(this.weeklyLearningChart, { timeout: TIMEOUT });
  }

  async verifyChartsLoaded() {
    const chartCount = await this.charts.count();
    expect(chartCount).toBeGreaterThan(0);
  }

  async verifyWeeklyLearningVisible() {
    await expect(this.weeklyLearningChart).toBeVisible();
  }

  async verifyProficiencyVisible() {
    await expect(this.proficiencyChart).toBeVisible();
  }

  async verifyRetentionVisible() {
    await expect(this.retentionChart).toBeVisible();
  }
}

class RecommendationsPage extends BasePage {
  constructor(page) {
    super(page);
    this.recommendationCards = page.locator('[data-testid="recommendation-card"], .recommendation-card, [class*="recommendation"]');
    this.filterButton = page.locator('button:has-text("Filter")');
    this.noRecommendationsMessage = page.locator('text=No recommendations');
  }

  async goto() {
    await super.goto('/recommendations');
    await this.page.waitForTimeout(1000);
  }

  async getRecommendationCount() {
    return await this.recommendationCards.count();
  }

  async clickFirstRecommendation() {
    const firstCard = this.recommendationCards.first();
    await firstCard.click();
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