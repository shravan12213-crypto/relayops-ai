import { test, expect } from "@playwright/test";

/**
 * Golden Path End-to-End Test Suite:
 * 1. Login as Aarav (Outgoing)
 * 2. Load demo / verify project PayFlow
 * 3. Create handover & run pipeline
 * 4. Review Studio: inspect claims, resolve ambiguities, create snapshot v1
 * 5. Dual Sign-off: Aarav (outgoing) signs -> Meera (lead) signs -> Deliver handover
 * 6. Successor Handover Portal (Kabir): view signed handover, ask Copilot with citations, verify refusal on off-topic query
 * 7. Contractor Firewall (Dev Mukherjee): verify sensitivity >= 2 masked placeholders with zero confidential leakage
 */

test.describe("RelayOps Golden Path E2E Journey", () => {
  let handoverId = "";

  test("1. Login as Aarav Kulkarni (Outgoing) and verify dashboard", async ({ page }) => {
    await page.goto("/login");
    await expect(page).toHaveTitle(/RelayOps/i);

    // Click Aarav Kulkarni demo account
    const aaravBtn = page.getByRole("button", { name: /Log in as Aarav Kulkarni/i });
    await expect(aaravBtn).toBeVisible();
    await aaravBtn.click();

    // Verify redirected to dashboard with Aarav's identity and clearance badge
    await expect(page).toHaveURL(/\/(?:dashboard)?$/);
    await expect(page.getByText(/Aarav Kulkarni/i).first()).toBeVisible();
  });

  test("2. Inspect PayFlow project sources and trigger pipeline", async ({ page, request }) => {
    // Ensure user session
    await page.goto("/login");
    await page.getByRole("button", { name: /Log in as Aarav Kulkarni/i }).click();

    // Ensure demo dataset is loaded via API
    const demoLoad = await request.post("/api/v1/projects/payflow/demo-load");
    expect(demoLoad.status()).toBeLessThan(500);

    // Get or create handover
    const hoRes = await request.get("/api/v1/handovers?project_slug=payflow");
    const handovers = await hoRes.json();
    if (handovers.items && handovers.items.length > 0) {
      handoverId = handovers.items[0].id;
    } else {
      // Create fresh handover
      const usersRes = await request.get("/api/v1/users");
      const users = await usersRes.json();
      const outgoing = users.find((u: { role: string }) => u.role === "outgoing");
      const lead = users.find((u: { role: string }) => u.role === "lead");
      const successor = users.find((u: { role: string }) => u.role === "successor");

      const createRes = await request.post("/api/v1/handovers", {
        data: {
          project_slug: "payflow",
          outgoing_user_id: outgoing.id,
          lead_user_id: lead.id,
          successor_user_id: successor.id,
          due_date: new Date(Date.now() + 86400000 * 14).toISOString(),
          notes: "Playwright E2E Handover",
        },
      });
      const created = await createRes.json();
      handoverId = created.id;
    }

    expect(handoverId).toBeTruthy();

    // Run pipeline
    const runRes = await request.post(`/api/v1/handovers/${handoverId}/run`);
    expect(runRes.status()).toBeLessThan(400);

    // Visit Review Studio
    await page.goto(`/handovers/${handoverId}/review`);
    await expect(page.getByText(/Review Studio/i).first()).toBeVisible({ timeout: 15000 });
  });

  test("3. Review Studio: Verify claims, citation pills, and snapshot creation", async ({ page, request }) => {
    // Login as Meera (Lead) who has full privileges to edit, snapshot, and resolve
    await page.goto("/login");
    await page.getByRole("button", { name: /Log in as Meera Patel/i }).click();

    await page.goto(`/handovers/${handoverId}/review`);
    await expect(page.getByText(/Review Studio/i).first()).toBeVisible({ timeout: 15000 });

    // Verify claim cards are visible with citation pills
    const claimCards = page.locator("article, [data-testid='claim-card']");
    await expect(claimCards.first()).toBeVisible();

    // Verify Citation Pills (e.g. PR #89, PAY-142, or ADR-003)
    const citationPills = page.locator("button, span").filter({ hasText: /PR #|PAY-|ADR-|RFC-/i });
    await expect(citationPills.first()).toBeVisible();

    // Accept all claims via API to ensure clean precondition for sign-off
    const claimsRes = await request.get(`/api/v1/handovers/${handoverId}/claims`);
    const claimsData = await claimsRes.json();
    for (const c of claimsData.items || []) {
      if (c.status === "draft" || c.status === "rejected") {
        await request.patch(`/api/v1/handovers/${handoverId}/claims/${c.id}`, {
          data: { status: "accepted" },
        });
      }
    }

    // Resolve or waive open high-severity ambiguities
    const ambRes = await request.get(`/api/v1/handovers/${handoverId}/ambiguities`);
    const ambData = await ambRes.json();
    for (const a of ambData.items || []) {
      if (a.severity === "high" && a.status === "open") {
        await request.post(`/api/v1/handovers/${handoverId}/ambiguities/${a.id}/resolve`, {
          data: { resolution: "Waived for Playwright E2E automated test run" },
        });
      }
    }

    // Create Snapshot v1
    const snapRes = await request.post(`/api/v1/handovers/${handoverId}/snapshot`, {
      data: { reason: "v1.0 E2E Golden Snapshot" },
    });
    expect(snapRes.status()).toBeLessThan(400);
    const snap = await snapRes.json();
    expect(snap.version).toBeGreaterThanOrEqual(1);
  });

  test("4. Dual Sign-off Lifecycle and Delivery", async ({ page, request }) => {
    // Step A: Aarav (Outgoing) signs off
    await page.goto("/login");
    await page.getByRole("button", { name: /Log in as Aarav Kulkarni/i }).click();

    const hoRes = await request.get(`/api/v1/handovers/${handoverId}`);
    const handover = await hoRes.json();
    const ver = handover.current_version || 1;

    const outSign = await request.post(`/api/v1/handovers/${handoverId}/signoff`, {
      data: { version: ver, comment: "Outgoing handover verified by Aarav" },
    });
    expect(outSign.status()).toBeLessThan(400);
    const outSignData = await outSign.json();
    expect(outSignData.both_signed).toBe(false);

    // Step B: Meera (Lead) signs off
    await page.goto("/login");
    await page.getByRole("button", { name: /Log in as Meera Patel/i }).click();

    const leadSign = await request.post(`/api/v1/handovers/${handoverId}/signoff`, {
      data: { version: ver, comment: "Lead sign-off approved by Meera" },
    });
    expect(leadSign.status()).toBeLessThan(400);
    const leadSignData = await leadSign.json();
    expect(leadSignData.both_signed).toBe(true);

    // Step C: Deliver handover
    const deliverRes = await request.post(`/api/v1/handovers/${handoverId}/deliver`);
    expect(deliverRes.status()).toBeLessThan(400);
    const deliverData = await deliverRes.json();
    expect(deliverData.status).toBe("delivered");
  });

  test("5. Kabir Sharma (Successor) Portal: Trust strip, receipts, and grounded Copilot", async ({
    page,
  }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: /Log in as Kabir Sharma/i }).click();

    // Visit Successor Handover Portal
    await page.goto(`/handovers/${handoverId}/portal`);
    await expect(page.getByText(/Handover Portal/i).first()).toBeVisible({ timeout: 15000 });

    // Trust strip: signed by Aarav and Meera
    await expect(page.getByText(/Aarav Kulkarni/i).first()).toBeVisible();
    await expect(page.getByText(/Meera Patel/i).first()).toBeVisible();

    // Section cards visible with citation pills
    await expect(page.getByText(/Architecture Decisions|Blockers|Runbooks/i).first()).toBeVisible();

    // Copilot: Ask domain question regarding PAY-142
    await page.goto(`/handovers/${handoverId}/copilot`);
    const input = page.getByPlaceholder(/Ask anything about architecture/i);
    await expect(input).toBeVisible();

    await input.fill("What is the status of PAY-142 vendor sandbox?");
    await page.keyboard.press("Enter");

    // Verify grounded answer with citation link
    await expect(page.getByText(/PAY-142/i).first()).toBeVisible({ timeout: 15000 });

    // Copilot: Ask out-of-domain question -> must refuse
    await input.fill("What is the best secret recipe for chocolate cake?");
    await page.keyboard.press("Enter");

    await expect(page.getByText(/I can't verify this from the handover evidence/i)).toBeVisible({
      timeout: 15000,
    });
  });

  test("6. Contractor Security Clearance Firewall: Dev Mukherjee", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: /Log in as Dev Mukherjee/i }).click();

    // Dev has clearance Level 1 (Contractor)
    await page.goto(`/handovers/${handoverId}/portal`);
    await expect(page.getByText(/Handover Portal/i).first()).toBeVisible({ timeout: 15000 });

    // Verify restricted clearance notice or masked placeholder is present
    const maskedOrRestricted = page.locator("text=/Restricted|Confidential|Masked/i");
    await expect(maskedOrRestricted.first()).toBeVisible();

    // Zero secret leakage: confidential strings must NEVER be rendered in DOM
    const bodyContent = await page.content();
    expect(bodyContent).not.toContain("david.vance@acquirercorp.com");
    expect(bodyContent).not.toContain("+1-555-019-2834");
    expect(bodyContent).not.toContain("$185,000");
  });
});
