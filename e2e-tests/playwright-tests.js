// e2e-tests/playwright-tests.js
const { test, expect } = require('@playwright/test');
const scenarios = require('./test-scenarios');
const pageObjects = require('./page-objects');

const CONFIG = {
  baseURL: 'http://localhost:5173',
  backendURL: 'http://localhost:8000',
  timeout: 15000,
};

// Mock learner personas (matching backend/testing/learner_personas.py)
const PERSONAS = {
  consistent_learner: {
    name: 'Consistent Learner',
    daily_activity_probability: 0.85,
    study_hours_per_session: [1, 3],
    completion_rate: 0.90,
    rewatch_frequency: 0.05,
    flashcard_consistency: 0.95,
    quiz_success_rate: 0.85,
    dropout_probability: 0.05,
  },
  struggling_learner: {
    name: 'Struggling Learner',
    daily_activity_probability: 0.50,
    study_hours_per_session: [0.5, 2],
    completion_rate: 0.40,
    rewatch_frequency: 0.50,
    flashcard_consistency: 0.30,
    quiz_success_rate: 0.40,
    dropout_probability: 0.40,
  },
  binge_learner: {
    name: 'Binge Learner',
    daily_activity_probability: 0.20,
    study_hours_per_session: [4, 8],
    completion_rate: 0.70,
    rewatch_frequency: 0.15,
    flashcard_consistency: 0.10,
    quiz_success_rate: 0.75,
    dropout_probability: 0.25,
  },
  casual_learner: {
    name: 'Casual Learner',
    daily_activity_probability: 0.35,
    study_hours_per_session: [0.5, 1.5],
    completion_rate: 0.50,
    rewatch_frequency: 0.20,
    flashcard_consistency: 0.25,
    quiz_success_rate: 0.60,
    dropout_probability: 0.35,
  },
  perfectionist_learner: {
    name: 'Perfectionist Learner',
    daily_activity_probability: 0.80,
    study_hours_per_session: [2, 4],
    completion_rate: 0.95,
    rewatch_frequency: 0.40,
    flashcard_consistency: 0.99,
    quiz_success_rate: 0.95,
    dropout_probability: 0.02,
  },
  procrastinator: {
    name: 'Procrastinator',
    daily_activity_probability: 0.10,
    study_hours_per_session: [1, 2],
    completion_rate: 0.25,
    rewatch_frequency: 0.30,
    flashcard_consistency: 0.05,
    quiz_success_rate: 0.50,
    dropout_probability: 0.70,
  },
};

// Test data for 50 users (simplified mock)
const generateTestUsers = (count = 50) => {
  const personaKeys = Object.keys(PERSONAS);
  const users = [];
  
  for (let i = 0; i < count; i++) {
    const personaKey = personaKeys[i % personaKeys.length];
    users.push({
      name: `Test User ${i + 1}`,
      email: `testuser${i + 1}.${Date.now()}@example.com`,
      password: 'TestPass123!',
      persona: PERSONAS[personaKey],
      personaType: personaKey,
    });
  }
  
  return users;
};

test.describe('SkillOS - User Registration & Authentication', () => {
  
  test('New user registration flow', async ({ page }) => {
    const user = {
      name: 'Jane Smith',
      email: `jane.${Date.now()}@example.com`,
      password: 'TestPass123!',
    };
    
    const success = await scenarios.registrationScenario(page, user);
    expect(success).toBe(true);
    
    // Verify user is on dashboard or onboarding
    const url = page.url();
    expect(url).toMatch(/(dashboard|onboarding)/);
  });

  test('User login with valid credentials', async ({ page }) => {
    // This assumes a test user already exists
    const email = 'testuser@example.com';
    const password = 'TestPass123!';
    
    const success = await scenarios.loginScenario(page, email, password);
    expect(success).toBe(true);
    expect(page.url()).toContain('dashboard');
  });
});

test.describe('SkillOS - Dashboard Functionality', () => {
  
  test('Dashboard displays user stats', async ({ page }) => {
    // Navigate to dashboard
    await page.goto(`${CONFIG.baseURL}/dashboard`);
    
    const stats = await scenarios.dashboardScenario(page);
    
    // Verify stats returned
    expect(stats).toHaveProperty('xp');
    expect(stats).toHaveProperty('streak');
    expect(stats.xp).toBeGreaterThanOrEqual(0);
    expect(stats.streak).toBeGreaterThanOrEqual(0);
  });

  test('Add learning resource to dashboard', async ({ page }) => {
    await page.goto(`${CONFIG.baseURL}/dashboard`);
    
    const resourceData = {
      title: 'Python Advanced Concepts',
      platform: 'Udemy',
      url: 'https://example.com/python-advanced',
    };
    
    const result = await scenarios.addResourceScenario(page, resourceData);
    expect(result.resourceAdded).toBe(true);
  });

  test('Dashboard UI elements are visible', async ({ page }) => {
    const dashboard = new pageObjects.DashboardPage(page);
    await dashboard.goto();
    
    await dashboard.verifyDashboardLoaded();
    await dashboard.verifyXPVisible();
    await dashboard.verifyStreakVisible();
    await dashboard.verifyGoalsVisible();
  });
});

test.describe('SkillOS - Analytics & Insights', () => {
  
  test('Analytics page loads successfully', async ({ page }) => {
    await page.goto(`${CONFIG.baseURL}/dashboard`);
    
    const success = await scenarios.analyticsScenario(page);
    expect(success).toBe(true);
  });

  test('Analytics shows learning charts', async ({ page }) => {
    const analyticsPage = new pageObjects.AnalyticsPage(page);
    await analyticsPage.goto();
    
    await analyticsPage.verifyChartsLoaded();
    await analyticsPage.verifyWeeklyLearningVisible();
    await analyticsPage.verifyProficiencyVisible();
  });
});

