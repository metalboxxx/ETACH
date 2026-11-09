/**
 * R15.3: dropping a 2-page PDF → 2 thumbnails; a DOCX with 1 image → 1 text page + 1 thumbnail.
 * The files in e2e/fixtures/ are synthetic (made with PyMuPDF and python-docx; no student data).
 */
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { connect, dropFiles } from "./drop";

const FIXTURES = join(import.meta.dirname, "fixtures");

test.beforeEach(async ({ page }) => {
  await connect(page);
  await expect(page.getByRole("tab", { name: "Chats" })).toBeVisible();
  await expect(page.getByTestId("connection-notice")).toHaveCount(0);
});

test("a 2-page PDF gives 2 thumbnails", async ({ page }) => {
  await dropFiles(page, [join(FIXTURES, "two-pages.pdf")]);
  const card = page.getByTestId("photo-check-card");
  await expect(card).toBeVisible();
  await expect(card.getByTestId("photo-thumb")).toHaveCount(2);
  await expect(card.locator('[data-testid="photo-thumb"] img')).toHaveCount(2);
  await expect(card.getByTestId("broken-page")).toHaveCount(0);
});

test("a DOCX with 1 image gives 1 text page + 1 thumbnail", async ({ page }) => {
  await dropFiles(page, [join(FIXTURES, "one-image.docx")]);
  const card = page.getByTestId("photo-check-card");
  await expect(card).toBeVisible();
  await expect(card.getByTestId("photo-thumb")).toHaveCount(2);
  await expect(card.getByTestId("photo-thumb").nth(0).getByTestId("text-page")).toBeVisible();
  await expect(card.getByTestId("photo-thumb").nth(1).locator("img")).toBeVisible();
  await expect(card.getByTestId("broken-page")).toHaveCount(0);
});
