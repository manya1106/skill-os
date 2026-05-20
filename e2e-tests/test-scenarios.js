// e2e-tests/test-scenarios.js
// Reusable test scenarios for Skill-OS

const {
  LoginPage,
  RegisterPage,
  DashboardPage,
  GoalWizardPage,
  ResourcePage,
  AnalyticsPage,
  RecommendationsPage,
  BASE_URL,
} = require('./page-objects');

/**
 * User Registration Scenario
 * Tests new user account creation
 */
async function registrationScenario(page, userData) {
  const registerPage = new RegisterPage(page);
  await registerPage.register(userData.name, userData.email, userData.password);
  return true;
}

/**
 * User Login Scenario
 * Tests user authentication
 */
async function loginScenario(page, email, password) {
  const loginPage = new LoginPage(page);
  await loginPage.login(email, password);
  return true;
}

/**
 * Dashboard Verification Scenario
 * Verifies all dashboard components are loaded
 */
async function dashboardScenario(page) {
  const dashboardPage = new DashboardPage(page);
  await dashboardPage.goto();
  await dashboardPage.verifyDashboardLoaded();
  await dashboardPage.verifyXPVisible();
  await dashboardPage.verifyStreakVisible();
  
  const xp = await dashboardPage.getXPValue();
  const streak = await dashboardPage.getStreakValue();
  
  return { xp, streak };
}

/**
 * Create Learning Goal Scenario
 * Tests goal creation workflow
 */
async function createLearningGoalScenario(page, goalText) {
  const dashboardPage = new DashboardPage(page);
  const goalPage = new GoalWizardPage(page);
  
  // Navigate to goal creation (assuming there's a button on dashboard)
  await dashboardPage.goto();
  
  // If there's a goal wizard page, navigate to it
  // You may need to adjust based on actual UI
  await page.goto(`${BASE_URL}/goals/create`);
  await goalPage.createGoal(goalText);
  
  return true;
}

/**
 * Add Learning Resource Scenario
 * Tests adding a course/resource to the dashboard
 */
async function addResourceScenario(page, resourceData) {
  const dashboardPage = new DashboardPage(page);
  const resourcePage = new ResourcePage(page);
  
  await dashboardPage.goto();
  const xpBefore = await dashboardPage.getXPValue();
  
  await dashboardPage.clickAddResource();
  await resourcePage.addResource(
    resourceData.title,
    resourceData.platform,
    resourceData.url
  );
  
  // Wait and verify XP might have changed
  await page.waitForTimeout(1000);
  const xpAfter = await dashboardPage.getXPValue();
  
  return { xpBefore, xpAfter, resourceAdded: true };
}

/**
 * Analytics Page Scenario
 * Tests analytics page load and chart rendering
 */
async function analyticsScenario(page) {
  const dashboardPage = new DashboardPage(page);
  const analyticsPage = new AnalyticsPage(page);
  
  await dashboardPage.goto();
  await dashboardPage.goToAnalytics();
  
  await analyticsPage.verifyChartsLoaded();
  await analyticsPage.verifyWeeklyLearningVisible();
  
  return true;
}

/**
 * Recommendations Scenario
 * Tests recommendations page
 */
async function recommendationsScenario(page) {
  const dashboardPage = new DashboardPage(page);
  const recommendationsPage = new RecommendationsPage(page);
  
  await dashboardPage.goto();
  await dashboardPage.goToRecommendations();
  
  const count = await recommendationsPage.getRecommendationCount();
  return { recommendationsCount: count };
}

/**
 * Complete User Journey Scenario
 * Tests the full user flow: register -> login -> create goal -> add resource -> view analytics
 */
async function completeUserJourneyScenario(page, userData) {
  // Registration
  await registrationScenario(page, userData);
  
  // Dashboard
  const dashboardStats = await dashboardScenario(page);
  
  // Add resource
  await addResourceScenario(page, {
    title: 'Advanced Python Programming',
    platform: 'Udemy',
    url: 'https://example.com/python-course'
  });
  
  // View analytics
  await analyticsScenario(page);
  
  // View recommendations
  const recs = await recommendationsScenario(page);
  
  return { dashboardStats, recommendationsCount: recs.recommendationsCount };
}

/**
 * Persona-based Activity Scenario
 * Simulates user activities based on learner persona
 */
async function personaActivityScenario(page, persona, activityCount = 3) {
  const dashboardPage = new DashboardPage(page);
  const resourcePage = new ResourcePage(page);
  
  const activities = [
    { title: 'React Fundamentals', platform: 'YouTube' },
    { title: 'State Management', platform: 'Coursera' },
    { title: 'Next.js Mastery', platform: 'Udemy' },
  ];
  
  const results = [];
  
  for (let i = 0; i < Math.min(activityCount, activities.length); i++) {
    await dashboardPage.goto();
    const before = await dashboardPage.getXPValue();
    
    try {
      await dashboardPage.clickAddResource();
      await resourcePage.addResource(
        activities[i].title,
        activities[i].platform
      );
      
      const after = await dashboardPage.getXPValue();
      results.push({
        activity: activities[i].title,
        xpGained: after - before,
        success: true
      });
    } catch (error) {
      results.push({
        activity: activities[i].title,
        success: false,
        error: error.message
      });
    }
    
    // Simulate different activity patterns based on persona
    const delay = persona.daily_activity_probability > 0.7 ? 500 : 2000;
    await page.waitForTimeout(delay);
  }
  
  return results;
}

module.exports = {
  registrationScenario,
  loginScenario,
  dashboardScenario,
  createLearningGoalScenario,
  addResourceScenario,
  analyticsScenario,
  recommendationsScenario,
  completeUserJourneyScenario,
  personaActivityScenario,
};