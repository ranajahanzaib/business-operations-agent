import { expect, test } from "@playwright/test";

const operatorToken = "local-operator-token";
const apiHeaders = { Authorization: `Bearer ${operatorToken}` };

test("approves, verifies, inspects, and recovers delayed-order workflow history", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Continue/ }).click();
  await expect(
    page.getByRole("heading", { name: "Good morning, Operator" }),
  ).toBeVisible();

  const before = await request.get(
    "http://127.0.0.1:8000/api/data/tickets?limit=100",
    { headers: apiHeaders },
  );
  expect((await before.json()).total).toBe(30);
  await page.getByRole("button", { name: "Run workflow" }).click();
  await page.getByRole("button", { name: /Approve all 25 actions/ }).waitFor();

  const awaiting = await request.get(
    "http://127.0.0.1:8000/api/data/tickets?limit=100",
    { headers: apiHeaders },
  );
  expect((await awaiting.json()).total).toBe(30);
  await page.getByRole("button", { name: /Approve all 25 actions/ }).click();
  await expect(page.getByRole("heading", { name: "completed" })).toBeVisible();

  const after = await request.get(
    "http://127.0.0.1:8000/api/data/tickets?limit=100",
    { headers: apiHeaders },
  );
  expect((await after.json()).total).toBe(55);
  const evaluations = await request.get(
    "http://127.0.0.1:8000/api/evaluations",
    { headers: apiHeaders },
  );
  expect((await evaluations.json()).items[0].status).toBe("passed");
  const latest = await request.get(
    "http://127.0.0.1:8000/api/data/tickets?limit=1&sort_by=created_at&descending=true",
    { headers: apiHeaders },
  );
  const ticket = (await latest.json()).items[0];

  await page.getByRole("button", { name: "Tickets", exact: true }).click();
  await page.getByRole("textbox", { name: "Search tickets" }).fill(ticket.id);
  await page.getByRole("button", { name: ticket.id }).click();
  await expect(page.getByText(ticket.ticket_number)).toBeVisible();

  await page.reload();
  await page.getByRole("button", { name: "Workspace" }).click();
  await page
    .getByRole("button", { name: /Find orders delayed more than five days/ })
    .click();
  await expect(page.getByRole("heading", { name: "completed" })).toBeVisible();
  await expect(
    page.locator(".event b").filter({ hasText: "verification" }).first(),
  ).toBeVisible();
});
