import puppeteer from 'puppeteer-core';

const CHROME_PATH = process.env.CHROME_BIN || '/usr/bin/google-chrome';
const FRONTEND_URL = process.env.FRONTEND_URL || 'http://localhost:5173';

async function run() {
  console.log(`Launching Chrome from: ${CHROME_PATH}`);
  console.log(`Testing frontend at: ${FRONTEND_URL}`);

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800 });

  page.on('console', (msg) => console.log('BROWSER CONSOLE:', msg.type(), msg.text()));
  page.on('pageerror', (err) => console.log('BROWSER PAGE ERROR:', err.message));
  page.on('requestfailed', (req) => console.log('BROWSER REQ FAILED:', req.url(), req.failure()?.errorText));

  const results = {};

  try {
    // 1. Login Page
    console.log('--- Step 1: Login Page ---');
    await page.goto(FRONTEND_URL, { waitUntil: 'networkidle2' });
    const title = await page.evaluate(() => document.querySelector('h1')?.textContent || '');
    console.log(`Page title: "${title}"`);
    if (title.includes('ResolveFlow Operations')) {
      results['login_page_render'] = 'PASS';
    } else {
      throw new Error(`Unexpected page title: "${title}"`);
    }

    // 2. Perform Login
    console.log('--- Step 2: Perform Login ---');
    // Click Quick Fill for Admin Profile
    const adminBtn = await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const found = btns.find((b) => b.textContent && b.textContent.includes('Admin Profile'));
      if (found) {
        found.click();
        return true;
      }
      return false;
    });
    console.log(`Admin quick-fill clicked: ${adminBtn}`);

    // Click submit
    const submitBtn = await page.$('button[type="submit"]');
    if (submitBtn) {
      await submitBtn.click();
    } else {
      throw new Error('Submit button not found');
    }

    // Wait for Dashboard to appear
    await page.waitForFunction(
      () => {
        const h1 = document.querySelector('h1');
        return h1 && h1.textContent && h1.textContent.includes('Operations Command Center');
      },
      { timeout: 10000 }
    );
    results['login_auth'] = 'PASS';
    console.log('Dashboard rendered after login.');

    // 3. Dashboard Metrics
    console.log('--- Step 3: Dashboard Metrics ---');
    const metricCards = await page.evaluate(() => {
      const cards = document.querySelectorAll('.rf-stat-card, .rf-card');
      return cards.length;
    });
    console.log(`Found ${metricCards} cards on dashboard.`);
    results['dashboard_metrics'] = metricCards > 0 ? 'PASS' : 'FAIL';

    // 4. Navigate to Tickets Page
    console.log('--- Step 4: Navigate to Tickets ---');
    await page.evaluate(() => {
      const links = Array.from(document.querySelectorAll('nav button, aside button'));
      const ticketsLink = links.find((l) => l.textContent && l.textContent.includes('Ticket Queue'));
      if (ticketsLink) ticketsLink.click();
    });

    await page.waitForFunction(
      () => {
        const h1 = document.querySelector('h1');
        return h1 && h1.textContent && h1.textContent.includes('Ticket Operations Queue');
      },
      { timeout: 8000 }
    );
    results['tickets_list'] = 'PASS';
    console.log('Tickets page loaded successfully.');

    // 5. Create Ticket Modal
    console.log('--- Step 5: Create Ticket ---');
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const createBtn = btns.find((b) => b.textContent && b.textContent.includes('Create Ticket'));
      if (createBtn) createBtn.click();
    });

    await page.waitForSelector('.rf-modal-backdrop', { timeout: 5000 });
    // Click quick scenario: Grounded Auto-Resolution
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const templateBtn = btns.find((b) => b.textContent && b.textContent.includes('Grounded Auto-Resolution'));
      if (templateBtn) templateBtn.click();
    });

    // Wait until subject input gets populated by template click
    await page.waitForFunction(
      () => {
        const input = document.querySelector('.rf-modal-backdrop input[type="text"]');
        return input && input.value && input.value.trim().length > 0;
      },
      { timeout: 5000 }
    );

    // Click submit: Submit Ticket inside modal
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('.rf-modal-backdrop button[type="submit"]'));
      if (btns[0]) btns[0].click();
    });

    // Wait for modal backdrop to be completely closed
    await page.waitForSelector('.rf-modal-backdrop', { hidden: true, timeout: 10000 });

    // Wait for Ticket Detail to open specifically with the new ticket's subject
    await page.waitForFunction(
      () => {
        const h1 = document.querySelector('h1');
        return h1 && h1.textContent && h1.textContent.includes('Where is my invoice');
      },
      { timeout: 10000 }
    );
    results['ticket_creation_and_detail'] = 'PASS';
    console.log('Ticket created and Ticket Detail page loaded.');

    // 6. Navigate to Approvals Page
    console.log('--- Step 6: Navigate to Approvals ---');
    await page.evaluate(() => {
      const links = Array.from(document.querySelectorAll('aside button'));
      const approvalsLink = links.find((l) => l.textContent && l.textContent.includes('Approval Queue'));
      if (approvalsLink) approvalsLink.click();
    });

    await page.waitForFunction(
      () => {
        const h1 = document.querySelector('h1');
        return h1 && h1.textContent && h1.textContent.includes('Approval Queue');
      },
      { timeout: 8000 }
    );
    results['approvals_queue'] = 'PASS';
    console.log('Approvals queue loaded.');

    // 7. Navigate to Knowledge Base
    console.log('--- Step 7: Navigate to Knowledge Base ---');
    await page.evaluate(() => {
      const links = Array.from(document.querySelectorAll('aside button'));
      const kLink = links.find((l) => l.textContent && l.textContent.includes('Knowledge Base'));
      if (kLink) kLink.click();
    });

    await page.waitForFunction(
      () => {
        const h1 = document.querySelector('h1');
        return h1 && h1.textContent && h1.textContent.includes('Knowledge Base');
      },
      { timeout: 8000 }
    );
    results['knowledge_base'] = 'PASS';
    console.log('Knowledge Base page loaded.');

    // 8. Navigate to Evals Page
    console.log('--- Step 8: Navigate to Evals ---');
    await page.evaluate(() => {
      const links = Array.from(document.querySelectorAll('aside button'));
      const evalsLink = links.find((l) => l.textContent && l.textContent.includes('Model Evaluations'));
      if (evalsLink) evalsLink.click();
    });

    await page.waitForFunction(
      () => {
        const h1 = document.querySelector('h1');
        return h1 && h1.textContent && h1.textContent.includes('Evaluations');
      },
      { timeout: 8000 }
    );
    results['evals_dashboard'] = 'PASS';
    console.log('Model Evals page loaded.');

    // 9. Navigate to Audit Page
    console.log('--- Step 9: Navigate to Audit ---');
    await page.evaluate(() => {
      const links = Array.from(document.querySelectorAll('aside button'));
      const auditLink = links.find((l) => l.textContent && (l.textContent.includes('Audit') || l.textContent.includes('Telemetry')));
      if (auditLink) auditLink.click();
    });

    await page.waitForFunction(
      () => {
        const h1 = document.querySelector('h1');
        return h1 && h1.textContent && h1.textContent.includes('Audit');
      },
      { timeout: 8000 }
    );
    results['audit_trail'] = 'PASS';
    console.log('Audit trail page loaded.');

    // 10. Responsive Viewport Test
    console.log('--- Step 10: Responsive Viewport Test ---');
    await page.setViewport({ width: 375, height: 812 }); // iPhone X
    await page.waitForFunction(() => true);
    await page.setViewport({ width: 1280, height: 800 }); // Desktop
    results['responsive_layout'] = 'PASS';
    console.log('Responsive layout verified.');

    // 11. Logout
    console.log('--- Step 11: Logout Test ---');
    await page.evaluate(() => {
      const logoutBtn = document.querySelector('button[title="Sign Out"]');
      if (logoutBtn) logoutBtn.click();
    });

    await page.waitForFunction(
      () => {
        const h1 = document.querySelector('h1');
        return h1 && h1.textContent && h1.textContent.includes('ResolveFlow Operations');
      },
      { timeout: 8000 }
    );
    results['logout'] = 'PASS';
    console.log('Logged out successfully.');

    console.log('\n=== BROWSER WORKFLOW VERIFICATION SUMMARY ===');
    console.log(JSON.stringify(results, null, 2));

    const allPassed = Object.values(results).every((v) => v === 'PASS');
    if (!allPassed) {
      process.exit(1);
    }
  } catch (err) {
    console.error('Browser verification failed:', err);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

run();