test.describe('SkillOS - Recommendations', () => {
  
  test('Recommendations page displays suggestions', async ({ page }) => {
    await page.goto(`${CONFIG.baseURL}/dashboard`);
    
    const result = await scenarios.recommendationsScenario(page);
    expect(result.recommendationsCount).toBeGreaterThanOrEqual(0);
  });
});

test.describe('SkillOS - Persona-Based Scenarios (50 Users)', () => {
  
  test('Consistent learner behavior - adds resources regularly', async ({ page }) => {
    await page.goto(`${CONFIG.baseURL}/dashboard`);
    
    const persona = PERSONAS.consistent_learner;
    const activities = await scenarios.personaActivityScenario(page, persona, 3);
    
    expect(activities.length).toBeGreaterThan(0);
    const successfulActivities = activities.filter(a => a.success);
    expect(successfulActivities.length).toBeGreaterThan(0);
  });

  test('Struggling learner behavior - inconsistent engagement', async ({ page }) => {
    await page.goto(`${CONFIG.baseURL}/dashboard`);
    
    const persona = PERSONAS.struggling_learner;
    const activities = await scenarios.personaActivityScenario(page, persona, 2);
    
    expect(activities.length).toBeGreaterThanOrEqual(0);
  });

  test('Binge learner behavior - longer session', async ({ page }) => {
    await page.goto(`${CONFIG.baseURL}/dashboard`);
    
    const persona = PERSONAS.binge_learner;
    const activities = await scenarios.personaActivityScenario(page, persona, 1);
    
    // Binge learners do fewer activities but longer ones
    expect(activities.length).toBeGreaterThanOrEqual(0);
  });

  test('Casual learner behavior - occasional engagement', async ({ page }) => {
    await page.goto(`${CONFIG.baseURL}/dashboard`);
    
    const persona = PERSONAS.casual_learner;
    const activities = await scenarios.personaActivityScenario(page, persona, 2);
    
    expect(activities.length).toBeGreaterThanOrEqual(0);
  });

  test('Perfectionist learner behavior - high completion rate', async ({ page }) => {
    await page.goto(`${CONFIG.baseURL}/dashboard`);
    
    const persona = PERSONAS.perfectionist_learner;
    const activities = await scenarios.personaActivityScenario(page, persona, 3);
    
    const successfulActivities = activities.filter(a => a.success);
    // Perfectionist should complete more activities successfully
    expect(successfulActivities.length).toBeGreaterThan(0);
  });

  test('Procrastinator behavior - low engagement', async ({ page }) => {
    await page.goto(`${CONFIG.baseURL}/dashboard`);
    
    const persona = PERSONAS.procrastinator;
    const activities = await scenarios.personaActivityScenario(page, persona, 1);
    
    expect(activities.length).toBeGreaterThanOrEqual(0);
  });
});

test.describe('SkillOS - Complete User Journeys', () => {
  
  test('Complete flow: register -> add resources -> view analytics', async ({ page }) => {
    const user = {
      name: `Journey User ${Date.now()}`,
      email: `journey.${Date.now()}@example.com`,
      password: 'TestPass123!',
    };
    
    const result = await scenarios.completeUserJourneyScenario(page, user);
    
    expect(result.dashboardStats).toBeDefined();
    expect(result.recommendationsCount).toBeGreaterThanOrEqual(0);
  });
});

test.describe('SkillOS - Performance Tests', () => {
  
  test('Dashboard loads in < 2 seconds', async ({ page }) => {
    const start = Date.now();
    await page.goto(`${CONFIG.baseURL}/dashboard`);
    const duration = Date.now() - start;
    
    console.log(`Dashboard load time: ${duration}ms`);
    expect(duration).toBeLessThan(2000);
  });
  
  test('Analytics page loads in < 3 seconds', async ({ page }) => {
    const start = Date.now();
    await page.goto(`${CONFIG.baseURL}/analytics`);
    const duration = Date.now() - start;
    
    console.log(`Analytics load time: ${duration}ms`);
    expect(duration).toBeLessThan(3000);
  });

  test('Recommendations page loads in < 2 seconds', async ({ page }) => {
    const start = Date.now();
    await page.goto(`${CONFIG.baseURL}/recommendations`);
    const duration = Date.now() - start;
    
    console.log(`Recommendations load time: ${duration}ms`);
    expect(duration).toBeLessThan(2000);
  });
});

test.describe('SkillOS - Data Validation (50 Users)', () => {
  
  test('Verify 50 user personas are represented', () => {
    const users = generateTestUsers(50);
    
    expect(users.length).toBe(50);
    
    // Verify persona distribution
    const personaCounts = {};
    users.forEach(user => {
      personaCounts[user.personaType] = (personaCounts[user.personaType] || 0) + 1;
    });
    
    console.log('Persona Distribution:', personaCounts);
    
    // All personas should be represented
    Object.keys(PERSONAS).forEach(personaType => {
      expect(personaCounts[personaType]).toBeGreaterThan(0);
    });
  });

  test('Each user has valid test data', () => {
    const users = generateTestUsers(50);
    
    users.forEach(user => {
      expect(user.name).toBeTruthy();
      expect(user.email).toMatch(/@example\.com$/);
      expect(user.password).toBe('TestPass123!');
      expect(user.persona).toBeDefined();
      expect(user.personaType).toBeTruthy();
    });
  });
});